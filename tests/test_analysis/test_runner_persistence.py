"""Kiểm tra runner lưu ĐÚNG 3 trường tách bạch vào predictions, dùng LLM giả để không tốn quota.

Quan trọng nhất: `verification_status` (danh tính khách hàng) phải luôn là 'unverified' bất kể
kết quả phân tích nội dung ra sao — đây là ràng buộc chống việc vô tình nối lại 2 khái niệm đã
tách ở migration 0005.
"""

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analysis.llm import record_usage
from src.analysis.schemas import ClassificationResult, ReferenceSource, SeedingResult, VerificationResult
from src.config import get_settings
from src.db.models import Base, LLMUsage, Post, Prediction, Source, Topic, User


def _default_test_db_url() -> str:
    base = get_settings().database_url
    root, sep, dbname = base.rpartition("/")
    return f"{root}/{dbname}_test" if sep else base


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _default_test_db_url())


def _connectable_engine():
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect():
            pass
        return engine
    except Exception:
        return None


_engine = _connectable_engine()

pytestmark = pytest.mark.skipif(
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test"
)


@pytest.fixture(scope="module", autouse=True)
def _setup_tables():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def seeded_post():
    """Tạo user/topic/source/post tối thiểu, trả về post_id."""
    session = sessionmaker(bind=_engine)()
    try:
        user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
        session.add(user)
        session.flush()
        topic = Topic(user_id=user.id, name="T", status="active")
        session.add(topic)
        session.flush()
        source = Source(topic_id=topic.id, type="google_play", config={})
        session.add(source)
        session.flush()
        post = Post(
            topic_id=topic.id,
            source_id=source.id,
            external_id=str(uuid.uuid4()),
            content="Chuyển tiền 2 triệu lúc 9h sáng báo lỗi TR-05, trừ tiền nhưng người nhận không nhận được",
            language="vi",
        )
        session.add(post)
        session.commit()
        yield post.id, topic.id
    finally:
        session.close()


def _run_with_mocked_llm(post_id, topic_id, content, *, reliability, reference_status, sources=()):
    classification = ClassificationResult(
        sentiment="negative",
        topic_label="lỗi giao dịch",
        severity_score=0.9,
        confidence_score=0.9,
        content_reliability=reliability,
        is_question=False,
    )
    verification = VerificationResult(
        reference_status=reference_status,
        reference_sources=list(sources),
        reference_confidence=0.8,
    )
    # patch tại module SỬ DỤNG (src.analysis.graph), không phải module định nghĩa — `from x import y`
    # tạo binding độc lập nên patch ở chỗ định nghĩa sẽ không có tác dụng.
    # SessionLocal cũng phải patch: _analyze_post_standalone tự mở session riêng (mỗi worker 1
    # session vì Session không thread-safe), mặc định trỏ DB dev chứ không phải DB test.
    with (
        patch("src.analysis.graph.classify_post", return_value=classification),
        patch("src.analysis.graph.verify_post", return_value=verification),
        patch("src.analysis.consensus._generate_reasoning", return_value="lý do giả lập"),
        patch("src.analysis.runner.SessionLocal", sessionmaker(bind=_engine)),
    ):
        from src.analysis.runner import _analyze_post_standalone

        return _analyze_post_standalone(post_id, topic_id, content)


def test_persists_three_separated_fields(seeded_post):
    post_id, topic_id = seeded_post
    outcome = _run_with_mocked_llm(post_id, topic_id, "nội dung", reliability="high", reference_status="no_match")
    assert outcome.success

    session = sessionmaker(bind=_engine)()
    try:
        pred = session.query(Prediction).filter_by(post_id=post_id).one()
        assert pred.content_reliability == "high"
        assert pred.reference_status == "no_match"
        # Danh tính KHÔNG bao giờ tự động thành 'verified' — chưa có tích hợp CRM.
        assert pred.verification_status == "unverified"
        assert pred.identity_checked_at is None
        assert pred.consensus_status == "confirmed"
    finally:
        session.close()


@pytest.fixture
def seeded_topic_with_posts():
    """3 post CHƯA có prediction, cùng 1 topic — dùng để kiểm tra run_analysis_cycle dừng sớm khi
    hết quota (khác seeded_post ở trên, vốn chỉ có 1 post và test ở mức _analyze_post_standalone)."""
    session = sessionmaker(bind=_engine)()
    try:
        user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
        session.add(user)
        session.flush()
        topic = Topic(user_id=user.id, name="T-quota", status="active")
        session.add(topic)
        session.flush()
        source = Source(topic_id=topic.id, type="google_play", config={})
        session.add(source)
        session.flush()

        post_ids = []
        for i in range(3):
            post = Post(
                topic_id=topic.id,
                source_id=source.id,
                external_id=str(uuid.uuid4()),
                content=f"nội dung review {i}",
                language="vi",
            )
            session.add(post)
            session.flush()
            post_ids.append(post.id)
        session.commit()
        yield topic.id, post_ids
    finally:
        session.close()


