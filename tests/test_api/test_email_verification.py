"""Xác thực email — chặn đăng nhập, resend, token dùng 1 lần.

Tự đăng ký công khai đã gỡ (xem src/api/routes_auth.py — tài khoản giờ luôn do platform admin/chủ
sở hữu chủ đề tạo hộ, is_verified=True ngay từ đầu), nhưng verify-email/resend-verification vẫn
giữ lại cho các tài khoản tự đăng ký TỪ TRƯỚC còn dang dở xác thực. `_create_unverified_user()` mô
phỏng đúng trạng thái đó (tạo User is_verified=False + verification_token hợp lệ qua DB) thay vì đi
qua endpoint đăng ký đã gỡ.
"""

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
    """SMTP thật đã cấu hình (Gmail) — không để test tự động gửi email thật tới các địa chỉ
    @example.com giả mỗi lần chạy. Patch tại nơi SỬ DỤNG (routes_auth), không phải nơi định nghĩa
    (notifications.email), vì `from x import y` tạo binding độc lập."""
    with patch("src.api.routes_auth.send_email") as mock:
        yield mock


@pytest_asyncio.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _get_user(email: str) -> User:
    session = sessionmaker(bind=_engine)()
    try:
        return session.query(User).filter(User.email == email).first()
    finally:
        session.close()


def _create_unverified_user(email: str) -> None:
    """Mô phỏng 1 tài khoản tự đăng ký TỪ TRƯỚC còn dang dở xác thực — gọi thẳng
    _send_verification_email() (helper nội bộ routes_auth.py, vẫn dùng lại y hệt luồng cũ) để có
    verification_token hợp lệ, thay vì qua POST /auth/register đã gỡ."""
    from src.api.routes_auth import _send_verification_email

    session = sessionmaker(bind=_engine)()
    try:
        user = User(email=email, password_hash=hash_password("testpass123"), is_verified=False)
        session.add(user)
        session.commit()
        _send_verification_email(user, session)
    finally:
        session.close()


@pytest.mark.asyncio
async def test_login_blocked_until_verified(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _create_unverified_user(email)

    r = await api_client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 403
    # Không lộ chi tiết nội bộ — chỉ cần message giải thích được lý do cho người dùng thật.
    assert "xác thực" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_email_with_bogus_token_returns_400(api_client):
    r = await api_client.post("/api/v1/auth/verify-email", json={"token": "khong-ton-tai"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_token_is_single_use(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _create_unverified_user(email)
    token = _get_user(email).verification_token

    r1 = await api_client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r1.status_code == 200

    # Token đã bị xoá sau khi dùng — dùng lại phải thất bại, không được xác thực "miễn phí" lần nữa.
    r2 = await api_client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_expired_token_rejected(api_client):
    from datetime import UTC, datetime, timedelta

    email = f"{uuid.uuid4()}@example.com"
    _create_unverified_user(email)

    session = sessionmaker(bind=_engine)()
    try:
        user = session.query(User).filter(User.email == email).first()
        token = user.verification_token
        user.verification_token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    finally:
        session.close()

    r = await api_client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_silent_for_unknown_email(api_client):
    """Không tiết lộ email có tồn tại trong hệ thống hay không — cùng nguyên tắc forgot-password."""
    r = await api_client.post("/api/v1/auth/resend-verification", json={"identifier": "khong-ai@example.com"})
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_resend_verification_silent_when_already_verified(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _create_unverified_user(email)
    token = _get_user(email).verification_token
    await api_client.post("/api/v1/auth/verify-email", json={"token": token})

    r = await api_client.post("/api/v1/auth/resend-verification", json={"identifier": email})
    assert r.status_code == 204
    # Không sinh token mới cho tài khoản đã xác thực rồi.
    assert _get_user(email).verification_token is None


@pytest.mark.asyncio
async def test_resend_verification_issues_new_token_and_allows_login(api_client):
    email = f"{uuid.uuid4()}@example.com"
    _create_unverified_user(email)
    old_token = _get_user(email).verification_token

    r = await api_client.post("/api/v1/auth/resend-verification", json={"identifier": email})
    assert r.status_code == 204
    new_token = _get_user(email).verification_token
    assert new_token is not None
    assert new_token != old_token

    r = await api_client.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert r.status_code == 200

    r = await api_client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
