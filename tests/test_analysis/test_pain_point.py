"""Pain Point Agent (run_pain_point_agent/_upsert_pain_point) — cần Postgres test thật vì thao
tác qua Post/Prediction/PainPoint có quan hệ FK thật, giống các test khác trong test_analysis/.

Trọng tâm: (1) mô tả LLM chỉ được gọi lại khi CÓ GÌ MỚI (case mới hoặc post_count đổi) — sửa lỗi
thực tế quan sát được (pain point của TP Bank/TPBank Mobile không bao giờ được tạo dù dữ liệu đã
đủ ngưỡng, vì trước đây gọi lại LLM mỗi chu kỳ cho MỌI pain point khiến quota hết làm treo hàng
phút, các topic sau trong vòng lặp không bao giờ được xử lý); (2) lỗi ở 1 nhóm không làm mất kết
quả của nhóm khác; (3) nhóm dưới ngưỡng không được tạo pain point."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analysis.pain_point import run_pain_point_agent
from src.config import get_settings
from src.db.models import Base, Post, Prediction, Source, Topic, User


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
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test pain point agent"
)


@pytest.fixture(scope="module")
def engine():
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)


@pytest.fixture
def session(engine):
    session_factory = sessionmaker(bind=engine)
    db_session = session_factory()
    yield db_session
    db_session.rollback()
    db_session.close()


def _make_user(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    db_session.add(user)
    db_session.flush()
    return user


def _make_topic(db_session, user, **overrides) -> Topic:
    defaults = {
        "user_id": user.id,
        "name": "Test Bank Pain Point",
        "keywords": [],
        "alert_threshold": 3,
        "notify_enabled": False,
        "notify_channel": "web",
        "status": "active",
    }
    defaults.update(overrides)
    topic = Topic(**defaults)
    db_session.add(topic)
    db_session.flush()
    return topic


def _make_source(db_session, topic) -> Source:
    source = Source(topic_id=topic.id, type="google_play", config={})
    db_session.add(source)
    db_session.flush()
    return source


def _make_analyzed_post(db_session, topic, source, *, topic_label, severity=0.5, sentiment="negative"):
    post = Post(
        topic_id=topic.id,
        source_id=source.id,
        external_id=str(uuid.uuid4()),
        content="nội dung test",
        language="vi",
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(
        Prediction(
            post_id=post.id,
            sentiment=sentiment,
            topic_label=topic_label,
            severity_score=severity,
            confidence_score=0.9,
            final_confidence=0.9,
            reference_status="no_match",
            consensus_status="confirmed",
        )
    )
    db_session.flush()
    return post


@patch("src.analysis.pain_point._generate_description")
@patch("src.analysis.pain_point.check_and_notify")
def test_group_below_threshold_not_upserted(mock_notify, mock_describe, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=5)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()

    pain_points = run_pain_point_agent(session, topic)

    assert pain_points == []
    mock_describe.assert_not_called()


@patch("src.analysis.pain_point._generate_description")
@patch("src.analysis.pain_point.check_and_notify")
def test_new_pain_point_calls_llm_description(mock_notify, mock_describe, session):
    mock_describe.return_value = "Mô tả do LLM sinh ra."
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=3)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()

    pain_points = run_pain_point_agent(session, topic)

    assert len(pain_points) == 1
    assert pain_points[0].post_count == 3
    assert pain_points[0].description == "Mô tả do LLM sinh ra."
    mock_describe.assert_called_once()


@patch("src.analysis.pain_point._generate_description")
@patch("src.analysis.pain_point.check_and_notify")
def test_unchanged_post_count_skips_llm_call(mock_notify, mock_describe, session):
    """Sửa lỗi thực tế: trước đây LLM bị gọi lại MỖI chu kỳ cho MỌI pain point dù không có gì mới,
    khiến quota hết làm treo hàng phút và các topic sau trong vòng lặp không bao giờ được xử lý."""
    mock_describe.return_value = "Mô tả lần đầu."
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=3)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()

    run_pain_point_agent(session, topic)
    assert mock_describe.call_count == 1

    # Chạy lại chu kỳ thứ 2 — CÙNG dữ liệu, không post nào mới.
    pain_points = run_pain_point_agent(session, topic)

    assert mock_describe.call_count == 1  # không gọi thêm lần nào
    assert pain_points[0].description == "Mô tả lần đầu."  # giữ nguyên mô tả cũ
    assert pain_points[0].post_count == 3


@patch("src.analysis.pain_point._generate_description")
@patch("src.analysis.pain_point.check_and_notify")
def test_post_count_change_triggers_new_description(mock_notify, mock_describe, session):
    mock_describe.side_effect = ["Mô tả lần đầu.", "Mô tả cập nhật."]
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=3)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()

    run_pain_point_agent(session, topic)
    assert mock_describe.call_count == 1

    # Có thêm 1 post mới thuộc cùng nhóm -> post_count đổi (3 -> 4) -> phải gọi lại LLM.
    _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()
    pain_points = run_pain_point_agent(session, topic)

    assert mock_describe.call_count == 2
    assert pain_points[0].description == "Mô tả cập nhật."
    assert pain_points[0].post_count == 4


@patch("src.analysis.pain_point.check_and_notify")
def test_llm_failure_on_one_group_does_not_affect_other_groups(mock_notify, session):
    """1 nhóm lỗi khi tạo mô tả (vd rate-limit) không được làm mất kết quả của nhóm khác đã xử lý
    xong trong cùng lượt chạy."""
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=3)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="phí dịch vụ")
    session.commit()

    def _flaky_describe(topic_label, items):
        if topic_label == "lỗi ứng dụng":
            raise RuntimeError("giả lập lỗi LLM / rate limit")
        return "Mô tả ổn định."

    with patch("src.analysis.pain_point._generate_description", side_effect=_flaky_describe):
        pain_points = run_pain_point_agent(session, topic)

    titles = {p.title: p for p in pain_points}
    assert set(titles) == {"lỗi ứng dụng", "phí dịch vụ"}
    # Nhóm lỗi vẫn được lưu (post_count/trend không phụ thuộc LLM) nhưng dùng mô tả fallback.
    assert "phản hồi thuộc nhóm" in titles["lỗi ứng dụng"].description
    assert titles["lỗi ứng dụng"].post_count == 3
    assert titles["phí dịch vụ"].description == "Mô tả ổn định."


@patch("src.analysis.pain_point._generate_description")
@patch("src.analysis.pain_point.check_and_notify")
def test_positive_and_neutral_posts_excluded_from_grouping(mock_notify, mock_describe, session):
    """Pain point = ĐIỂM ĐAU, chỉ gồm review sentiment=negative — review tích cực/trung lập cùng
    topic_label KHÔNG được tính vào post_count, và 1 nhóm toàn tích cực/trung lập (dù nhiều review)
    không được tạo pain point nào cả."""
    mock_describe.return_value = "Mô tả."
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=3)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="trải nghiệm sử dụng", sentiment="negative")
    for _ in range(5):
        _make_analyzed_post(session, topic, source, topic_label="trải nghiệm sử dụng", sentiment="positive")
    for _ in range(2):
        _make_analyzed_post(session, topic, source, topic_label="trải nghiệm sử dụng", sentiment="neutral")
    # Nhóm khác toàn tích cực, vượt ngưỡng nếu tính cả — không được tạo pain point nào.
    for _ in range(4):
        _make_analyzed_post(session, topic, source, topic_label="chăm sóc khách hàng", sentiment="positive")
    session.commit()

    pain_points = run_pain_point_agent(session, topic)

    titles = {p.title: p for p in pain_points}
    assert set(titles) == {"trải nghiệm sử dụng"}
    assert titles["trải nghiệm sử dụng"].post_count == 3  # chỉ đếm 3 review tiêu cực, bỏ 5 tích cực + 2 trung lập


@patch("src.analysis.pain_point._generate_description")
@patch("src.analysis.pain_point.check_and_notify")
def test_overridden_due_at_survives_recompute_cycle(mock_notify, mock_describe, session):
    """Quản lý tự đặt hạn xử lý (PATCH .../lifecycle) không được bị auto-recompute của chu kỳ phân
    tích sau ghi đè lại — kể cả khi post_count đổi (vốn dĩ NGUYÊN NHÂN kích hoạt recompute cho case
    bình thường, xem test_post_count_change_triggers_new_description)."""
    mock_describe.return_value = "Mô tả."
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=3)
    source = _make_source(session, topic)
    for _ in range(3):
        _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()

    pain_points = run_pain_point_agent(session, topic)
    pain_point = pain_points[0]

    custom_due_at = datetime.now(UTC) + timedelta(days=365)
    pain_point.due_at = custom_due_at
    pain_point.due_at_overridden = True
    session.commit()

    # Thêm post mới vào cùng nhóm -> post_count đổi (3 -> 4), điều kiện lẽ ra kích hoạt recompute.
    _make_analyzed_post(session, topic, source, topic_label="lỗi ứng dụng")
    session.commit()
    pain_points = run_pain_point_agent(session, topic)

    updated = pain_points[0]
    assert updated.post_count == 4
    assert updated.due_at_overridden is True
    assert updated.due_at == custom_due_at