def test_run_analysis_cycle_stops_early_on_quota_exhaustion(seeded_topic_with_posts):
    """Hết quota Gemini (429 RESOURCE_EXHAUSTED) ở post đầu tiên -> chu kỳ dừng NGAY, không thử
    tiếp các post còn lại (mỗi post cũng sẽ fail cùng lý do, chỉ tốn thời gian). Các post chưa được
    phân tích vẫn ở DB, chỉ đơn giản là chưa có Prediction — đúng ngữ nghĩa "pending queue"."""
    topic_id, post_ids = seeded_topic_with_posts
    quota_error = Exception("429 Resource has been exhausted (RESOURCE_EXHAUSTED)")

    with (
        patch("src.analysis.graph.classify_post", side_effect=quota_error) as mock_classify,
        patch("src.analysis.runner.SessionLocal", sessionmaker(bind=_engine)),
    ):
        from src.analysis.runner import run_analysis_cycle

        result = run_analysis_cycle(topic_id=topic_id)

    assert result.quota_exhausted is True
    assert result.analyzed == 0
    assert result.pending_remaining == len(post_ids) - 1
    # Chỉ 1 post được thử — không kiên trì gọi LLM cho 2 post còn lại sau khi đã phát hiện hết quota.
    assert mock_classify.call_count == 1

    session = sessionmaker(bind=_engine)()
    try:
        predictions = session.query(Prediction).filter(Prediction.post_id.in_(post_ids)).all()
        assert predictions == []
    finally:
        session.close()


def test_persists_llm_usage_recorded_during_analysis(seeded_post):
    """_analyze_post_standalone phải ghi lại llm_usage cho ĐÚNG topic của post — record_usage() bên
    trong classify_post thật (ở đây giả lập bằng side_effect) chỉ có tác dụng nếu có ai đó gọi
    reset_usage_log() trước và pop_usage_log()+persist sau, đúng như runner.py thật làm."""
    from langchain_core.messages import AIMessage

    post_id, topic_id = seeded_post
    classification = ClassificationResult(
        sentiment="negative",
        topic_label="lỗi giao dịch",
        severity_score=0.9,
        confidence_score=0.9,
        content_reliability="high",
        is_question=False,
    )
    verification = VerificationResult(reference_status="no_match", reference_sources=[], reference_confidence=0.8)

    def _fake_classify(content):
        record_usage(
            "classification",
            AIMessage(content="", usage_metadata={"input_tokens": 200, "output_tokens": 40, "total_tokens": 240}),
            "gemma-4-26b-a4b-it",
        )
        return classification

    with (
        patch("src.analysis.graph.classify_post", side_effect=_fake_classify),
        # Không record_usage("seeding_detection", ...) thật — Seeding Agent bị mock hẳn, giống
        # verify_post bên dưới, nên không phát sinh usage row thứ 2 làm sai lệch assert len==1 ở
        # cuối test này (test chỉ quan tâm usage của classification).
        patch("src.analysis.graph.detect_seeding", return_value=SeedingResult(is_seeding=False, reasoning="test")),
        patch("src.analysis.graph.verify_post", return_value=verification),
        patch("src.analysis.consensus._generate_reasoning", return_value="lý do giả lập"),
        patch("src.analysis.runner.SessionLocal", sessionmaker(bind=_engine)),
    ):
        from src.analysis.runner import _analyze_post_standalone

        outcome = _analyze_post_standalone(post_id, topic_id, "nội dung")
    assert outcome.success

    session = sessionmaker(bind=_engine)()
    try:
        usage_rows = session.query(LLMUsage).filter(LLMUsage.topic_id == topic_id).all()
        assert len(usage_rows) == 1
        assert usage_rows[0].call_type == "classification"
        assert usage_rows[0].input_tokens == 200
        assert usage_rows[0].output_tokens == 40
        topic = session.query(Topic).filter(Topic.id == topic_id).one()
        assert usage_rows[0].user_id == topic.user_id
    finally:
        session.close()


def test_identity_stays_unverified_even_when_reference_matched(seeded_post):
    """Khớp được văn bản chính thức KHÔNG có nghĩa là đã xác minh được danh tính khách hàng."""
    post_id, topic_id = seeded_post
    outcome = _run_with_mocked_llm(
        post_id,
        topic_id,
        "nội dung",
        reliability="high",
        reference_status="matched",
        sources=[
            ReferenceSource(doc_id="qd-2345", title="Quyết định 2345", url="https://x", relation="explains_as_policy")
        ],
    )
    assert outcome.success

    session = sessionmaker(bind=_engine)()
    try:
        pred = session.query(Prediction).filter_by(post_id=post_id).one()
        assert pred.reference_status == "matched"
        assert pred.consensus_status == "dismissed"
        assert pred.verification_status == "unverified"
    finally:
        session.close()
