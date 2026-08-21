"""Source trùng định danh app thật (package_name/app_id) ở topic khác phải đồng bộ content +
Prediction từ source canonical thay vì tự gọi API bên ngoài/LLM lại từ đầu — xem
src/pipeline/processing/cross_topic_dedup.py. Dùng DB Postgres thật (như test_runner_persistence.py)
vì logic phụ thuộc UNIQUE(source_id, external_id) và ON CONFLICT của upsert_posts.

QUAN TRỌNG: fixture bảng là module-scoped (dữ liệu các test CHIA SẺ cùng 1 DB trong suốt file, xem
_setup_tables) — mỗi test PHẢI dùng package_name/app_id RIÊNG (uuid) thay vì hardcode 1 giá trị
thật, nếu không resolve_follower_sources()/run_cycle() (vốn nhìn TOÀN BỘ DB) sẽ vô tình gộp nhầm
source của các test khác nhau vào cùng 1 nhóm trùng định danh.
"""

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test"
)


@pytest.fixture(scope="module", autouse=True)
def _setup_tables():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def session():
    s = sessionmaker(bind=_engine)()
    try:
        yield s
    finally:
        s.close()


def _unique_package_name() -> str:
    return f"vn.test.{uuid.uuid4().hex}.mbanking"


def _unique_app_id() -> str:
    return uuid.uuid4().hex


def _make_user(session) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    session.add(user)
    session.flush()
    return user


def _make_topic(session, user, name="T") -> Topic:
    topic = Topic(user_id=user.id, name=name, status="active")
    session.add(topic)
    session.flush()
    return topic


def _make_source(session, topic, *, type_="google_play", config=None) -> Source:
    source = Source(topic_id=topic.id, type=type_, config=config or {})
    session.add(source)
    session.flush()
    return source


def _make_post(session, topic, source, external_id, content="nội dung", **kwargs) -> Post:
    post = Post(topic_id=topic.id, source_id=source.id, external_id=external_id, content=content, **kwargs)
    session.add(post)
    session.flush()
    return post


def _make_prediction(session, post, **overrides) -> Prediction:
    defaults = dict(
        sentiment="negative",
        topic_label="lỗi ứng dụng",
        severity_score=0.8,
        confidence_score=0.9,
        consensus_status="confirmed",
        final_confidence=0.9,
        reasoning="lý do",
    )
    defaults.update(overrides)
    prediction = Prediction(post_id=post.id, **defaults)
    session.add(prediction)
    session.flush()
    return prediction


def test_sync_copies_posts_and_predictions_without_calling_collector(session):
    user = _make_user(session)
    canonical_topic = _make_topic(session, user, "Canonical")
    follower_topic = _make_topic(session, user, "Follower")

    package_name = _unique_package_name()
    canonical_source = _make_source(session, canonical_topic, config={"package_name": package_name})
    follower_source = _make_source(session, follower_topic, config={"package_name": package_name})

    analyzed_post = _make_post(session, canonical_topic, canonical_source, "ext-1", content="đã phân tích")
    _make_prediction(session, analyzed_post, topic_label="lỗi đăng nhập")
    _make_post(session, canonical_topic, canonical_source, "ext-2", content="chưa phân tích")
    session.commit()

    with patch("src.pipeline.runner.get_collector") as mock_get_collector:
        from src.pipeline.runner import _sync_post_source_from_canonical

        result = _sync_post_source_from_canonical(session, follower_topic, follower_source, canonical_source.id)

    assert mock_get_collector.call_count == 0  # follower không bao giờ tự gọi API bên ngoài
    assert result.inserted == 2
    assert result.error is None

    follower_posts = {p.external_id: p for p in session.query(Post).filter_by(source_id=follower_source.id).all()}
    assert set(follower_posts) == {"ext-1", "ext-2"}
    assert follower_posts["ext-1"].content == "đã phân tích"

    pred_1 = session.query(Prediction).filter_by(post_id=follower_posts["ext-1"].id).one_or_none()
    pred_2 = session.query(Prediction).filter_by(post_id=follower_posts["ext-2"].id).one_or_none()
    assert pred_1 is not None and pred_1.topic_label == "lỗi đăng nhập"
    assert pred_2 is None  # canonical cũng chưa phân tích post này -> follower cũng chưa có


