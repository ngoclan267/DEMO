"""Bản tin tổng hợp hàng ngày (build_digest_message / run_daily_digest) — cần Postgres test thật
vì thao tác qua nhiều bảng có quan hệ FK thật (Topic/Post/Prediction/User), giống test_service.py."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.db.models import Base, Notification, Post, Prediction, Source, Topic, User
from src.notifications.digest import build_digest_message, run_daily_digest


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
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test digest"
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
        "name": "Test Bank Digest",
        "keywords": [],
        "alert_threshold": 10,
        "notify_enabled": True,
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


def _make_post(db_session, topic, source, *, posted_at, sentiment=None, topic_label=None, classified_at=None):
    post = Post(
        topic_id=topic.id,
        source_id=source.id,
        external_id=str(uuid.uuid4()),
        content="nội dung test",
        language="vi",
        posted_at=posted_at,
    )
    db_session.add(post)
    db_session.flush()
    if sentiment is not None or topic_label is not None:
        db_session.add(
            Prediction(
                post_id=post.id,
                sentiment=sentiment,
                topic_label=topic_label,
                severity_score=0.5,
                confidence_score=0.9,
                consensus_status="confirmed",
                # Mặc định = posted_at (giả lập "phân tích ngay khi đăng" — đúng ý mọi test khác
                # trong file dùng posted_at làm trục thời gian chính). Bản tin đếm theo
                # Prediction.classified_at (xem digest.py::_window_stats) — test riêng cho backlog
                # LLM (phân tích trễ nhiều ngày sau khi đăng/thu thập) tự truyền classified_at khác
                # posted_at.
                classified_at=classified_at if classified_at is not None else posted_at,
            )
        )
        db_session.flush()
    return post


# Mốc thời gian cố định cho mọi test build_digest_message — tránh phụ thuộc đồng hồ hệ thống lúc
# chạy test (build_digest_message nhận `now` làm tham số, không tự đọc datetime.now()).
NOW = datetime(2026, 8, 9, 7, 0, tzinfo=UTC)


@patch("src.notifications.service.send_email")
def test_no_digest_when_no_posts_in_last_24h(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    _make_source(session, topic)
    session.commit()

    assert build_digest_message(session, topic, NOW) is None


@patch("src.notifications.service.send_email")
def test_sentiment_trend_vs_7_days_ago(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    source = _make_source(session, topic)

    # Hôm nay: 4 post, 3 tiêu cực -> 75%.
    for i in range(3):
        _make_post(
            session, topic, source, posted_at=NOW - timedelta(hours=i + 1), sentiment="negative", topic_label="lỗi ứng dụng"
        )
    _make_post(session, topic, source, posted_at=NOW - timedelta(hours=4), sentiment="positive", topic_label="lỗi ứng dụng")

    # Đúng khung 24h của 7 ngày trước: 2 post, 1 tiêu cực -> 50%.
    week_ago_end = NOW - timedelta(days=7)
    _make_post(
        session, topic, source, posted_at=week_ago_end - timedelta(hours=1), sentiment="negative", topic_label="lỗi ứng dụng"
    )
    _make_post(
        session, topic, source, posted_at=week_ago_end - timedelta(hours=2), sentiment="positive", topic_label="lỗi ứng dụng"
    )
    session.commit()

    message = build_digest_message(session, topic, NOW)
    assert message is not None
    assert "4 phản hồi đã phân tích, 75% tiêu cực" in message
    assert "tăng 25 điểm % so với cùng khung giờ 7 ngày trước" in message


@patch("src.notifications.service.send_email")
def test_counts_posts_classified_today_regardless_of_when_posted(mock_send_email, session):
    """Bug thật đã xảy ra: quota LLM free-tier có hạn nên backlog phân tích có thể trễ nhiều ngày
    (xem DEFAULT_BATCH_LIMIT trong src/analysis/runner.py) — 1 post ĐĂNG/THU THẬP từ 10 ngày trước
    nhưng chỉ vừa được AI PHÂN TÍCH XONG hôm nay vẫn phải được tính vào bản tin hôm nay. Trước đây
    lọc theo posted_at/collected_at nên post dạng này bị bỏ sót, khiến bản tin báo số phản hồi/tiêu
    cực thấp hơn nhiều so với thực tế đã phân tích trong ngày."""
    user = _make_user(session)
    topic = _make_topic(session, user)
    source = _make_source(session, topic)

    _make_post(
        session,
        topic,
        source,
        posted_at=NOW - timedelta(days=10),
        classified_at=NOW - timedelta(hours=1),
        sentiment="negative",
        topic_label="lỗi ứng dụng",
    )
    session.commit()

    message = build_digest_message(session, topic, NOW)
    assert message is not None
    assert "1 phản hồi đã phân tích, 100% tiêu cực" in message


@patch("src.notifications.service.send_email")
def test_no_comparison_note_when_no_data_7_days_ago(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    source = _make_source(session, topic)
    _make_post(session, topic, source, posted_at=NOW - timedelta(hours=1), sentiment="negative", topic_label="lỗi ứng dụng")
    session.commit()

    message = build_digest_message(session, topic, NOW)
    assert message is not None
    assert "7 ngày trước không có dữ liệu để so sánh" in message


@patch("src.notifications.service.send_email")
def test_top_3_pain_points_ordered_by_new_count_today(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    source = _make_source(session, topic)

    counts = {"lỗi ứng dụng": 5, "phí dịch vụ": 3, "chuyển tiền chậm": 2, "giao diện xấu": 1}
    for label, n in counts.items():
        for i in range(n):
            _make_post(session, topic, source, posted_at=NOW - timedelta(hours=i + 1), sentiment="negative", topic_label=label)
    session.commit()

    message = build_digest_message(session, topic, NOW)
    assert message is not None
    assert message.index("lỗi ứng dụng") < message.index("phí dịch vụ") < message.index("chuyển tiền chậm")
    assert "giao diện xấu" not in message  # đứng thứ 4 -> bị loại khỏi Top 3


@patch("src.notifications.service.send_email")
def test_spike_alert_fires_only_when_prior_day_nonzero(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    source = _make_source(session, topic)

    # "lỗi ứng dụng": hôm qua 2, hôm nay 5 -> tăng 150% (>50%) -> phải cảnh báo.
    for i in range(2):
        _make_post(
            session,
            topic,
            source,
            posted_at=NOW - timedelta(hours=24 + i + 1),
            sentiment="negative",
            topic_label="lỗi ứng dụng",
        )
    for i in range(5):
        _make_post(session, topic, source, posted_at=NOW - timedelta(hours=i + 1), sentiment="negative", topic_label="lỗi ứng dụng")

    # "case mới": hôm qua 0, hôm nay 4 -> KHÔNG cảnh báo (tránh chia 0; case hoàn toàn mới đã nằm
    # trong Top 3 rồi, không cần cảnh báo trùng).
    for i in range(4):
        _make_post(session, topic, source, posted_at=NOW - timedelta(hours=i + 1), sentiment="negative", topic_label="case mới")
    session.commit()

    message = build_digest_message(session, topic, NOW)
    assert message is not None
    assert "Cảnh báo tăng đột biến" in message
    assert '"lỗi ứng dụng" tăng' in message
    assert '"case mới" tăng' not in message


@patch("src.notifications.service.send_email")
def test_run_daily_digest_respects_notify_enabled(mock_send_email, session):
    user = _make_user(session)
    enabled_topic = _make_topic(session, user, name=f"Enabled {uuid.uuid4()}")
    disabled_topic = _make_topic(session, user, name=f"Disabled {uuid.uuid4()}", notify_enabled=False)
    source_enabled = _make_source(session, enabled_topic)
    source_disabled = _make_source(session, disabled_topic)
    now = datetime.now(UTC)
    _make_post(session, enabled_topic, source_enabled, posted_at=now - timedelta(hours=1), sentiment="negative", topic_label="lỗi ứng dụng")
    _make_post(session, disabled_topic, source_disabled, posted_at=now - timedelta(hours=1), sentiment="negative", topic_label="lỗi ứng dụng")
    session.commit()

    # run_daily_digest quét TOÀN BỘ topic active trong DB test (không lọc theo user) — chỉ kiểm
    # tra kết quả cho đúng 2 topic vừa tạo, không dựa vào tổng số trả về (DB test dùng chung giữa
    # các test trong module, có thể có topic khác từ test khác).
    run_daily_digest(session)

    notifications = (
        session.query(Notification)
        .filter(Notification.topic_id.in_([enabled_topic.id, disabled_topic.id]))
        .all()
    )
    assert len(notifications) == 1
    assert notifications[0].topic_id == enabled_topic.id
    assert notifications[0].notification_type == "daily_digest"
    assert notifications[0].pain_point_id is None


@patch("src.notifications.service.send_email")
def test_run_daily_digest_skips_topic_with_recent_digest(mock_send_email, session):
    """Sửa lỗi thực tế: scheduler.py cho job này chạy thêm 1 lần ngay lúc khởi động (bắt kịp
    trường hợp container restart trước khi qua mốc cron 7:00) — không được gửi trùng bản tin nếu
    container restart nhiều lần trong cùng 1 ngày (xem DIGEST_COOLDOWN_HOURS)."""
    user = _make_user(session)
    topic = _make_topic(session, user, name=f"Recent {uuid.uuid4()}")
    source = _make_source(session, topic)
    now = datetime.now(UTC)
    _make_post(session, topic, source, posted_at=now - timedelta(hours=1), sentiment="negative", topic_label="lỗi ứng dụng")
    session.add(
        Notification(
            user_id=user.id,
            topic_id=topic.id,
            notification_type="daily_digest",
            channel="web",
            message="bản tin cũ",
            sent_at=now - timedelta(hours=2),
        )
    )
    session.commit()

    created = run_daily_digest(session)

    notifications = session.query(Notification).filter(Notification.topic_id == topic.id).all()
    assert len(notifications) == 1  # vẫn chỉ có bản tin cũ, không tạo thêm
    assert created == 0


@patch("src.notifications.service.send_email")
def test_run_daily_digest_sends_again_after_cooldown_expires(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, name=f"Stale {uuid.uuid4()}")
    source = _make_source(session, topic)
    now = datetime.now(UTC)
    _make_post(session, topic, source, posted_at=now - timedelta(hours=1), sentiment="negative", topic_label="lỗi ứng dụng")
    session.add(
        Notification(
            user_id=user.id,
            topic_id=topic.id,
            notification_type="daily_digest",
            channel="web",
            message="bản tin hôm qua",
            sent_at=now - timedelta(hours=25),
        )
    )
    session.commit()

    run_daily_digest(session)

    notifications = session.query(Notification).filter(Notification.topic_id == topic.id).all()
    assert len(notifications) == 2
