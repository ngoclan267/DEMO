"""run_analysis_cycle: thứ tự chọn post để phân tích — dữ liệu MỚI (theo ngày) phải luôn được xét
trước dữ liệu cũ hơn, bất kể priority_score (heuristic độ nghiêm trọng) cao thấp ra sao. Hết post
của ngày gần nhất mới "rơi" xuống ngày cũ hơn kế tiếp (xem order_columns trong
src/analysis/runner.py)."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analysis.runner import _PostOutcome, run_analysis_cycle
from src.config import get_settings
from src.db.models import Base, Post, Source, Topic, User


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


def _session():
    return sessionmaker(bind=_engine)()


def test_new_data_is_analyzed_before_older_data_regardless_of_priority_score():
    session = _session()
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

        now = datetime.now(UTC)
        old_day = now - timedelta(days=5)

        def _make_post(*, posted_at, priority_score, label) -> uuid.UUID:
            post = Post(
                topic_id=topic.id,
                source_id=source.id,
                external_id=str(uuid.uuid4()),
                content=f"review {label}",
                language="vi",
                posted_at=posted_at,
                priority_score=priority_score,
            )
            session.add(post)
            session.flush()
            return post.id

        # Cũ + priority_score CAO (nếu thứ tự cũ còn hiệu lực thì post này sẽ đứng ĐẦU — chính là
        # hành vi SAI cần sửa).
        old_high = _make_post(posted_at=old_day, priority_score=0.9, label="old_high")
        # Cũ + priority_score THẤP.
        old_low = _make_post(posted_at=old_day, priority_score=0.1, label="old_low")
        # Mới + priority_score THẤP — vẫn phải đứng TRƯỚC cả 2 post cũ ở trên dù priority_score thấp
        # hơn hẳn old_high — đây là hành vi ĐÚNG cần xác nhận.
        new_low = _make_post(posted_at=now, priority_score=0.1, label="new_low")
        # Mới + priority_score CAO — đứng đầu tuyệt đối (mới nhất VÀ ưu tiên cao nhất trong ngày).
        new_high = _make_post(posted_at=now, priority_score=0.9, label="new_high")

        session.commit()
        topic_id = topic.id
    finally:
        session.close()

    call_order: list[uuid.UUID] = []

    def _fake_analyze(post_id, post_topic_id, content):
        call_order.append(post_id)
        return _PostOutcome(success=True, consensus_status="confirmed")

    with (
        patch("src.analysis.runner._analyze_post_standalone", side_effect=_fake_analyze),
        patch("src.analysis.runner.SessionLocal", sessionmaker(bind=_engine)),
    ):
        run_analysis_cycle(limit=10, concurrency=1, topic_id=topic_id)

    assert call_order == [new_high, new_low, old_high, old_low]
