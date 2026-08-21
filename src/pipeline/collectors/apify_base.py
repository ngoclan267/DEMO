import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

APIFY_API_BASE = "https://api.apify.com/v2"
# Trần 300s là giới hạn CỨNG của chính endpoint run-sync-get-dataset-items (Apify tự trả 408 quá
# mốc này) — đặt timeout httpx hơi cao hơn để chính Apify là bên báo lỗi trước.
APIFY_RUN_TIMEOUT_SECONDS = 310.0


def apify_timestamp_now() -> str:
    """Mốc thời gian "bây giờ" ở định dạng nhiều actor Apify chấp nhận cho input lọc theo ngày (vd
    "onlyPostsNewerThan") — hậu tố "Z", KHÔNG dùng `datetime.isoformat()` mặc định của Python (cho
    ra "+00:00", nhiều actor từ chối với lỗi 400 "must match pattern ...Z?$", xác nhận thật với
    apify/facebook-groups-scraper). Dùng chung cho mọi collector Apify có cơ chế incremental theo
    "since_date" (xem facebook.py/tiktok.py/news.py::resolved_config_update)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_apify_actor_sync(actor_id: str, run_input: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Chạy 1 Apify Actor ĐỒNG BỘ và lấy thẳng dataset item — dùng endpoint chính thức
    `run-sync-get-dataset-items` (POST, trả về mảng item trực tiếp, không cần tự poll trạng thái
    run). Dùng chung cho mọi collector dựa trên Apify (hiện có FacebookApifyCollector — xem
    src/pipeline/collectors/facebook.py); nguồn xã hội khác Apify hỗ trợ actor tương ứng chỉ cần
    gọi lại hàm này với actor_id/run_input khác, không cần viết lại phần gọi API.

    LƯU Ý CHI PHÍ: Apify tính phí theo actor (thường theo số kết quả trả về) — luôn giới hạn kết
    quả trong `run_input` (vd "resultsLimit"), không gọi không giới hạn.

    Trả về None (không raise) khi thiếu token hoặc lỗi mạng/API — CỐ Ý phân biệt với [] (chạy
    thành công nhưng không có kết quả mới, vd không có comment nào mới). Phân biệt này quan trọng
    cho caller nào dùng cursor tăng dần theo thời gian (xem FacebookApifyCollector.resolved_config_
    update): lỗi tạm thời không được phép đẩy cursor tới, nếu không sẽ bỏ sót vĩnh viễn khoảng thời
    gian của lần chạy lỗi đó."""
    token = get_settings().apify_api_token
    if not token:
        logger.warning("Chưa cấu hình APIFY_API_TOKEN — bỏ qua Apify actor=%s", actor_id)
        return None

    # Quy ước URL của Apify API: id actor dạng "chủ_sở_hữu/tên_actor" phải thay "/" bằng "~".
    url_actor_id = actor_id.replace("/", "~")
    url = f"{APIFY_API_BASE}/actors/{url_actor_id}/run-sync-get-dataset-items"

    try:
        with httpx.Client(timeout=APIFY_RUN_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers={"Authorization": f"Bearer {token}"}, json=run_input)
            response.raise_for_status()
            items = response.json()
    except Exception:
        logger.exception("Lỗi khi chạy Apify actor=%s", actor_id)
        return None

    if not isinstance(items, list):
        logger.warning("Apify actor=%s trả về dữ liệu không đúng dạng danh sách: %r", actor_id, type(items))
        return None
    return items
