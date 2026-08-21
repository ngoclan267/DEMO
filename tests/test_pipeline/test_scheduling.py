from datetime import UTC, datetime, timedelta

from src.db.models import Source
from src.pipeline.runner import _is_source_due


def _source(crawl_interval_minutes=None, last_crawled_at=None) -> Source:
    return Source(crawl_interval_minutes=crawl_interval_minutes, last_crawled_at=last_crawled_at)


def test_source_without_interval_is_always_due():
    """Mọi nguồn hiện có (crawl_interval_minutes=None) phải LUÔN đến hạn — giữ nguyên hành vi cũ."""
    now = datetime.now(UTC)
    source = _source(crawl_interval_minutes=None, last_crawled_at=now)
    assert _is_source_due(source, now) is True


def test_source_never_crawled_is_due_even_with_interval_set():
    now = datetime.now(UTC)
    source = _source(crawl_interval_minutes=60, last_crawled_at=None)
    assert _is_source_due(source, now) is True


def test_source_with_interval_not_due_yet():
    now = datetime.now(UTC)
    source = _source(crawl_interval_minutes=60, last_crawled_at=now - timedelta(minutes=10))
    assert _is_source_due(source, now) is False


def test_source_with_interval_due_after_elapsed():
    now = datetime.now(UTC)
    source = _source(crawl_interval_minutes=60, last_crawled_at=now - timedelta(minutes=61))
    assert _is_source_due(source, now) is True
