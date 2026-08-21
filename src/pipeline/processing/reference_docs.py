import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import OfficialDocument
from src.pipeline.collectors.base import RawPost
from src.pipeline.processing.clean import clean_text
from src.pipeline.processing.dedup import dedupe_in_batch

logger = logging.getLogger(__name__)


def process_raw_documents(raw_posts: list[RawPost], *, topic_id: UUID, source_id: UUID) -> list[dict]:
    """Tương đương process_raw_posts nhưng cho tài liệu THAM CHIẾU (thông báo/chính sách/biểu phí...
    chính thức của ngân hàng) — không cần spam/lang detection như phản hồi khách hàng, chỉ cần làm
    sạch text + tính content_hash để phát hiện nội dung trang đã đổi giữa các lần crawl."""
    deduped = dedupe_in_batch(raw_posts)
    now = datetime.now(UTC)

    rows = []
    for raw_post in deduped:
        content = clean_text(raw_post.content)
        if not content:
            continue

        raw = raw_post.raw or {}
        rows.append(
            {
                "topic_id": topic_id,
                "source_id": source_id,
                "url": raw_post.external_id,
                "title": raw.get("title") or raw_post.external_id,
                "content": content,
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "category": raw.get("category") or "other",
                "published_at": raw_post.posted_at,
                # Đặt tường minh (thay vì dựa vào default cột) vì cần CÙNG giá trị này trong mệnh đề
                # ON CONFLICT DO UPDATE bên dưới (upsert_official_documents) — cột không có
                # default= ở model thì không tự có mặt trong EXCLUDED của Postgres.
                "last_checked_at": now,
            }
        )

    logger.info("Reference Processing: %d raw -> %d rows", len(raw_posts), len(rows))
    return rows


@dataclass
class UpsertDocumentResult:
    inserted: int
    skipped_unchanged: int


def upsert_official_documents(session: Session, rows: list[dict]) -> UpsertDocumentResult:
    """Insert hàng loạt vào official_documents, dựa vào UNIQUE(topic_id, url) — tài liệu đã biết chỉ
    được CẬP NHẬT (content/content_hash/title/category/last_seen_at) khi content_hash thực sự đổi,
    để không ghi lại (và bump last_seen_at) mỗi chu kỳ cho những trang không đổi gì."""
    if not rows:
        return UpsertDocumentResult(inserted=0, skipped_unchanged=0)

    stmt = pg_insert(OfficialDocument).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["topic_id", "url"],
        set_={
            "content": stmt.excluded.content,
            "content_hash": stmt.excluded.content_hash,
            "title": stmt.excluded.title,
            "category": stmt.excluded.category,
            "published_at": stmt.excluded.published_at,
            "last_seen_at": stmt.excluded.last_seen_at,
            "last_checked_at": stmt.excluded.last_checked_at,
        },
        where=(OfficialDocument.content_hash.is_distinct_from(stmt.excluded.content_hash)),
    )
    result = session.execute(stmt)
    session.commit()

    inserted = result.rowcount if result.rowcount and result.rowcount > 0 else 0
    skipped = len(rows) - inserted
    return UpsertDocumentResult(inserted=inserted, skipped_unchanged=skipped)
