from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    payment_url: str


class PaymentStatusResponse(BaseModel):
    status: str


class BillingPlan(BaseModel):
    """1 gói trả phí hiển thị ở màn "chọn gói" (frontend). id hiện chỉ dùng để hiển thị/tương lai
    (chưa có nhiều gói để phân biệt lúc checkout — mọi gói đều gọi chung /billing/checkout*,
    charge đúng subscription_price_vnd) — xem GET /billing/plans."""

    id: str
    name: str
    price_vnd: int
    description: str


class BillingPlansResponse(BaseModel):
    plans: list[BillingPlan]