def test_sync_does_not_overwrite_existing_local_prediction(session):
    """Post follower đã tự có Prediction riêng từ trước (vd trước khi có cơ chế đồng bộ này) không
    bị ghi đè, kể cả khi canonical có giá trị khác."""
    user = _make_user(session)
    canonical_topic = _make_topic(session, user, "Canonical-2")
    follower_topic = _make_topic(session, user, "Follower-2")

    app_id = _unique_app_id()
    canonical_source = _make_source(session, canonical_topic, config={"app_id": app_id}, type_="app_store")
    follower_source = _make_source(session, follower_topic, config={"app_id": app_id}, type_="app_store")

    canonical_post = _make_post(session, canonical_topic, canonical_source, "shared-ext", content="review gốc")
    _make_prediction(session, canonical_post, topic_label="phí dịch vụ")

    follower_post = _make_post(session, follower_topic, follower_source, "shared-ext", content="review gốc")
    _make_prediction(session, follower_post, topic_label="đã có sẵn từ trước")
    session.commit()

    from src.pipeline.runner import _sync_post_source_from_canonical

    _sync_post_source_from_canonical(session, follower_topic, follower_source, canonical_source.id)

    kept = session.query(Prediction).filter_by(post_id=follower_post.id).one()
    assert kept.topic_label == "đã có sẵn từ trước"


def test_maybe_resolve_identity_saves_resolved_package_name(session):
    """Source mới tạo chỉ có {"query": "..."} — resolve_identity() của collector phải được gọi và
    kết quả lưu lại vào Source.config, để chu kỳ này (không phải chu kỳ sau) đã nhận diện được
    trùng định danh với source khác nếu có."""
    user = _make_user(session)
    topic = _make_topic(session, user, "Query-only")
    source = _make_source(session, topic, config={"query": "SHB Saha", "country": "vn", "lang": "vi"})
    session.commit()

    package_name = _unique_package_name()
    from src.pipeline.runner import _maybe_resolve_identity

    with patch(
        "src.pipeline.collectors.google_play.GooglePlayCollector.resolve_identity",
        return_value={"package_name": package_name},
    ):
        _maybe_resolve_identity(session, source)

    session.refresh(source)
    assert source.config["package_name"] == package_name
    assert source.config["query"] == "SHB Saha"  # giữ nguyên field cũ, chỉ bổ sung


def test_maybe_resolve_identity_noop_when_already_resolved(session):
    """Source đã có package_name sẵn thì không cần gọi resolver (không tốn network call)."""
    user = _make_user(session)
    topic = _make_topic(session, user, "Already-resolved")
    source = _make_source(session, topic, config={"package_name": _unique_package_name()})
    session.commit()

    from src.pipeline.runner import _maybe_resolve_identity

    with patch("src.pipeline.collectors.google_play.GooglePlayCollector.resolve_identity") as mock_resolve:
        _maybe_resolve_identity(session, source)

    mock_resolve.assert_not_called()


