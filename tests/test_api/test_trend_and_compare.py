"""GET /pain-points/{id}/trend chỉ tính đúng post khớp topic_label của pain point đó (không lẫn
pain point khác cùng topic); GET /topics/{id}/compare-periods trả đúng số liệu từng giai đoạn và
404 khi topic không thuộc quyền truy cập của user hiện tại (thay cho GET /topics/compare topic-với-
topic cũ đã gỡ — mỗi ngân hàng giờ là 1 workspace riêng biệt, xem src/api/routes_dashboard.py)."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.security import hash_password
from src.config import get_settings
from src.db.models import Base, PainPoint, Post, Prediction, Source, Topic, User
from src.db.session import get_db
from src.logging_config import VN_TZ
from src.main import app


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
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test API"
)


@pytest.fixture(scope="module", autouse=True)
def _setup_tables():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture(autouse=True)
def _override_get_db():
    session_factory = sessionmaker(bind=_engine)

    def _get_test_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _registered_headers(api_client) -> tuple[dict, str]:
    """Trả về (headers, user_id) — cần user_id để seed dữ liệu ĐÚNG dưới user đó (bài học từ
    test_post_filters.py: seed lệch user_id khiến get_accessible_topic 404 nhầm). Tạo User trực
    tiếp qua DB (tự đăng ký công khai đã gỡ, xem src/api/routes_auth.py) thay vì qua
    POST /auth/register."""
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(User(email=email, password_hash=hash_password("testpass123"), is_verified=True))
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, me.json()["id"]


def _seed_post(session, topic, source, content, days_ago, sentiment, topic_label):
    now = datetime.now(UTC)
    post = Post(
        topic_id=topic.id,
        source_id=source.id,
        external_id=str(uuid.uuid4()),
        content=content,
        language="vi",
        posted_at=now - timedelta(days=days_ago),
    )
    session.add(post)
    session.flush()
    session.add(
        Prediction(
            post_id=post.id,
            sentiment=sentiment,
            topic_label=topic_label,
            severity_score=0.5,
            confidence_score=0.9,
            consensus_status="confirmed",
        )
    )
    return post


@pytest_asyncio.fixture
async def two_pain_points_same_topic(api_client):
    """1 topic, 2 pain point khác title, mỗi pain point có post riêng — dùng để kiểm tra trend
    không bị lẫn giữa 2 pain point cùng topic."""
    headers, owner_id = await _registered_headers(api_client)
    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(owner_id), name="Test Bank Trend", status="active")
        session.add(topic)
        session.flush()
        source = Source(topic_id=topic.id, type="google_play", config={})
        session.add(source)
        session.flush()

        p_a1 = _seed_post(session, topic, source, "app crash liên tục", 1, "negative", "lỗi ứng dụng")
        p_a2 = _seed_post(session, topic, source, "app crash khi mở", 2, "negative", "lỗi ứng dụng")
        p_b1 = _seed_post(session, topic, source, "phí giao dịch cao", 1, "negative", "phí dịch vụ")

        pp_a = PainPoint(topic_id=topic.id, title="lỗi ứng dụng", post_count=2, severity_avg=0.5)
        pp_b = PainPoint(topic_id=topic.id, title="phí dịch vụ", post_count=1, severity_avg=0.5)
        session.add_all([pp_a, pp_b])
        session.commit()

        return {
            "headers": headers,
            "pain_point_a_id": str(pp_a.id),
            "pain_point_b_id": str(pp_b.id),
            "p_a1": str(p_a1.id),
            "p_a2": str(p_a2.id),
            "p_b1": str(p_b1.id),
        }
    finally:
        session.close()


@pytest.mark.asyncio
async def test_pain_point_trend_only_counts_matching_topic_label(api_client, two_pain_points_same_topic):
    headers = two_pain_points_same_topic["headers"]
    r = await api_client.get(
        f"/api/v1/pain-points/{two_pain_points_same_topic['pain_point_a_id']}/trend", headers=headers
    )
    assert r.status_code == 200
    points = r.json()
    # 2 post của pain point A trải trên 2 ngày khác nhau -> tổng count qua các ngày phải là 2,
    # không lẫn post của pain point B (phí dịch vụ).
    assert sum(p["count"] for p in points) == 2

    r = await api_client.get(
        f"/api/v1/pain-points/{two_pain_points_same_topic['pain_point_b_id']}/trend", headers=headers
    )
    points_b = r.json()
    assert sum(p["count"] for p in points_b) == 1


@pytest.mark.asyncio
async def test_pain_point_trend_404_for_inaccessible_pain_point(api_client, two_pain_points_same_topic):
    other_headers, _ = await _registered_headers(api_client)
    r = await api_client.get(
        f"/api/v1/pain-points/{two_pain_points_same_topic['pain_point_a_id']}/trend", headers=other_headers
    )
    assert r.status_code == 404


def _vn_date(days_ago: int):
    """Ngày dương lịch giờ Việt Nam N ngày trước — dùng để tính period_*_from/to khớp đúng cách
    quy đổi biên ngày của compare_periods() (xem src/api/routes_dashboard.py::_period_stats)."""
    return (datetime.now(VN_TZ) - timedelta(days=days_ago)).date()


@pytest_asyncio.fixture
async def topic_with_two_periods(api_client):
    """1 topic, post trải 2 giai đoạn CÁCH XA nhau (không liền kề, tránh flaky do giờ chạy test sát
    ranh giới ngày): giai đoạn A ~9-8 ngày trước, giai đoạn B ~1-0 ngày trước (bao gồm hôm nay, để
    PainPoint tạo lúc chạy test — created_at=now — chắc chắn rơi vào giai đoạn B)."""
    headers, owner_id = await _registered_headers(api_client)
    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(owner_id), name="TPBank Mobile Test", status="active")
        session.add(topic)
        session.flush()
        source = Source(topic_id=topic.id, type="google_play", config={})
        session.add(source)
        session.flush()

        # Giai đoạn A: 2 post tiêu cực cùng nhóm "lỗi ứng dụng".
        _seed_post(session, topic, source, "app crash A1", 9, "negative", "lỗi ứng dụng")
        _seed_post(session, topic, source, "app crash A2", 8, "negative", "lỗi ứng dụng")
        # Giai đoạn B: 1 tiêu cực nhóm khác + 1 tích cực.
        _seed_post(session, topic, source, "phí cao B1", 1, "negative", "phí dịch vụ")
        _seed_post(session, topic, source, "app tốt B2", 0, "positive", "trải nghiệm sử dụng")

        # Pain point tạo NGAY (created_at mặc định = lúc insert) — rơi vào giai đoạn B.
        session.add(PainPoint(topic_id=topic.id, title="phí dịch vụ", post_count=1, severity_avg=0.5))
        session.commit()

        return {
            "headers": headers,
            "topic_id": str(topic.id),
            "period_a_from": _vn_date(11),
            "period_a_to": _vn_date(7),
            "period_b_from": _vn_date(3),
            "period_b_to": _vn_date(0),
        }
    finally:
        session.close()


def _compare_periods_url(topic_id: str, data: dict) -> str:
    return (
        f"/api/v1/topics/{topic_id}/compare-periods"
        f"?period_a_from={data['period_a_from']}&period_a_to={data['period_a_to']}"
        f"&period_b_from={data['period_b_from']}&period_b_to={data['period_b_to']}"
    )


@pytest.mark.asyncio
async def test_compare_periods_returns_stats_per_period(api_client, topic_with_two_periods):
    d = topic_with_two_periods
    r = await api_client.get(_compare_periods_url(d["topic_id"], d), headers=d["headers"])
    assert r.status_code == 200
    body = r.json()

    period_a = body["period_a"]
    assert period_a["post_count"] == 2
    assert period_a["sentiment_breakdown"] == {"negative": 2}
    assert period_a["negative_by_group"] == {"lỗi ứng dụng": 2}
    assert period_a["pain_point_count"] == 0
    # 2 post ở 2 ngày khác nhau (9 và 8 ngày trước) -> 2 điểm trend, mỗi điểm 1 post, tổng khớp
    # post_count — phục vụ biểu đồ đường so 2 giai đoạn ở frontend (PeriodTrendChart.tsx).
    assert sum(p["count"] for p in period_a["trend"]) == 2
    assert all(p["count"] == 1 and p["negative_count"] == 1 and p["positive_count"] == 0 for p in period_a["trend"])

    period_b = body["period_b"]
    assert period_b["post_count"] == 2
    assert period_b["sentiment_breakdown"] == {"negative": 1, "positive": 1}
    assert period_b["negative_by_group"] == {"phí dịch vụ": 1}
    assert period_b["pain_point_count"] == 1
    assert sum(p["count"] for p in period_b["trend"]) == 2
    assert sum(p["negative_count"] for p in period_b["trend"]) == 1
    assert sum(p["positive_count"] for p in period_b["trend"]) == 1


@pytest.mark.asyncio
async def test_compare_periods_404_when_topic_not_accessible(api_client, topic_with_two_periods):
    """Kiểm soát truy cập, không chỉ happy path — user khác không sở hữu/được mời topic thì bị chặn."""
    other_headers, _ = await _registered_headers(api_client)
    d = topic_with_two_periods
    r = await api_client.get(_compare_periods_url(d["topic_id"], d), headers=other_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_compare_periods_requires_all_four_dates(api_client, topic_with_two_periods):
    d = topic_with_two_periods
    r = await api_client.get(
        f"/api/v1/topics/{d['topic_id']}/compare-periods"
        f"?period_a_from={d['period_a_from']}&period_a_to={d['period_a_to']}",
        headers=d["headers"],
    )
    assert r.status_code == 422
