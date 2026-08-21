"""Kiểm chứng đúng các mục trong "Cách test" của docs/phase0/0.2-erd-foreign-keys.md:
FK reject, UNIQUE reject (prediction 1-1, posts trùng source+external_id), cascade delete.

Cần một Postgres thật (không chạy được trên SQLite vì dùng JSONB + ON DELETE) — nếu không kết
nối được, cả module tự skip. Chạy `docker compose up -d db` trước khi chạy pytest.

Dùng DB riêng `TEST_DATABASE_URL` (mặc định: cùng host/user với DATABASE_URL nhưng đổi tên DB
thành "<tên>_test") thay vì DATABASE_URL của dev, vì module này tự tạo/xóa toàn bộ bảng
(`create_all`/`drop_all`) — nếu trỏ vào DB dev sẽ xóa mất dữ liệu đã seed/crawl thật.
`docker-compose.yml` đã tự tạo sẵn DB "painpoints_test" qua `docker/init-test-db.sql`.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.db.models import Base, Post, Prediction, Source, Topic, User


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
    reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test DB layer",
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
    user = User(email=f"{uuid.uuid4()}@test.local", password_hash="x")
    db_session.add(user)
    db_session.flush()
    return user


def _make_topic(db_session, user: User) -> Topic:
    topic = Topic(user_id=user.id, name="Test Topic", keywords=[])
    db_session.add(topic)
    db_session.flush()
    return topic


def test_post_rejects_unknown_topic_id(session):
    session.add(Post(topic_id=uuid.uuid4(), external_id="x", content="hi"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_prediction_post_id_rejected(session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    post = Post(topic_id=topic.id, external_id="p1", content="hi")
    session.add(post)
    session.flush()

    session.add(Prediction(post_id=post.id))
    session.flush()

    session.add(Prediction(post_id=post.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_source_external_id_rejected(session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    source = Source(topic_id=topic.id, type="google_play", config={})
    session.add(source)
    session.flush()

    session.add(Post(topic_id=topic.id, source_id=source.id, external_id="dup", content="a"))
    session.flush()

    session.add(Post(topic_id=topic.id, source_id=source.id, external_id="dup", content="b"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_cascade_delete_topic_removes_posts(session):
    user = _make_user(session)
    topic = _make_topic(session, user)
    session.add(Post(topic_id=topic.id, external_id="c1", content="a"))
    session.commit()

    topic_id = topic.id
    session.delete(topic)
    session.commit()

    remaining = session.query(Post).filter_by(topic_id=topic_id).all()
    assert remaining == []
