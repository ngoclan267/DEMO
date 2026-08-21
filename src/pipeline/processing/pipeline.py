import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

from src.pipeline.collectors.base import RawPost
from src.pipeline.processing.clean import clean_text
from src.pipeline.processing.dedup import dedupe_in_batch
from src.pipeline.processing.lang import detect_language
from src.pipeline.processing.priority import estimate_priority
from src.pipeline.processing.spam import is_spam

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    rows: list[dict]
    spam_count: int
    duplicate_in_batch: int
    # external_id (comment) -> external_id (bài viết cha) — CHỈ chứa các row có RawPost.parent_external_id
    # (hiện chỉ comment Facebook). Runner (xem src/pipeline/runner.py::_run_post_source) dùng map này
    # để resolve parent_post_id (UUID nội bộ) SAU KHI bài viết cha đã được upsert — rows ở trên
    # KHÔNG có sẵn parent_post_id vì tại bước này còn chưa biết UUID nội bộ của bài viết cha.
    parent_external_id_by_external_id: dict[str, str] = field(default_factory=dict)


def process_raw_posts(raw_posts: list[RawPost], *, topic_id: UUID, source_id: UUID) -> ProcessResult:
    """Processing Agent: dedup trong batch, làm sạch text, chuẩn hóa định dạng, gắn cờ spam,
    nhận diện ngôn ngữ — trả về các dict sẵn sàng để upsert vào bảng `posts`."""
    original_count = len(raw_posts)
    deduped = dedupe_in_batch(raw_posts)
    duplicate_in_batch = original_count - len(deduped)

    rows = []
    parent_map: dict[str, str] = {}
    spam_count = 0
    for raw_post in deduped:
        content = clean_text(raw_post.content)
        if not content:
            continue

        spam = is_spam(content)
        if spam:
            spam_count += 1

        rows.append(
            {
                "topic_id": topic_id,
                "source_id": source_id,
                "external_id": raw_post.external_id,
                "raw_content": json.dumps(raw_post.raw, default=str, ensure_ascii=False),
                "content": content,
                "language": detect_language(content),
                "posted_at": raw_post.posted_at,
                "reply_content": raw_post.reply_content,
                "reply_at": raw_post.reply_at,
                "is_spam": spam,
                "status": "cleaned",
                "priority_score": estimate_priority(content, raw_post.raw),
                "like_count": raw_post.like_count,
                "comment_count": raw_post.comment_count,
                "share_count": raw_post.share_count,
                "source_url": raw_post.source_url,
            }
        )
        if raw_post.parent_external_id:
            parent_map[raw_post.external_id] = raw_post.parent_external_id

    logger.info(
        "Processing Agent: %d raw -> %d rows (trùng batch: %d, spam: %d)",
        original_count,
        len(rows),
        duplicate_in_batch,
        spam_count,
    )

    return ProcessResult(
        rows=rows, spam_count=spam_count, duplicate_in_batch=duplicate_in_batch, parent_external_id_by_external_id=parent_map
    )
