from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Post
from src.pipeline.processing.content_dedup import _normalize_for_comparison

# Cửa sổ thời gian coi là "đăng dồn dập" — không quét cả lịch sử topic (có thể rất dài), chỉ cần đủ
# để phát hiện cụm bài đăng gần nhau thật sự đáng ngờ.
SEEDING_CLUSTER_WINDOW_HOURS = 48
# Chặn số bài so sánh mỗi lần — topic hoạt động mạnh trong 48h có thể có hàng trăm bài, so sánh
# từng cặp mọi bài là O(n^2) không cần thiết cho mục đích ước lượng quy mô cụm.
SEEDING_CLUSTER_LOOKBACK = 200
# Similarity lỏng hơn hẳn content_dedup.py (bắt trùng gần y hệt) — seeding thường đổi từ ngữ nhưng
# giữ nguyên cấu trúc câu/ý, nên ngưỡng thấp hơn để vẫn bắt được nhóm "na ná nhau", chấp nhận có thể
# bắt nhầm vài trường hợp trùng ngẫu nhiên (LLM ở detect_seeding sẽ tự cân nhắc thêm giọng văn, đây
# chỉ là TÍN HIỆU BỔ SUNG đưa vào prompt, không phải kết luận cuối).
_SIMILARITY_THRESHOLD = 0.6


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def count_similar_recent_posts(
    session: Session, topic_id: UUID, content: str, exclude_post_id: UUID | None = None
) -> int:
    """Đếm số bài viết CÙNG topic có nội dung/giọng văn TƯƠNG TỰ (không cần trùng y hệt như
    content_dedup.find_duplicate_content_ids) đăng trong SEEDING_CLUSTER_WINDOW_HOURS giờ gần đây —
    làm bằng chứng đưa vào prompt cho src/analysis/seeding_detection.py::detect_seeding. Cụm dồn dập
    KHÔNG tự động là seeding (có thể là bùng nổ complaint THẬT từ 1 sự cố có thật) — số đếm này chỉ
    là 1 tín hiệu, LLM tự cân nhắc thêm giọng văn để kết luận."""
    target_tokens = set(_normalize_for_comparison(content).split())
    if not target_tokens:
        return 0

    since = datetime.now(UTC) - timedelta(hours=SEEDING_CLUSTER_WINDOW_HOURS)
    effective_date = func.coalesce(Post.posted_at, Post.collected_at)
    query = (
        session.query(Post.content)
        .filter(Post.topic_id == topic_id, Post.content.isnot(None), effective_date >= since)
        .order_by(effective_date.desc())
        .limit(SEEDING_CLUSTER_LOOKBACK)
    )
    if exclude_post_id is not None:
        query = query.filter(Post.id != exclude_post_id)

    count = 0
    for (other_content,) in query.all():
        other_tokens = set(_normalize_for_comparison(other_content).split())
        if _jaccard_similarity(target_tokens, other_tokens) >= _SIMILARITY_THRESHOLD:
            count += 1
    return count
