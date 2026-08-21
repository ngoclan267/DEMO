from src.pipeline.collectors.base import RawPost
from src.pipeline.processing.dedup import dedupe_in_batch


def test_dedupe_in_batch_keeps_first_occurrence():
    posts = [
        RawPost(external_id="a", content="1", posted_at=None),
        RawPost(external_id="b", content="2", posted_at=None),
        RawPost(external_id="a", content="1-dup", posted_at=None),
    ]

    result = dedupe_in_batch(posts)

    assert [p.external_id for p in result] == ["a", "b"]
    assert result[0].content == "1"
