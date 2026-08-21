"""POST /contact (form "Liên hệ tư vấn" công khai) + GET/PATCH /admin/contacts (xem/đánh dấu xử lý,
chỉ platform admin) — xem src/api/routes_contact.py, src/api/routes_admin.py."""

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
from src.db.models import Base, ContactRequest, User
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
    with patch("src.api.routes_contact.send_email") as mock:
        yield mock


@pytest_asyncio.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _admin_headers(api_client) -> dict:
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(
            User(email=email, password_hash=hash_password("testpass123"), is_verified=True, is_platform_admin=True)
        )
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _contact_payload(**overrides) -> dict:
    payload = {
        "company_name": f"Ngân hàng {uuid.uuid4().hex[:6]}",
        "contact_name": "Nguyễn Văn A",
        "email": f"{uuid.uuid4()}@example.com",
        "phone": "0900000000",
        "message": "Muốn dùng thử sản phẩm",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_submit_contact_request_persists_and_emails_every_platform_admin(_no_real_email, api_client):
    """LƯU DB TRƯỚC (không phụ thuộc email có gửi được hay không), rồi gửi email cho TOÀN BỘ
    platform admin đang có — xem docstring submit_contact_request()."""
    session = sessionmaker(bind=_engine)()
    try:
        admin_emails = [f"{uuid.uuid4()}@example.com" for _ in range(2)]
        for email in admin_emails:
            session.add(User(email=email, password_hash=hash_password("x"), is_verified=True, is_platform_admin=True))
        session.commit()
    finally:
        session.close()

    payload = _contact_payload()
    r = await api_client.post("/api/v1/contact", json=payload)
    assert r.status_code == 204

    session = sessionmaker(bind=_engine)()
    try:
        record = session.query(ContactRequest).filter(ContactRequest.email == payload["email"]).one()
        assert record.company_name == payload["company_name"]
        assert record.contact_name == payload["contact_name"]
        assert record.phone == payload["phone"]
        assert record.message == payload["message"]
        assert record.is_handled is False
    finally:
        session.close()

    assert _no_real_email.call_count == len(admin_emails)
    notified = {call.kwargs["to"] for call in _no_real_email.call_args_list}
    assert notified == set(admin_emails)


@pytest.mark.asyncio
async def test_list_contacts_requires_platform_admin(api_client):
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(User(email=email, password_hash=hash_password("testpass123"), is_verified=True))
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await api_client.get("/api/v1/admin/contacts", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_contacts_filters_by_handled(api_client):
    admin_headers = await _admin_headers(api_client)
    session = sessionmaker(bind=_engine)()
    try:
        pending = ContactRequest(**_contact_payload(), is_handled=False)
        handled = ContactRequest(**_contact_payload(), is_handled=True)
        session.add_all([pending, handled])
        session.commit()
        pending_email, handled_email = pending.email, handled.email
    finally:
        session.close()

    r = await api_client.get("/api/v1/admin/contacts?handled=false", headers=admin_headers)
    assert r.status_code == 200
    emails = {row["email"] for row in r.json()}
    assert pending_email in emails
    assert handled_email not in emails

    r = await api_client.get("/api/v1/admin/contacts?handled=true", headers=admin_headers)
    emails = {row["email"] for row in r.json()}
    assert handled_email in emails
    assert pending_email not in emails


@pytest.mark.asyncio
async def test_update_contact_marks_handled(api_client):
    admin_headers = await _admin_headers(api_client)
    session = sessionmaker(bind=_engine)()
    try:
        record = ContactRequest(**_contact_payload(), is_handled=False)
        session.add(record)
        session.commit()
        contact_id = str(record.id)
    finally:
        session.close()

    r = await api_client.patch(f"/api/v1/admin/contacts/{contact_id}", json={"is_handled": True}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_handled"] is True

    session = sessionmaker(bind=_engine)()
    try:
        assert session.get(ContactRequest, uuid.UUID(contact_id)).is_handled is True
    finally:
        session.close()


@pytest.mark.asyncio
async def test_update_contact_404_for_unknown_id(api_client):
    admin_headers = await _admin_headers(api_client)
    r = await api_client.patch(
        f"/api/v1/admin/contacts/{uuid.uuid4()}", json={"is_handled": True}, headers=admin_headers
    )
    assert r.status_code == 404
