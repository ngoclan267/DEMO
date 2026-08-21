"""POST /topics/admin — quản trị TỔNG nền tảng tạo topic thay doanh nghiệp khác, kèm tạo tài
khoản chủ sở hữu cho họ. Trọng tâm: kiểm soát truy cập (chỉ platform admin) + owner đúng người
được chỉ định (không phải admin) + không tạo trùng user khi owner_email đã tồn tại."""

import os
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.security import hash_password
from src.config import get_settings
from src.db.models import Base, User
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


@pytest.fixture(autouse=True)
def _no_real_email():
    with patch("src.api.routes_auth.send_email"), patch("src.api.routes_topics.send_email"):
        yield


@pytest_asyncio.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _new_user_headers(api_client, *, platform_admin: bool = False) -> dict:
    """Tạo User trực tiếp qua DB (tự đăng ký công khai đã gỡ, xem src/api/routes_auth.py) rồi đăng
    nhập."""
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(
            User(
                email=email,
                password_hash=hash_password("testpass123"),
                is_verified=True,
                is_platform_admin=platform_admin,
            )
        )
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get_user_by_email(email: str) -> User | None:
    session = sessionmaker(bind=_engine)()
    try:
        return session.query(User).filter(User.email == email).first()
    finally:
        session.close()


@pytest.mark.asyncio
async def test_regular_user_cannot_create_admin_topic(api_client):
    headers = await _new_user_headers(api_client, platform_admin=False)
    r = await api_client.post(
        "/api/v1/topics/admin",
        json={"name": "Ngân hàng ABC", "owner_email": f"{uuid.uuid4()}@example.com"},
        headers=headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_creates_trial_topic_and_owner_sets_password_via_email_link(api_client):
    admin_headers = await _new_user_headers(api_client, platform_admin=True)
    owner_email = f"{uuid.uuid4()}@example.com"

    r = await api_client.post(
        "/api/v1/topics/admin",
        json={
            "name": "Ngân hàng ABC",
            "keywords": ["ABC Bank"],
            "owner_email": owner_email,
            "owner_full_name": "Chủ sở hữu ABC",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Ngân hàng ABC"
    # is_owner tính theo NGƯỜI GỌI (admin) — admin không sở hữu topic này.
    assert body["is_owner"] is False

    owner = _get_user_by_email(owner_email)
    assert owner is not None
    assert owner.is_verified is True
    # Mặc định "trial" — không thanh toán, có hạn dùng thử.
    assert owner.is_paid is False
    assert owner.trial_ends_at is not None
    # Không nhận mật khẩu từ admin — thay vào đó có link đặt mật khẩu (reset_token), tái dùng đúng
    # cơ chế forgot-password sẵn có.
    assert owner.reset_token is not None

    # Chưa đặt mật khẩu thì chưa đăng nhập được (không có mật khẩu nào để đoán).
    reset_r = await api_client.post(
        "/api/v1/auth/reset-password", json={"token": owner.reset_token, "new_password": "ownernewpass123"}
    )
    assert reset_r.status_code == 204

    login_r = await api_client.post(
        "/api/v1/auth/login", json={"identifier": owner_email, "password": "ownernewpass123"}
    )
    assert login_r.status_code == 200
    owner_headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}
    topics_r = await api_client.get("/api/v1/topics", headers=owner_headers)
    names = [t["name"] for t in topics_r.json()]
    assert names == ["Ngân hàng ABC"]


@pytest.mark.asyncio
async def test_platform_admin_can_create_paid_topic_without_trial_limit(api_client):
    admin_headers = await _new_user_headers(api_client, platform_admin=True)
    owner_email = f"{uuid.uuid4()}@example.com"

    r = await api_client.post(
        "/api/v1/topics/admin",
        json={"name": "Ngân hàng Paid", "owner_email": owner_email, "plan": "paid"},
        headers=admin_headers,
    )
    assert r.status_code == 201

    owner = _get_user_by_email(owner_email)
    assert owner.is_paid is True
    assert owner.trial_ends_at is None


@pytest.mark.asyncio
async def test_admin_reuses_existing_owner_account_without_creating_duplicate(api_client):
    admin_headers = await _new_user_headers(api_client, platform_admin=True)
    existing_headers = await _new_user_headers(api_client, platform_admin=False)
    me = await api_client.get("/api/v1/auth/me", headers=existing_headers)
    existing_email = me.json()["email"]

    # Trạng thái thanh toán TRƯỚC khi admin tạo topic — ghi lại đây thay vì hardcode để test không
    # phụ thuộc giá trị mặc định cụ thể của _new_user_headers() là gì.
    existing_user_before = _get_user_by_email(existing_email)
    is_paid_before = existing_user_before.is_paid
    trial_ends_at_before = existing_user_before.trial_ends_at

    r = await api_client.post(
        "/api/v1/topics/admin",
        json={"name": "Ngân hàng XYZ", "owner_email": existing_email},
        headers=admin_headers,
    )
    assert r.status_code == 201

    # Mật khẩu CŨ của user vẫn còn dùng được — xác nhận không bị ghi đè/không gửi lại link đặt mật
    # khẩu mới cho user đã có sẵn.
    login_r = await api_client.post(
        "/api/v1/auth/login", json={"identifier": existing_email, "password": "testpass123"}
    )
    assert login_r.status_code == 200

    # Trạng thái thanh toán của user đã tồn tại KHÔNG bị đổi dù payload không truyền plan (mặc định
    # "trial" chỉ áp dụng cho user MỚI được tạo trong chính lệnh gọi này, không áp lên user có sẵn).
    existing_user = _get_user_by_email(existing_email)
    assert existing_user.is_paid == is_paid_before
    assert existing_user.trial_ends_at == trial_ends_at_before

    # Chỉ có đúng 1 user với email này — không tạo trùng.
    session = sessionmaker(bind=_engine)()
    try:
        count = session.query(User).filter(User.email == existing_email).count()
        assert count == 1
    finally:
        session.close()