def test_new_query_only_topic_syncs_from_canonical_on_first_cycle():
    """Kịch bản đúng câu hỏi người dùng đặt ra: tài khoản khác tạo topic MỚI cho 1 ngân hàng đã có
    sẵn dữ liệu crawl+phân tích ở topic khác — ngay CHU KỲ ĐẦU TIÊN (run_cycle) phải nhận được toàn
    bộ dữ liệu đã có, KHÔNG tự gọi collect() để backfill lại từ đầu.

    run_cycle() nhìn TOÀN BỘ topic active trong DB (kể cả của test khác, do fixture module-scoped)
    nên package_name dùng ở đây PHẢI riêng biệt (_unique_package_name) — nếu không sẽ bị gộp nhầm
    nhóm với source của test khác chạy trước, làm sai lệch việc xác định ai là canonical.
    """
    session = sessionmaker(bind=_engine)()
    try:
        package_name = _unique_package_name()
        user = _make_user(session)
        canonical_topic = _make_topic(session, user, "Canonical-existing")
        canonical_source = _make_source(session, canonical_topic, config={"package_name": package_name})
        analyzed = _make_post(session, canonical_topic, canonical_source, "ext-a", content="review cũ")
        _make_prediction(session, analyzed, topic_label="lỗi ứng dụng")
        session.commit()

        new_topic = _make_topic(session, user, "New-account-same-bank")
        new_source = _make_source(session, new_topic, config={"query": "SHB Saha", "country": "vn", "lang": "vi"})
        session.commit()

        with (
            patch(
                "src.pipeline.collectors.google_play.GooglePlayCollector.resolve_identity",
                return_value={"package_name": package_name},
            ),
            patch(
                "src.pipeline.collectors.google_play.GooglePlayCollector.collect",
                autospec=True,
                return_value=[],
            ) as mock_collect,
            patch(
                "src.pipeline.collectors.app_store.AppStoreCollector.collect",
                autospec=True,
                return_value=[],
            ),
        ):
            from src.pipeline.runner import run_cycle

            run_cycle(session=session)

        # collect() (fetch review thật) chỉ được gọi cho source CANONICAL (package_name có sẵn từ
        # đầu) — KHÔNG được gọi cho source mới (đã nhận diện là follower ngay từ bước resolve).
        # autospec=True để mock giữ đúng chữ ký phương thức thật (bao gồm `self`), nếu không call
        # args sẽ không có self để kiểm tra collector nào đã thực sự gọi collect().
        calls_for_this_app = [
            call for call in mock_collect.call_args_list if call.args[0].config.get("package_name") == package_name
        ]
        assert len(calls_for_this_app) == 1
        assert "query" not in calls_for_this_app[0].args[0].config

        new_post = session.query(Post).filter_by(source_id=new_source.id, external_id="ext-a").one()
        assert new_post.content == "review cũ"
        pred = session.query(Prediction).filter_by(post_id=new_post.id).one()
        assert pred.topic_label == "lỗi ứng dụng"
    finally:
        session.close()


def test_run_analysis_cycle_excludes_follower_source_posts():
    """Post chưa phân tích của source follower KHÔNG được đưa vào hàng đợi LLM — kể cả khi
    canonical chưa kịp phân tích post tương ứng, follower vẫn phải đợi thay vì tự phân tích trùng."""
    session = sessionmaker(bind=_engine)()
    try:
        package_name = _unique_package_name()
        user = _make_user(session)
        canonical_topic = _make_topic(session, user, "Canonical-3")
        follower_topic = _make_topic(session, user, "Follower-3")
        canonical_source = _make_source(session, canonical_topic, config={"package_name": package_name})
        follower_source = _make_source(session, follower_topic, config={"package_name": package_name})

        _make_post(session, canonical_topic, canonical_source, "c-1", content="canonical chưa phân tích")
        follower_post = _make_post(session, follower_topic, follower_source, "f-1", content="follower chưa phân tích")
        session.commit()

        with (
            patch("src.analysis.graph.classify_post") as mock_classify,
            patch("src.analysis.runner.SessionLocal", sessionmaker(bind=_engine)),
        ):
            from src.analysis.runner import run_analysis_cycle

            run_analysis_cycle(topic_id=follower_topic.id)

        mock_classify.assert_not_called()
        assert session.query(Prediction).filter_by(post_id=follower_post.id).first() is None
    finally:
        session.close()
