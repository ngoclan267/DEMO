"""Ký/xác thực chữ ký VNPay (HMAC-SHA512) — chỉ hàm thuần, không phụ thuộc DB/FastAPI/Settings để
dễ unit-test (ký rồi tự xác thực lại bằng cùng secret, không cần gọi máy chủ VNPay thật).

Spec chữ ký VNPay (paymentv2/vpcpay.html, API v2.1.0): sort toàn bộ tham số vnp_* theo tên key
(alphabet), encode giá trị kiểu form (dấu cách -> '+', giống PHP urlencode()), nối thành chuỗi
"key1=value1&key2=value2&...", rồi HMAC-SHA512 chuỗi đó bằng hash_secret của merchant. Áp dụng cho
cả lúc TẠO url thanh toán lẫn lúc XÁC THỰC dữ liệu VNPay gửi về (return URL redirect và IPN
webhook) — cùng 1 thuật toán, khác chiều.
"""

import hashlib
import hmac
from datetime import datetime
from urllib.parse import quote_plus

VNP_VERSION = "2.1.0"
VNP_COMMAND = "pay"
VNP_CURR_CODE = "VND"
VNP_LOCALE = "vn"
VNP_ORDER_TYPE = "other"


class VNPayNotConfiguredError(RuntimeError):
    """vnpay_tmn_code/vnpay_hash_secret chưa được cấu hình trong .env (xem src/config.py)."""


def _hash_data(params: dict[str, str]) -> str:
    return "&".join(f"{key}={quote_plus(str(value))}" for key, value in sorted(params.items()))


def sign(params: dict[str, str], hash_secret: str) -> str:
    """params KHÔNG được chứa vnp_SecureHash/vnp_SecureHashType — loại 2 key này trước khi gọi."""
    return hmac.new(hash_secret.encode("utf-8"), _hash_data(params).encode("utf-8"), hashlib.sha512).hexdigest()


def build_payment_url(
    *,
    tmn_code: str,
    hash_secret: str,
    payment_base_url: str,
    txn_ref: str,
    amount_vnd: int,
    order_info: str,
    client_ip: str,
    return_url: str,
) -> str:
    """Sinh URL thanh toán VNPay để redirect trình duyệt sang. amount_vnd là số VND thật (KHÔNG
    nhân 100 trước khi gọi) — VNPay yêu cầu đơn vị nhỏ nhất (x100), hàm này tự nhân."""
    if not tmn_code or not hash_secret:
        raise VNPayNotConfiguredError("Chưa cấu hình VNPAY_TMN_CODE/VNPAY_HASH_SECRET trong .env")

    params = {
        "vnp_Version": VNP_VERSION,
        "vnp_Command": VNP_COMMAND,
        "vnp_TmnCode": tmn_code,
        "vnp_Amount": str(amount_vnd * 100),
        "vnp_CurrCode": VNP_CURR_CODE,
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": order_info,
        "vnp_OrderType": VNP_ORDER_TYPE,
        "vnp_Locale": VNP_LOCALE,
        "vnp_ReturnUrl": return_url,
        "vnp_IpAddr": client_ip or "127.0.0.1",
        "vnp_CreateDate": datetime.now().strftime("%Y%m%d%H%M%S"),
    }
    secure_hash = sign(params, hash_secret)
    query = "&".join(f"{key}={quote_plus(str(value))}" for key, value in sorted(params.items()))
    return f"{payment_base_url}?{query}&vnp_SecureHash={secure_hash}"


def verify_signature(params: dict[str, str], hash_secret: str) -> bool:
    """Xác thực chữ ký VNPay gửi kèm — dùng chung cho cả return-URL redirect và IPN webhook. params
    là TOÀN BỘ query params VNPay gửi về (bao gồm vnp_SecureHash)."""
    params = dict(params)
    received_hash = params.pop("vnp_SecureHash", "")
    params.pop("vnp_SecureHashType", None)
    if not received_hash:
        return False
    expected_hash = sign(params, hash_secret)
    return hmac.compare_digest(expected_hash.lower(), received_hash.lower())
