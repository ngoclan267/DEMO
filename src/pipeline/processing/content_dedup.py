import re
import unicodedata
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Post

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")

# So sánh với bao nhiêu bài viết GẦN NHẤT của source này — chặn để không quét toàn bộ lịch sử
# (source tồn tại lâu có thể đã tích luỹ hàng nghìn bài), vẫn đủ bắt được kiểu đăng lại/spam lặp
# nội dung trong khoảng thời gian gần — đúng hiện tượng quan sát được trên Facebook: nội dung
# giống hệt nhau, chỉ khác NGÀY đăng.
CONTENT_DEDUP_LOOKBACK = 500


def _normalize_for_comparison(text: str) -> str:
    """Chuẩn hoá CHỈ để so sánh trùng lặp (không dùng để lưu/hiển thị) — hạ chữ thường, bỏ dấu
    tiếng Việt, bỏ dấu câu/emoji, gộp khoảng trắng — để 2 bài viết giống nội dung nhưng khác biểu
    tượng cảm xúc/dấu câu/viết hoa vẫn nhận ra là trùng."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = _PUNCT_RE.sub(" ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def find_duplicate_content_ids(
    session: Session,
    source_id: UUID,
    rows: list[dict],
    parent_external_id_by_external_id: dict[str, str],
) -> set[str]:
    """Trả về tập external_id trong `rows` có NỘI DUNG trùng (sau chuẩn hoá) với 1 bài viết khác đã
    thấy — hoặc với 1 bài đã có sẵn trong DB của CÙNG source — bắt đúng kiểu đăng lại/spam lặp nội
    dung NHIỀU NGÀY khác nhau trên Facebook, không chỉ trùng trong 1 lần crawl. Bài viết ĐẦU TIÊN
    xuất hiện (dù trong batch này hay đã có sẵn trong DB) KHÔNG bị đánh dấu — chỉ các bản lặp lại
    sau đó, để vẫn giữ đúng 1 bản phân tích được.

    CHỈ áp dụng cho bài viết GỐC (parent_external_id rỗng) — comment ngắn nên trùng câu chữ giữa
    những người khác nhau là bình thường (vd "App lỗi quá", "Sao chưa fix"), không phải dấu hiệu
    đăng lại như bài viết dài hơn.

    Không xoá bản ghi — caller tự đánh dấu is_duplicate=True (giữ nguyên dữ liệu, cùng triết lý với
    is_spam() trong spam.py: đánh dấu thay vì loại bỏ, để không mất số liệu thống kê/bằng chứng)."""
    top_level_rows = [row for row in rows if row["external_id"] not in parent_external_id_by_external_id]
    if not top_level_rows:
        return set()

    existing_contents = (
        session.query(Post.content)
        .filter(Post.source_id == source_id, Post.parent_post_id.is_(None), Post.content.isnot(None))
        .order_by(Post.collected_at.desc())
        .limit(CONTENT_DEDUP_LOOKBACK)
        .all()
    )
    seen = {_normalize_for_comparison(content) for (content,) in existing_contents if content}

    duplicate_ids: set[str] = set()
    for row in top_level_rows:
        fingerprint = _normalize_for_comparison(row["content"])
        if not fingerprint:
            continue
        if fingerprint in seen:
            duplicate_ids.add(row["external_id"])
        else:
            seen.add(fingerprint)
    return duplicate_ids
