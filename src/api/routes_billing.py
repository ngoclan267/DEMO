import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.api.schemas_billing import BillingPlan, BillingPlansResponse, CheckoutResponse, PaymentStatusResponse
from src.auth.dependencies import get_current_user
from src.billing.vnpay import VNPayNotConfiguredError, build_payment_url, verify_signature
from src.config import get_settings
from src.db.models import Payment, User
from src.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=BillingPlansResponse)
def list_plans() -> BillingPlansResponse:
    """Danh sách gói trả phí — hiện chỉ có 1 gói (subscription_price_vnd), tách ra thành danh sách
    (thay vì hardcode giá ở frontend) để mở rộng thêm gói sau này chỉ cần sửa ở đây. Công khai
    (không cần JWT) — dùng ở màn "chọn gói"/banner nâng cấp trong dashboard."""
    settings = get_settings()
    return BillingPlansResponse(
        plans=[
            BillingPlan(
                id="standard",
                name="Gói Chính thức",
                price_vnd=settings.subscription_price_vnd,
                description="Không giới hạn số lượt phân tích AI mỗi ngày, dùng không giới hạn thời gian.",
            )
        ]
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CheckoutResponse:
    """Yêu cầu JWT bình thường — hết hạn dùng thử KHÔNG khoá đăng nhập (xem UserResponse.trial_expired
    trong routes_auth.py), nên luôn có session hợp lệ để gọi thẳng, không cần token riêng nào khác."""
    settings = get_settings()
    txn_ref = secrets.token_hex(16)
    payment = Payment(user_id=current_user.id, txn_ref=txn_ref, amount_vnd=settings.subscription_price_vnd, status="pending")
    db.add(payment)
    db.commit()

    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        payment_url = build_payment_url(
            tmn_code=settings.vnpay_tmn_code,
            hash_secret=settings.vnpay_hash_secret,
            payment_base_url=settings.vnpay_payment_url,
            txn_ref=txn_ref,
            amount_vnd=settings.subscription_price_vnd,
            order_info=f"Nang cap tai khoan {current_user.email}",
            client_ip=client_ip,
            return_url=f"{settings.backend_base_url}/api/v1/billing/vnpay-return",
        )
    except VNPayNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return CheckoutResponse(payment_url=payment_url)


@router.get("/status", response_model=PaymentStatusResponse)
def get_payment_status(txn_ref: str, db: Session = Depends(get_db)) -> PaymentStatusResponse:
    payment = db.query(Payment).filter(Payment.txn_ref == txn_ref).first()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy giao dịch")
    return PaymentStatusResponse(status=payment.status)


@router.get("/vnpay-return")
def vnpay_return(request: Request) -> RedirectResponse:
    """VNPay redirect TRÌNH DUYỆT về đây sau khi thanh toán — chỉ để điều hướng người dùng, KHÔNG
    phải nơi chốt trạng thái thanh toán chính thức (việc đó thuộc về IPN bên dưới, vì return-URL có
    thể bị bỏ lỡ nếu người dùng đóng tab giữa chừng)."""
    settings = get_settings()
    params = dict(request.query_params)
    txn_ref = params.get("vnp_TxnRef", "")
    signature_ok = bool(settings.vnpay_hash_secret) and verify_signature(params, settings.vnpay_hash_secret)
    code = params.get("vnp_ResponseCode", "") if signature_ok else "invalid_signature"
    return RedirectResponse(url=f"{settings.frontend_base_url}/billing-return?txn_ref={txn_ref}&code={code}")


@router.get("/vnpay-ipn")
def vnpay_ipn(request: Request, db: Session = Depends(get_db)) -> dict:
    """VNPay gọi server-to-server (GET, query string, theo đúng mẫu tích hợp chính thức của VNPay)
    sau khi thanh toán — đây là nơi CHÍNH THỨC chốt is_paid, khác /vnpay-return (chỉ redirect trình
    duyệt). Phải trả đúng format {"RspCode", "Message"} để VNPay ngừng gọi lại — RspCode ở ĐÂY
    nghĩa là "đã nhận/xử lý thông báo", KHÁC vnp_ResponseCode trong params (kết quả thanh toán
    thật)."""
    settings = get_settings()
    params = dict(request.query_params)

    if not settings.vnpay_hash_secret or not verify_signature(params, settings.vnpay_hash_secret):
        return {"RspCode": "97", "Message": "Invalid signature"}

    txn_ref = params.get("vnp_TxnRef", "")
    payment = db.query(Payment).filter(Payment.txn_ref == txn_ref).first()
    if payment is None:
        return {"RspCode": "01", "Message": "Order not found"}

    if payment.status != "pending":
        return {"RspCode": "02", "Message": "Order already confirmed"}

    if params.get("vnp_Amount", "") != str(payment.amount_vnd * 100):
        return {"RspCode": "04", "Message": "Invalid amount"}

    if params.get("vnp_ResponseCode") == "00":
        payment.status = "success"
        payment.paid_at = datetime.now(UTC)
        payment.user.is_paid = True
    else:
        payment.status = "failed"
    db.commit()

    return {"RspCode": "00", "Message": "Confirm Success"}
