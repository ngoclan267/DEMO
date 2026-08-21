"""Cần Postgres test thật (giống tests/test_db/test_models.py) vì check_and_notify thao tác trực
tiếp với User/Topic/PainPoint/Notification qua quan hệ FK thật (topic.user, pain_point.topic)."""

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.db.models import Base, PainPoint, Topic, User
from src.notifications.service import check_and_notify


def _default_test_db_url() -> str:
    base = get_settings().database_url
    root, sep, dbname = base.rpartition("/")
    if not sep:
        return base
    return f"{root}/{dbname}_test"


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
    _engine is None,
    reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test notification service",
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
        "name": "Test Topic",
        "keywords": [],
        "alert_threshold": 10,
        "notify_enabled": True,
        "notify_channel": "both",
    }
    defaults.update(overrides)
    topic = Topic(**defaults)
    db_session.add(topic)
    db_session.flush()
    return topic


def _make_pain_point(db_session, topic, **overrides) -> PainPoint:
    defaults = {"topic_id": topic.id, "title": "lỗi ứng dụng", "post_count": 10, "reference_status": "no_match"}
    defaults.update(overrides)
    pain_point = PainPoint(**defaults)
    db_session.add(pain_point)
    db_session.flush()
    return pain_point


@patch("src.notifications.service.send_email")
def test_notifies_when_threshold_crossed(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10)
    pain_point = _make_pain_point(session, topic, post_count=10)

    notification = check_and_notify(session, pain_point)

    assert notification is not None
    assert notification.channel == "both"
    mock_send_email.assert_called_once()
    assert pain_point.last_notified_post_count == 10


@patch("src.notifications.service.send_email")
def test_no_notification_below_threshold(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10)
    pain_point = _make_pain_point(session, topic, post_count=5)

    notification = check_and_notify(session, pain_point)

    assert notification is None
    mock_send_email.assert_not_called()


@patch("src.notifications.service.send_email")
def test_no_duplicate_notification_same_post_count(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10)
    pain_point = _make_pain_point(session, topic, post_count=10, last_notified_post_count=10)

    notification = check_and_notify(session, pain_point)

    assert notification is None
    mock_send_email.assert_not_called()


@patch("src.notifications.service.send_email")
def test_no_renotify_before_post_count_doubles(mock_send_email, session):
    """Sau lần báo ở post_count=10, tăng lên 15 (chưa gấp đôi) không được báo lại — tránh báo dồn
    dập mỗi khi có thêm 1 review."""
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10)
    pain_point = _make_pain_point(session, topic, post_count=15, last_notified_post_count=10)

    notification = check_and_notify(session, pain_point)

    assert notification is None
    mock_send_email.assert_not_called()


@patch("src.notifications.service.send_email")
def test_renotifies_when_post_count_doubles(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10)
    pain_point = _make_pain_point(session, topic, post_count=20, last_notified_post_count=10)

    notification = check_and_notify(session, pain_point)

    assert notification is not None
    assert pain_point.last_notified_post_count == 20


@patch("src.notifications.service.send_email")
def test_respects_notify_enabled_false(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10, notify_enabled=False)
    pain_point = _make_pain_point(session, topic, post_count=15)

    notification = check_and_notify(session, pain_point)

    assert notification is None
    mock_send_email.assert_not_called()


@patch("src.notifications.service.send_email")
def test_web_only_channel_does_not_send_email(mock_send_email, session):
    user = _make_user(session)
    topic = _make_topic(session, user, alert_threshold=10, notify_channel="web")
    pain_point = _make_pain_point(session, topic, post_count=15)

    notification = check_and_notify(session, pain_point)

    assert notification is not None
    assert notification.channel == "web"
    mock_send_email.assert_not_called()
