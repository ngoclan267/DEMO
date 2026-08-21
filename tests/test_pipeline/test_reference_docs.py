from uuid import uuid4

from src.pipeline.collectors.base import RawPost
from src.pipeline.processing.reference_docs import process_raw_documents


def test_process_raw_documents_cleans_and_hashes_content():
    topic_id = uuid4()
    source_id = uuid4()
    raw_docs = [
        RawPost(
            external_id="https://bank.example/tin-tuc/bao-tri",
            content="<p>Bảo trì hệ thống  từ 23h</p>",
            posted_at=None,
            raw={"title": "Thông báo bảo trì", "category": "maintenance"},
        )
    ]

    rows = process_raw_documents(raw_docs, topic_id=topic_id, source_id=source_id)

    assert len(rows) == 1
    row = rows[0]
    assert row["topic_id"] == topic_id
    assert row["source_id"] == source_id
    assert row["url"] == "https://bank.example/tin-tuc/bao-tri"
    assert row["title"] == "Thông báo bảo trì"
    assert row["category"] == "maintenance"
    assert row["content"] == "Bảo trì hệ thống từ 23h"
    assert len(row["content_hash"]) == 64  # sha256 hex digest
    assert row["last_checked_at"] is not None


def test_process_raw_documents_dedupes_in_batch_by_url():
    topic_id = uuid4()
    source_id = uuid4()
    raw_docs = [
        RawPost(external_id="https://bank.example/a", content="nội dung 1", posted_at=None, raw={}),
        RawPost(external_id="https://bank.example/a", content="nội dung trùng url", posted_at=None, raw={}),
    ]

    rows = process_raw_documents(raw_docs, topic_id=topic_id, source_id=source_id)

    assert len(rows) == 1
    assert rows[0]["content"] == "nội dung 1"


def test_process_raw_documents_skips_empty_content():
    topic_id = uuid4()
    source_id = uuid4()
    raw_docs = [RawPost(external_id="https://bank.example/empty", content="   ", posted_at=None, raw={})]

    rows = process_raw_documents(raw_docs, topic_id=topic_id, source_id=source_id)

    assert rows == []


def test_process_raw_documents_defaults_category_and_title():
    topic_id = uuid4()
    source_id = uuid4()
    raw_docs = [RawPost(external_id="https://bank.example/x", content="nội dung", posted_at=None, raw={})]

    rows = process_raw_documents(raw_docs, topic_id=topic_id, source_id=source_id)

    assert rows[0]["category"] == "other"
    assert rows[0]["title"] == "https://bank.example/x"


def test_process_raw_documents_same_content_produces_same_hash():
    topic_id = uuid4()
    source_id = uuid4()
    doc_a = RawPost(external_id="https://bank.example/a", content="cùng nội dung", posted_at=None, raw={})
    doc_b = RawPost(external_id="https://bank.example/b", content="cùng nội dung", posted_at=None, raw={})

    rows = process_raw_documents([doc_a, doc_b], topic_id=topic_id, source_id=source_id)

    assert rows[0]["content_hash"] == rows[1]["content_hash"]
