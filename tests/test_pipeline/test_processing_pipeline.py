from uuid import uuid4

from src.pipeline.collectors.base import RawPost
from src.pipeline.processing.pipeline import process_raw_posts


def test_process_raw_posts_cleans_dedupes_and_flags_spam():
    topic_id = uuid4()
    source_id = uuid4()
    raw_posts = [
        RawPost(external_id="1", content="<p>Ứng dụng ổn định</p>", posted_at=None, raw={"score": 5}),
        RawPost(external_id="1", content="dup", posted_at=None, raw={}),  # trùng external_id trong batch
        RawPost(external_id="2", content="AAAAAAAAAA", posted_at=None, raw={}),  # spam (toàn hoa)
    ]

    result = process_raw_posts(raw_posts, topic_id=topic_id, source_id=source_id)

    assert result.duplicate_in_batch == 1
    assert len(result.rows) == 2

    row1 = next(r for r in result.rows if r["external_id"] == "1")
    assert row1["content"] == "Ứng dụng ổn định"
    assert row1["topic_id"] == topic_id
    assert row1["source_id"] == source_id
    assert row1["is_spam"] is False
    assert row1["status"] == "cleaned"

    row2 = next(r for r in result.rows if r["external_id"] == "2")
    assert row2["is_spam"] is True
    assert result.spam_count == 1
