from unittest.mock import patch

import pytest

from src.pipeline.collectors.news import NewsApifyCollector

ACTOR_ID = "scrapesage/google-news-scraper"


def _config(**overrides):
    base = {"actor_id": ACTOR_ID, "run_input": {"queries": ["TPBank"]}}
    base.update(overrides)
    return base


def test_requires_actor_id_and_run_input():
    with pytest.raises(ValueError):
        NewsApifyCollector({}).collect()
    with pytest.raises(ValueError):
        NewsApifyCollector({"actor_id": ACTOR_ID}).collect()


def test_maps_items_using_default_field_map():
    items = [
        {"url": "https://baomoi.com/a1", "title": "TPBank ra mắt tính năng mới", "date": "2026-08-01T10:00:00Z"},
        {"url": "https://baomoi.com/a2", "title": "  ", "date": "2026-08-01T10:00:00Z"},  # tiêu đề rỗng -> bỏ qua
        {"url": None, "title": "thiếu id"},  # thiếu id -> bỏ qua
    ]
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=items) as mock_run:
        collector = NewsApifyCollector(_config())
        result = collector.collect(limit=10)

    assert len(result) == 1
    assert result[0].external_id == "https://baomoi.com/a1"
    assert result[0].content == "TPBank ra mắt tính năng mới"
    assert result[0].posted_at is not None
    assert result[0].raw["category"] == "news"
    assert result[0].raw["title"] == "TPBank ra mắt tính năng mới"
    mock_run.assert_called_once()


def test_skips_known_ids():
    items = [{"url": "u1", "title": "đã biết"}, {"url": "u2", "title": "mới"}]
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=items):
        collector = NewsApifyCollector(_config())
        result = collector.collect(limit=10, known_ids={"u1"})

    assert len(result) == 1
    assert result[0].external_id == "u2"


def test_respects_limit():
    items = [{"url": str(i), "title": f"tin {i}"} for i in range(5)]
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=items):
        collector = NewsApifyCollector(_config())
        result = collector.collect(limit=2)

    assert len(result) == 2


def test_custom_field_map():
    items = [{"id": "x1", "headline": "nội dung tuỳ biến", "publishedAt": "2026-08-01T10:00:00Z"}]
    config = _config(field_map={"id": "id", "content": "headline", "posted_at": "publishedAt"})
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=items):
        collector = NewsApifyCollector(config)
        result = collector.collect(limit=10)

    assert result[0].external_id == "x1"
    assert result[0].content == "nội dung tuỳ biến"


def test_sets_since_date_cursor_on_success_even_if_empty():
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=[]):
        collector = NewsApifyCollector(_config())
        result = collector.collect(limit=10)

    assert result == []
    assert collector.resolved_config_update is not None
    assert "since_date" in collector.resolved_config_update


def test_does_not_advance_cursor_on_actor_failure():
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=None):
        collector = NewsApifyCollector(_config())
        result = collector.collect(limit=10)

    assert result == []
    assert collector.resolved_config_update is None


def test_defaults_results_limit_when_not_set_in_run_input():
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=[]) as mock_run:
        NewsApifyCollector(_config()).collect(limit=10)

    called_input = mock_run.call_args.args[1]
    assert called_input["resultsLimit"] == 10


def test_get_collector_dispatches_news_article():
    from src.pipeline.collectors import get_collector

    collector = get_collector("news_article", _config())
    assert isinstance(collector, NewsApifyCollector)


def test_news_article_is_a_reference_source_type():
    from src.pipeline.collectors import REFERENCE_SOURCE_TYPES

    assert "news_article" in REFERENCE_SOURCE_TYPES


def test_process_raw_documents_assigns_news_category():
    from uuid import uuid4

    from src.pipeline.processing.reference_docs import process_raw_documents

    items = [{"url": "https://baomoi.com/a1", "title": "TPBank ra mắt tính năng mới", "date": "2026-08-01T10:00:00Z"}]
    with patch("src.pipeline.collectors.news.run_apify_actor_sync", return_value=items):
        raw_posts = NewsApifyCollector(_config()).collect(limit=10)

    rows = process_raw_documents(raw_posts, topic_id=uuid4(), source_id=uuid4())
    assert len(rows) == 1
    assert rows[0]["category"] == "news"
    assert rows[0]["title"] == "TPBank ra mắt tính năng mới"
