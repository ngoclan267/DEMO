"""GET/PATCH/DELETE /admin/users — chỉ platform admin gọi được, xem toàn bộ tài khoản + mức tiêu
thụ token/chi phí ước tính theo llm_usage."""

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
from src.db.models import Base, LLMUsage, Source, Topic, User
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


async def _register_and_login(api_client, *, is_platform_admin: bool = False) -> tuple[dict, str]:
    """Tạo User trực tiếp qua DB (tự đăng ký công khai đã gỡ, xem src/api/routes_auth.py) rồi đăng
    nhập. is_paid mặc định True/trial_ends_at=None (default ở User model, giống mọi tài khoản do
    admin/chủ sở hữu tạo hộ) — khác hành vi register() cũ (luôn ép is_paid=False); test nào cần mô
    phỏng tài khoản dùng thử thì tự set is_paid=False + trial_ends_at sau khi tạo."""
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(
            User(
                email=email,
                password_hash=hash_password("testpass123"),
                is_verified=True,
                is_platform_admin=is_platform_admin,
            )
        )
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, me.json()["id"]


@pytest.mark.asyncio
async def test_non_admin_gets_403(api_client):
    headers, _ = await _register_and_login(api_client)
    r = await api_client.get("/api/v1/admin/users", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_lists_users_with_usage(api_client):
    admin_headers, admin_id = await _register_and_login(api_client, is_platform_admin=True)
    _, other_id = await _register_and_login(api_client)

    session = sessionmaker(bind=_engine)()
    try:
        # is_paid=True/trial_ends_at=None là mặc định của _register_and_login() (KHÔNG bị áp trần
        # lượt gọi AI) — tách biệt với test_admin_shows_trial_analysis_call_limit_for_trial_accounts
        # ngay dưới đây, nơi tự set lại thành tài khoản dùng thử.
        topic = Topic(user_id=uuid.UUID(other_id), name="Test Bank", status="active")
        session.add(topic)
        session.flush()
        source = Source(topic_id=topic.id, type="google_play", config={})
        session.add(source)
        session.flush()
        session.add(
            LLMUsage(
                user_id=uuid.UUID(other_id),
                topic_id=topic.id,
                call_type="classification",
                model="gemma-4-26b-a4b-it",
                input_tokens=1000,
                output_tokens=200,
            )
        )
        session.add(
            LLMUsage(
                user_id=uuid.UUID(other_id),
                topic_id=topic.id,
                call_type="verification",
                model="gpt-4o-mini",
                input_tokens=2_000_000,
                output_tokens=0,
            )
        )
        session.commit()
    finally:
        session.close()

    r = await api_client.get("/api/v1/admin/users", headers=admin_headers)
    assert r.status_code == 200
    rows = {row["id"]: row for row in r.json()}
    assert admin_id in rows
    assert other_id in rows

    other_row = rows[other_id]
    assert other_row["topic_count"] == 1
    assert other_row["usage"]["total_input_tokens"] == 1000 + 2_000_000
    assert other_row["usage"]["call_count"] == 2
    # gemma-*: miễn phí ($0) + gpt-4o-mini: 2M input * $0.15/1M = $0.30
    assert other_row["usage"]["estimated_cost_usd"] == pytest.approx(0.30)
    assert other_row["usage"]["has_unpriced_usage"] is False
    # Đã set is_paid=True ở trên (không phải diện dùng thử) — không bị áp trần lượt gọi AI miễn phí.
    assert other_row["trial_analysis_call_limit"] is None


@pytest.mark.asyncio
async def test_admin_shows_trial_analysis_call_limit_for_trial_accounts(api_client):
    admin_headers, _ = await _register_and_login(api_client, is_platform_admin=True)
    _, trial_id = await _register_and_login(api_client)

    session = sessionmaker(bind=_engine)()
    try:
        session.query(User).filter(User.id == uuid.UUID(trial_id)).update(
            {"is_paid": False, "trial_ends_at": datetime.now(UTC) + timedelta(days=7)}
        )
        session.commit()
    finally:
        session.close()

    r = await api_client.get("/api/v1/admin/users", headers=admin_headers)
    assert r.status_code == 200
    row = {row["id"]: row for row in r.json()}[trial_id]
    assert row["trial_analysis_call_limit"] == get_settings().trial_analysis_call_limit

    detail = await api_client.get(f"/api/v1/admin/users/{trial_id}", headers=admin_headers)
    assert detail.json()["trial_analysis_call_limit"] == get_settings().trial_analysis_call_limit


@pytest.mark.asyncio
async def test_admin_views_user_detail_with_topics(api_client):
    admin_headers, _ = await _register_and_login(api_client, is_platform_admin=True)
    _, other_id = await _register_and_login(api_client)

    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(other_id), name="Detail Bank", status="active")
        session.add(topic)
        session.commit()
    finally:
        session.close()

    r = await api_client.get(f"/api/v1/admin/users/{other_id}", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["topics"]) == 1
    assert body["topics"][0]["name"] == "Detail Bank"


@pytest.mark.asyncio
async def test_admin_updates_user_is_paid(api_client):
    admin_headers, _ = await _register_and_login(api_client, is_platform_admin=True)
    _, other_id = await _register_and_login(api_client)

    r = await api_client.patch(f"/api/v1/admin/users/{other_id}", json={"is_paid": True}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_paid"] is True


@pytest.mark.asyncio
async def test_admin_cannot_revoke_own_admin_flag(api_client):
    admin_headers, admin_id = await _register_and_login(api_client, is_platform_admin=True)

    r = await api_client.patch(
        f"/api/v1/admin/users/{admin_id}", json={"is_platform_admin": False}, headers=admin_headers
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(api_client):
    admin_headers, admin_id = await _register_and_login(api_client, is_platform_admin=True)

    r = await api_client.delete(f"/api/v1/admin/users/{admin_id}", headers=admin_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_deletes_another_user_cascades_topics(api_client):
    admin_headers, _ = await _register_and_login(api_client, is_platform_admin=True)
    _, other_id = await _register_and_login(api_client)

    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(other_id), name="To Delete", status="active")
        session.add(topic)
        session.commit()
        topic_id = topic.id
    finally:
        session.close()

    r = await api_client.delete(f"/api/v1/admin/users/{other_id}", headers=admin_headers)
    assert r.status_code == 204

    session = sessionmaker(bind=_engine)()
    try:
        assert session.get(User, uuid.UUID(other_id)) is None
        assert session.get(Topic, topic_id) is None
    finally:
        session.close()
