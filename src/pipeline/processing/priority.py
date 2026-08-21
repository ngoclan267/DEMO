import re
from typing import Any

# Từ khoá tiêu cực tiếng Việt phổ biến trong review ngân hàng — tín hiệu HEURISTIC, KHÔNG phải kết
# luận sentiment (đó là việc của Classification Agent, xem src/analysis/classification.py). Chỉ
# dùng để sắp thứ tự hàng đợi phân tích khi quota LLM có hạn, ưu tiên nội dung NHIỀU KHẢ NĂNG tiêu
# cực được phân tích trước.
NEGATIVE_SIGNAL_KEYWORDS = (
    "lỗi",
    "mất tiền",
    "lừa đảo",
    "tệ",
    "chậm",
    "không nhận được",
    "trừ tiền",
    "khóa tài khoản",
    "khoá tài khoản",
    "không đăng nhập",
    "treo",
    "đơ",
    "văng",
    "thất vọng",
    "tồi",
    "kém",
    "chán",
    "bực",
    "không thể",
    "không được",
)

# Tín hiệu nội dung có CLAIM cần đối chiếu (số tiền/%/chính sách) — ưu tiên phân tích trước vì đây
# đúng loại nội dung Verification Agent có thể đối chiếu được với nguồn chính thức.
CLAIM_SIGNAL_KEYWORDS = ("phí", "lãi suất", "cam kết", "quy định", "thông báo", "chính sách", "biểu phí")
_CURRENCY_RE = re.compile(r"\d+[.,]?\d*\s*(k|nghìn|triệu|tr|đồng|vnd|vnđ)\b", re.IGNORECASE)
_PERCENT_RE = re.compile(r"\d+([.,]\d+)?\s*%")

_NEGATIVE_WEIGHT = 0.15
_CLAIM_WEIGHT = 0.15
_LOW_RATING_WEIGHT = 0.3
_MAX_KEYWORD_HITS_COUNTED = 3  # tránh 1 review lặp từ khoá nhiều lần thổi điểm quá cao

_LOW_RATING_THRESHOLD = 2


def _count_hits(content_lower: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for kw in keywords if kw in content_lower)


def _extract_rating(raw: dict[str, Any]) -> int | None:
    """Google Play trả 'score' (int), App Store RSS trả 'im:rating': {'label': '5'} — 2 định dạng
    khác nhau tuỳ collector (xem src/pipeline/collectors/google_play.py, app_store.py)."""
    score = raw.get("score")
    if isinstance(score, int | float):
        return int(score)

    rating_field = raw.get("im:rating")
    if isinstance(rating_field, dict):
        label = rating_field.get("label")
        if label is not None:
            try:
                return int(label)
            except (TypeError, ValueError):
                return None
    return None


def estimate_priority(content: str, raw: dict[str, Any] | None = None) -> float:
    """Điểm ưu tiên PHÂN TÍCH — heuristic thuần (không qua LLM), tính lúc thu thập. CHỈ dùng để sắp
    thứ tự hàng đợi khi quota LLM có hạn (xem order_by trong src/analysis/runner.py::
    run_analysis_cycle), KHÔNG phải sentiment/kết luận AI. Điểm càng cao càng nên được phân tích
    sớm: có dấu hiệu tiêu cực, có claim cần đối chiếu, hoặc rating thấp (nếu nguồn có rating)."""
    raw = raw or {}
    content_lower = (content or "").lower()

    score = 0.0
    score += min(_count_hits(content_lower, NEGATIVE_SIGNAL_KEYWORDS), _MAX_KEYWORD_HITS_COUNTED) * _NEGATIVE_WEIGHT

    claim_hits = _count_hits(content_lower, CLAIM_SIGNAL_KEYWORDS)
    has_claim_pattern = bool(_CURRENCY_RE.search(content_lower) or _PERCENT_RE.search(content_lower))
    score += min(claim_hits + (1 if has_claim_pattern else 0), _MAX_KEYWORD_HITS_COUNTED) * _CLAIM_WEIGHT

    rating = _extract_rating(raw)
    if rating is not None and rating <= _LOW_RATING_THRESHOLD:
        score += _LOW_RATING_WEIGHT

    return round(min(score, 1.0), 4)
