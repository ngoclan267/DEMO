import logging
from dataclasses import dataclass

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import Post
from src.pipeline.collectors.base import RawPost

logger = logging.getLogger(__name__)


def dedupe_in_batch(raw_posts: list[RawPost]) -> list[RawPost]:
    """Loại các RawPost trùng external_id trong cùng một lần thu thập (giữ bản ghi đầu tiên)."""
    seen: set[str] = set()
    deduped: list[RawPost] = []
    for post in raw_posts:
        if post.external_id in seen:
            continue
        seen.add(post.external_id)
        deduped.append(post)
    return deduped


@dataclass
class UpsertResult:
    inserted: int
    skipped_duplicate: int


def upsert_posts(session: Session, rows: list[dict]) -> UpsertResult:
    """Insert hàng loạt vào bảng `posts`, dựa vào UNIQUE(source_id, external_id) ở tầng DB để
    xử lý bản ghi đã tồn tại — an toàn khi các chu kỳ crawl chồng lấn dữ liệu (review cũ xuất hiện
    lại), tránh race condition so với kiểu SELECT rồi mới INSERT.

    Review đã tồn tại thì giữ nguyên nội dung/ngày đăng gốc — CHỈ ghi đè reply_content/reply_at, và
    chỉ khi bản ghi mới có reply_at (ngân hàng vừa trả lời một review cũ đã thu thập từ trước — xem
    GooglePlayCollector.collect, phần is_known). Không dùng ON CONFLICT DO NOTHING như trước vì
    cách đó bỏ qua vĩnh viễn mọi cập nhật cho review đã biết, kể cả phản hồi phát sinh sau.

    Riêng like_count/comment_count/share_count/source_url (hiện chỉ Facebook điền — xem
    src/pipeline/collectors/facebook.py) LUÔN ghi đè bằng giá trị mới nhất, KHÔNG cần điều kiện như
    reply_at: đây là số liệu/link đọc lại được mỗi chu kỳ (không phải nội dung 1 lần rồi bất biến
    như review), nếu chỉ ghi lúc insert lần đầu thì bài viết đã biết từ trước sẽ mãi mãi không có
    source_url/like count cập nhật dù actor luôn trả về đủ field này mỗi lần gọi lại.
    """
    if not rows:
        return UpsertResult(inserted=0, skipped_duplicate=0)

    stmt = pg_insert(Post).values(rows)
    # WHERE này chỉ để tránh đếm "inserted" ảo cho review đã biết không có gì mới (vd google_play/
    # app_store re-crawl lại review cũ không có reply/engagement) — search KHÔNG cản trở việc ghi
    # đè engagement/source_url khi 1 trong 3 điều kiện đúng, giữ nguyên ý nghĩa cũ cho reply.
    has_new_data = (
        stmt.excluded.reply_at.isnot(None)
        | stmt.excluded.like_count.isnot(None)
        | stmt.excluded.source_url.isnot(None)
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_id", "external_id"],
        set_={
            "reply_content": case((stmt.excluded.reply_at.isnot(None), stmt.excluded.reply_content), else_=Post.reply_content),
            "reply_at": case((stmt.excluded.reply_at.isnot(None), stmt.excluded.reply_at), else_=Post.reply_at),
            "like_count": stmt.excluded.like_count,
            "comment_count": stmt.excluded.comment_count,
            "share_count": stmt.excluded.share_count,
            "source_url": stmt.excluded.source_url,
        },
        where=has_new_data,
    )
    result = session.execute(stmt)
    session.commit()

    inserted = result.rowcount if result.rowcount and result.rowcount > 0 else 0
    skipped = len(rows) - inserted
    return UpsertResult(inserted=inserted, skipped_duplicate=skipped)
