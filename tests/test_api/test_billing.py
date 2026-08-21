"""Dùng thử có hạn + nâng cấp trả phí qua VNPay. 2 phần: (1) hàm ký/xác thực chữ ký VNPay thuần
(không cần DB, tự ký rồi tự xác thực lại, không gọi máy chủ VNPay thật) — xem src/billing/vnpay.py;
(2) luồng API: login LUÔN thành công kể cả hết hạn dùng thử (chỉ tạm dừng phân tích + hiện
UserResponse.trial_expired, xem routes_auth.py), /billing/checkout (yêu cầu JWT), /billing/vnpay-ipn."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.security import hash_password
from src.billing import vnpay
from src.config import Settings, get_settings
from src.db.models import Base, LLMUsage, Payment, User
from src.db.session import get_db
from src.main import app

# ---------------------------------------------------------------------------
# Phần 1: ký/xác thực chữ ký VNPay — hàm thuần, không cần DB/Postgres.
# ---------------------------------------------------------------------------

_TEST_HASH_SECRET = "TESTSECRETKEY123"


def test_build_payment_url_raises_when_not_configured():
    with pytest.raises(vnpay.VNPayNotConfiguredError):
        vnpay.build_payment_url(
            tmn_code="",
            hash_secret="",
            payment_base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
            txn_ref="abc123",
            amount_vnd=2_000_000,
            order_info="test",
            client_ip="127.0.0.1",
            return_url="http://localhost:8000/api/v1/billing/vnpay-return",
        )


def _parse_query(url: str) -> dict[str, str]:
    from urllib.parse import parse_qsl, urlsplit

    return dict(parse_qsl(urlsplit(url).query))


def test_build_and_verify_signature_roundtrip():
    url = vnpay.build_payment_url(
        tmn_code="TESTCODE01",
        hash_secret=_TEST_HASH_SECRET,
        payment_base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        txn_ref="abc123",
        amount_vnd=2_000_000,
        order_info="Nang cap tai khoan",
        client_ip="127.0.0.1",
        return_url="http://localhost:8000/api/v1/billing/vnpay-return",
    )
    params = _parse_query(url)
    assert params["vnp_Amount"] == "200000000"  # x100
    assert vnpay.verify_signature(params, _TEST_HASH_SECRET) is True


def test_verify_signature_rejects_wrong_secret():
    url = vnpay.build_payment_url(
        tmn_code="TESTCODE01",
        hash_secret=_TEST_HASH_SECRET,
        payment_base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        txn_ref="abc123",
        amount_vnd=2_000_000,
        order_info="test",
        client_ip="127.0.0.1",
        return_url="http://localhost:8000/api/v1/billing/vnpay-return",
    )
    params = _parse_query(url)
    assert vnpay.verify_signature(params, "wrong-secret") is False


def test_verify_signature_rejects_tampered_param():
    url = vnpay.build_payment_url(
        tmn_code="TESTCODE01",
        hash_secret=_TEST_HASH_SECRET,
        payment_base_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        txn_ref="abc123",
        amount_vnd=2_000_000,
        order_info="test",
        client_ip="127.0.0.1",
        return_url="http://localhost:8000/api/v1/billing/vnpay-return",
    )
    params = _parse_query(url)
    params["vnp_Amount"] = "999999999"
    assert vnpay.verify_signature(params, _TEST_HASH_SECRET) is False


def test_verify_signature_missing_hash_rejected():
    assert vnpay.verify_signature({"vnp_TxnRef": "abc123"}, _TEST_HASH_SECRET) is False


# ---------------------------------------------------------------------------
# Phần 2: luồng API — cần Postgres thật (giống test_admin_topics.py).
# ---------------------------------------------------------------------------


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


_VNPAY_SETTINGS = Settings(
    vnpay_tmn_code="TESTCODE01",
    vnpay_hash_secret=_TEST_HASH_SECRET,
    vnpay_payment_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
    subscription_price_vnd=2_000_000,
    backend_base_url="http://testserver",
    frontend_base_url="http://localhost:3000",
)


@pytest.fixture(autouse=True)
def _vnpay_configured():
    """VNPAY_TMN_CODE/VNPAY_HASH_SECRET rỗng theo mặc định (xem src/config.py) — patch get_settings
    ở đúng những module gọi nó để test được /billing/checkout và /billing/vnpay-ipn mà không cần
    đăng ký merchant sandbox thật."""
    with (
        patch("src.api.routes_billing.get_settings", return_value=_VNPAY_SETTINGS),
        patch("src.api.routes_auth.get_settings", return_value=_VNPAY_SETTINGS),
    ):
        yield


@pytest_asyncio.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _session():
    return sessionmaker(bind=_engine)()


async def _create_trial_owner(api_client, *, expired: bool) -> tuple[str, str]:
    """Tạo 1 tài khoản doanh nghiệp "dùng thử" qua admin, đặt mật khẩu qua link (giống luồng thật),
    rồi (tuỳ chọn) chỉnh trial_ends_at về quá khứ để giả lập hết hạn. Trả về (email, password)."""
    admin_email = f"{uuid.uuid4()}@example.com"
    session = _session()
    try:
        session.add(
            User(
                email=admin_email,
                password_hash=hash_password("adminpass123"),
                is_verified=True,
                is_platform_admin=True,
            )
        )
        session.commit()
    finally:
        session.close()
    admin_login = await api_client.post(
        "/api/v1/auth/login", json={"identifier": admin_email, "password": "adminpass123"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    owner_email = f"{uuid.uuid4()}@example.com"
    await api_client.post(
        "/api/v1/topics/admin",
        json={"name": "Ngân hàng Trial", "owner_email": owner_email, "plan": "trial"},
        headers=admin_headers,
    )

    session = _session()
    try:
        owner = session.query(User).filter(User.email == owner_email).first()
        reset_token = owner.reset_token
        if expired:
            owner.trial_ends_at = datetime.now(UTC) - timedelta(days=1)
            session.commit()
    finally:
        session.close()

    password = "ownernewpass123"
    r = await api_client.post("/api/v1/auth/reset-password", json={"token": reset_token, "new_password": password})
    assert r.status_code == 204
    return owner_email, password


async def _login_headers(api_client, email: str, password: str) -> dict:
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_login_succeeds_when_trial_still_active(api_client):
    email, password = await _create_trial_owner(api_client, expired=False)
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_succeeds_and_trial_expired_flag_set_when_time_expired(api_client):
    """Hết hạn THỜI GIAN (trial_ends_at) KHÔNG khoá đăng nhập nữa — chỉ báo qua
    UserResponse.trial_expired để frontend hiện banner mời nâng cấp (xem TrialQuotaBanner.tsx)."""
    email, password = await _create_trial_owner(api_client, expired=True)
    headers = await _login_headers(api_client, email, password)

    me = await api_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["trial_expired"] is True


@pytest.mark.asyncio
async def test_login_succeeds_and_trial_expired_flag_set_when_usage_limit_exceeded(api_client):
    """Chưa hết hạn THỜI GIAN nhưng đã dùng hết trần lượt gọi AI miễn phí (trial_analysis_call_limit)
    vẫn phải báo trial_expired=True y hệt hết hạn thời gian — 2 điều kiện độc lập, chỉ cần 1 cái
    đúng — nhưng KHÔNG khoá đăng nhập ở cả 2 trường hợp."""
    email, password = await _create_trial_owner(api_client, expired=False)

    session = _session()
    try:
        owner = session.query(User).filter(User.email == email).first()
        session.add(
            LLMUsage(user_id=owner.id, call_type="classification", model="gemma-4-26b-a4b-it", input_tokens=10, output_tokens=5)
        )
        session.commit()
    finally:
        session.close()

    low_limit_settings = _VNPAY_SETTINGS.model_copy(update={"trial_analysis_call_limit": 1})
    with patch("src.api.routes_auth.get_settings", return_value=low_limit_settings):
        login_r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
        assert login_r.status_code == 200
        headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}
        me = await api_client.get("/api/v1/auth/me", headers=headers)

    assert me.status_code == 200
    assert me.json()["trial_expired"] is True


@pytest.mark.asyncio
async def test_list_plans_returns_configured_price_without_auth(api_client):
    """GET /billing/plans công khai (không cần JWT) — dùng ở màn "chọn gói"/banner nâng cấp trong
    dashboard."""
    r = await api_client.get("/api/v1/billing/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert len(plans) >= 1
    assert plans[0]["price_vnd"] == _VNPAY_SETTINGS.subscription_price_vnd


@pytest.mark.asyncio
async def test_checkout_requires_authentication(api_client):
    r = await api_client.post("/api/v1/billing/checkout")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_checkout_returns_vnpay_payment_url(api_client):
    """Tài khoản dùng thử đã hết hạn vẫn đăng nhập được (xem test_login_succeeds_and_trial_expired_*
    ở trên) nên gọi thẳng /billing/checkout bằng JWT bình thường, không cần token riêng nào khác."""
    email, password = await _create_trial_owner(api_client, expired=True)
    headers = await _login_headers(api_client, email, password)

    r = await api_client.post("/api/v1/billing/checkout", headers=headers)
    assert r.status_code == 200
    payment_url = r.json()["payment_url"]
    assert payment_url.startswith(_VNPAY_SETTINGS.vnpay_payment_url)
    assert "vnp_SecureHash=" in payment_url

    session = _session()
    try:
        payments = session.query(Payment).filter(Payment.user_id == session.query(User).filter(User.email == email).first().id).all()
        assert len(payments) == 1
        assert payments[0].status == "pending"
        assert payments[0].amount_vnd == _VNPAY_SETTINGS.subscription_price_vnd
    finally:
        session.close()


def _build_ipn_params(*, txn_ref: str, amount_vnd: int, response_code: str) -> dict:
    params = {
        "vnp_Amount": str(amount_vnd * 100),
        "vnp_BankCode": "NCB",
        "vnp_OrderInfo": "Nang cap tai khoan",
        "vnp_ResponseCode": response_code,
        "vnp_TransactionStatus": response_code,
        "vnp_TxnRef": txn_ref,
        "vnp_PayDate": "20260815120000",
    }
    params["vnp_SecureHash"] = vnpay.sign(params, _TEST_HASH_SECRET)
    return params


async def _create_pending_payment(api_client, *, email: str, password: str) -> str:
    headers = await _login_headers(api_client, email, password)
    checkout_r = await api_client.post("/api/v1/billing/checkout", headers=headers)
    txn_ref = _parse_query(checkout_r.json()["payment_url"])["vnp_TxnRef"]
    return txn_ref


@pytest.mark.asyncio
async def test_vnpay_ipn_success_flips_user_to_paid(api_client):
    email, password = await _create_trial_owner(api_client, expired=True)
    txn_ref = await _create_pending_payment(api_client, email=email, password=password)

    ipn_params = _build_ipn_params(txn_ref=txn_ref, amount_vnd=_VNPAY_SETTINGS.subscription_price_vnd, response_code="00")
    r = await api_client.get("/api/v1/billing/vnpay-ipn", params=ipn_params)
    assert r.status_code == 200
    assert r.json()["RspCode"] == "00"

    session = _session()
    try:
        owner = session.query(User).filter(User.email == email).first()
        assert owner.is_paid is True
        payment = session.query(Payment).filter(Payment.txn_ref == txn_ref).first()
        assert payment.status == "success"
    finally:
        session.close()

    # is_paid=True rồi thì trial_expired phải về False (đăng nhập vẫn luôn thành công dù trước/sau).
    login_r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert login_r.status_code == 200
    headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["trial_expired"] is False


@pytest.mark.asyncio
async def test_vnpay_ipn_rejects_bad_signature(api_client):
    email, password = await _create_trial_owner(api_client, expired=True)
    txn_ref = await _create_pending_payment(api_client, email=email, password=password)

    ipn_params = _build_ipn_params(txn_ref=txn_ref, amount_vnd=_VNPAY_SETTINGS.subscription_price_vnd, response_code="00")
    ipn_params["vnp_Amount"] = str((_VNPAY_SETTINGS.subscription_price_vnd + 1) * 100)  # phá chữ ký

    r = await api_client.get("/api/v1/billing/vnpay-ipn", params=ipn_params)
    assert r.json()["RspCode"] == "97"

    session = _session()
    try:
        payment = session.query(Payment).filter(Payment.txn_ref == txn_ref).first()
        assert payment.status == "pending"
    finally:
        session.close()


@pytest.mark.asyncio
async def test_vnpay_ipn_idempotent_on_repeat(api_client):
    email, password = await _create_trial_owner(api_client, expired=True)
    txn_ref = await _create_pending_payment(api_client, email=email, password=password)
    ipn_params = _build_ipn_params(txn_ref=txn_ref, amount_vnd=_VNPAY_SETTINGS.subscription_price_vnd, response_code="00")

    first = await api_client.get("/api/v1/billing/vnpay-ipn", params=ipn_params)
    assert first.json()["RspCode"] == "00"

    second = await api_client.get("/api/v1/billing/vnpay-ipn", params=ipn_params)
    assert second.json()["RspCode"] == "02"


@pytest.mark.asyncio
async def test_vnpay_ipn_failed_payment_does_not_mark_paid(api_client):
    email, password = await _create_trial_owner(api_client, expired=True)
    txn_ref = await _create_pending_payment(api_client, email=email, password=password)

    ipn_params = _build_ipn_params(txn_ref=txn_ref, amount_vnd=_VNPAY_SETTINGS.subscription_price_vnd, response_code="24")
    r = await api_client.get("/api/v1/billing/vnpay-ipn", params=ipn_params)
    assert r.json()["RspCode"] == "00"  # đã nhận thông báo — chỉ là thanh toán thất bại

    session = _session()
    try:
        owner = session.query(User).filter(User.email == email).first()
        assert owner.is_paid is False
        payment = session.query(Payment).filter(Payment.txn_ref == txn_ref).first()
        assert payment.status == "failed"
    finally:
        session.close()
