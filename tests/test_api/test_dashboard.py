"""GET /topics/{id}/dashboard — lọc toàn bộ thống kê theo source_type (xem _filter_by_source trong
src/api/routes_dashboard.py), phục vụ nút chọn nguồn trên biểu đồ xu hướng ở frontend."""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.security import hash_password
from src.config import get_settings
from src.db.models import Base, OfficialDocument, Post, Prediction, Source, Topic, User
from src.db.session import get_db
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


def _session():
    return sessionmaker(bind=_engine)()


async def _register_and_login(api_client) -> tuple[dict, str]:
    """Tạo User trực tiếp qua DB (tự đăng ký công khai đã gỡ, xem src/api/routes_auth.py) rồi đăng
    nhập, trả (headers, user_id)."""
    email = f"{uuid.uuid4()}@example.com"
    session = _session()
    try:
        session.add(User(email=email, password_hash=hash_password("testpass123"), is_verified=True))
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, me.json()["id"]


def _seed_topic_with_two_sources(owner_id: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """3 post negative: 2 từ Google Play, 1 từ App Store — trả về (topic_id, google_play_source_id,
    app_store_source_id) để test so khớp đúng số lượng lọc theo từng nguồn."""
    session = _session()
    try:
        topic = Topic(user_id=uuid.UUID(owner_id), name="Test Bank", status="active")
        session.add(topic)
        session.flush()

        gp_source = Source(topic_id=topic.id, type="google_play", config={})
        as_source = Source(topic_id=topic.id, type="app_store", config={})
        session.add_all([gp_source, as_source])
        session.flush()

        for i in range(2):
            post = Post(topic_id=topic.id, source_id=gp_source.id, content=f"gp review {i}")
            session.add(post)
            session.flush()
            session.add(Prediction(post_id=post.id, sentiment="negative", topic_label="lỗi ứng dụng", severity_score=0.5))

        post = Post(topic_id=topic.id, source_id=as_source.id, content="as review")
        session.add(post)
        session.flush()
        session.add(Prediction(post_id=post.id, sentiment="negative", topic_label="lỗi ứng dụng", severity_score=0.5))

        session.commit()
        return topic.id, gp_source.id, as_source.id
    finally:
        session.close()


@pytest.mark.asyncio
async def test_dashboard_without_filter_counts_all_sources(api_client):
    headers, owner_id = await _register_and_login(api_client)
    topic_id, _, _ = _seed_topic_with_two_sources(owner_id)

    r = await api_client.get(f"/api/v1/topics/{topic_id}/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_posts_count"] == 3
    assert body["negative_posts_count"] == 3
    # source_breakdown LUÔN đủ mọi nguồn (kể cả khi lọc) — dùng để hiển thị đủ nút chọn nguồn.
    assert body["source_breakdown"] == {"google_play": 2, "app_store": 1}


@pytest.mark.asyncio
async def test_dashboard_filters_stats_by_source_type(api_client):
    headers, owner_id = await _register_and_login(api_client)
    topic_id, _, _ = _seed_topic_with_two_sources(owner_id)

    r = await api_client.get(f"/api/v1/topics/{topic_id}/dashboard?source_type=google_play", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_posts_count"] == 2
    assert body["negative_posts_count"] == 2
    assert body["sentiment_breakdown"] == {"negative": 2}
    # source_breakdown vẫn đủ cả 2 nguồn dù đang lọc theo google_play — xem docstring _filter_by_source.
    assert body["source_breakdown"] == {"google_play": 2, "app_store": 1}


@pytest.mark.asyncio
async def test_dashboard_filter_matching_no_posts_returns_zero(api_client):
    headers, owner_id = await _register_and_login(api_client)
    topic_id, _, _ = _seed_topic_with_two_sources(owner_id)

    r = await api_client.get(f"/api/v1/topics/{topic_id}/dashboard?source_type=linkedin", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_posts_count"] == 0
    assert body["negative_posts_count"] == 0


@pytest.mark.asyncio
async def test_dashboard_trend_not_corrupted_by_official_documents(api_client):
    """Bug hồi quy: vòng lặp cộng dồn source_breakdown từ official_documents từng dùng biến tên
    "source_type" TRÙNG với tham số lọc của cả hàm get_dashboard — vòng lặp chạy xong thì biến
    source_type bị GHI ĐÈ thành giá trị Source.type cuối cùng duyệt qua thay vì giữ nguyên None
    (không lọc), khiến mọi query TÍNH SAU đó (sentiment_breakdown/negative_by_group/trend) bị lọc
    NHẦM theo 1 nguồn ngẫu nhiên. Bug này VÔ HÌNH nếu topic không có OfficialDocument nào (vòng lặp
    rỗng, không có gì để ghi đè) — 2 test phía trên không seed OfficialDocument nên không bắt được,
    đây là lý do cần 1 test RIÊNG có seed OfficialDocument để lộ đúng bug."""
    headers, owner_id = await _register_and_login(api_client)
    topic_id, gp_source_id, _ = _seed_topic_with_two_sources(owner_id)

    session = _session()
    try:
        bank_source = Source(topic_id=topic_id, type="bank_website", config={})
        session.add(bank_source)
        session.flush()
        session.add(
            OfficialDocument(
                topic_id=topic_id,
                source_id=bank_source.id,
                category="notice",
                title="Thông báo bảo trì",
                url="https://example.com/notice",
            )
        )
        session.commit()
    finally:
        session.close()

    r = await api_client.get(f"/api/v1/topics/{topic_id}/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    # Không lọc gì cả -> trend/sentiment_breakdown PHẢI tính trên toàn bộ 3 post (2 google_play + 1
    # app_store), KHÔNG bị lọc nhầm còn lại đúng 1 nguồn do biến source_type bị ghi đè.
    assert body["sentiment_breakdown"] == {"negative": 3}
    assert sum(p["count"] for p in body["trend"]) == 3
    assert body["source_breakdown"]["bank_website"] == 1
