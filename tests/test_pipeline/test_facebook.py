from unittest.mock import patch

import pytest

from src.pipeline.collectors.facebook import DEFAULT_COMMENT_ACTOR_ID, DEFAULT_POST_ACTOR_ID, FacebookApifyCollector

POST_ACTOR_ID = "some-actor/facebook-posts-scraper"


def _config(**overrides):
    base = {
        "post_actor_id": POST_ACTOR_ID,
        "post_run_input": {"startUrls": [{"url": "https://facebook.com/TPBank"}]},
    }
    base.update(overrides)
    return base


def _post_item(post_id="p1", url="https://facebook.com/TPBank/posts/p1", **overrides):
    item = {
        "postId": post_id,
        "text": "Thông báo bảo trì hệ thống",
        "time": "2026-08-01T09:00:00Z",
        "url": url,
        "likes": 12,
        "comments": 3,
        "shares": 1,
    }
    item.update(overrides)
    return item


def _run_side_effect(post_items, comments_by_post_url=None):
    """Giả lập run_apify_actor_sync: gọi actor bài viết (POST_ACTOR_ID) trả post_items, gọi actor
    comment (DEFAULT_COMMENT_ACTOR_ID) trả đúng danh sách comment của URL trong startUrls."""
    comments_by_post_url = comments_by_post_url or {}

    def _side_effect(actor_id, run_input):
        if actor_id == POST_ACTOR_ID:
            return post_items
        url = run_input["startUrls"][0]["url"]
        return comments_by_post_url.get(url, [])

    return _side_effect


def test_requires_post_run_input():
    with pytest.raises(ValueError):
        FacebookApifyCollector({}).collect()
    with pytest.raises(ValueError):
        FacebookApifyCollector({"post_actor_id": POST_ACTOR_ID}).collect()


def test_uses_default_post_actor_id_when_not_set():
    config = {"post_run_input": {"startUrls": [{"url": "https://facebook.com/TPBank"}]}}
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect([])) as mock_run:
        FacebookApifyCollector(config).collect(limit=10)

    assert mock_run.call_args.args[0] == DEFAULT_POST_ACTOR_ID


def test_maps_post_fields_including_engagement_counts():
    items = [_post_item()]
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect(items)):
        result = FacebookApifyCollector(_config()).collect(limit=10)

    assert len(result) == 1
    post = result[0]
    assert post.external_id == "p1"
    assert post.content == "Thông báo bảo trì hệ thống"
    assert post.posted_at is not None
    assert post.like_count == 12
    assert post.comment_count == 3
    assert post.share_count == 1
    assert post.parent_external_id is None


def test_skips_post_with_empty_content_or_missing_id():
    items = [_post_item(post_id="p1", text="  "), _post_item(post_id=None)]
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect(items)):
        result = FacebookApifyCollector(_config()).collect(limit=10)

    assert result == []


def test_fetches_comments_per_post_and_links_parent_external_id():
    post_url = "https://facebook.com/TPBank/posts/p1"
    items = [_post_item(post_id="p1", url=post_url)]
    comments = {post_url: [{"commentId": "c1", "text": "Khi nào xong vậy?", "date": "2026-08-01T10:00:00Z"}]}
    with patch(
        "src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect(items, comments)
    ) as mock_run:
        result = FacebookApifyCollector(_config()).collect(limit=10)

    assert len(result) == 2
    post, comment = result
    assert post.external_id == "p1"
    assert comment.external_id == "c1"
    assert comment.content == "Khi nào xong vậy?"
    assert comment.parent_external_id == "p1"

    comment_calls = [c for c in mock_run.call_args_list if c.args[0] == DEFAULT_COMMENT_ACTOR_ID]
    assert len(comment_calls) == 1
    assert comment_calls[0].args[1]["startUrls"] == [{"url": post_url}]
    assert comment_calls[0].args[1]["resultsLimit"] == 50


def test_skips_post_without_url_but_keeps_the_post_itself():
    items = [_post_item(post_id="p1", url=None)]
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect(items)) as mock_run:
        result = FacebookApifyCollector(_config()).collect(limit=10)

    assert len(result) == 1
    assert result[0].external_id == "p1"
    comment_calls = [c for c in mock_run.call_args_list if c.args[0] == DEFAULT_COMMENT_ACTOR_ID]
    assert comment_calls == []


def test_skips_known_comment_ids():
    post_url = "https://facebook.com/TPBank/posts/p1"
    items = [_post_item(post_id="p1", url=post_url)]
    comments = {
        post_url: [
            {"commentId": "c1", "text": "đã biết"},
            {"commentId": "c2", "text": "mới"},
        ]
    }
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect(items, comments)):
        result = FacebookApifyCollector(_config()).collect(limit=10, known_ids={"c1"})

    comment_ids = [r.external_id for r in result if r.parent_external_id]
    assert comment_ids == ["c2"]


def test_custom_field_maps():
    post_url = "https://facebook.com/x/posts/1"
    items = [
        {"id": "x1", "message": "nội dung tuỳ biến", "createdAt": "2026-08-01T10:00:00Z", "link": post_url, "reactions": 7}
    ]
    comments = {post_url: [{"cid": "y1", "body": "comment tuỳ biến"}]}
    config = _config(
        post_field_map={"id": "id", "content": "message", "posted_at": "createdAt", "url": "link", "like_count": "reactions"},
        comment_field_map={"id": "cid", "content": "body"},
    )
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect(items, comments)):
        result = FacebookApifyCollector(config).collect(limit=10)

    post, comment = result
    assert post.external_id == "x1"
    assert post.content == "nội dung tuỳ biến"
    assert post.like_count == 7
    assert comment.external_id == "y1"
    assert comment.content == "comment tuỳ biến"


def test_sets_since_date_cursor_on_success_even_if_empty():
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect([])):
        collector = FacebookApifyCollector(_config())
        result = collector.collect(limit=10)

    assert result == []
    assert collector.resolved_config_update is not None
    assert "since_date" in collector.resolved_config_update


def test_does_not_advance_cursor_on_actor_failure():
    """Lỗi thật (mạng/token/API) ở actor BÀI VIẾT KHÔNG được đẩy since_date tới — nếu không lần sau
    sẽ bỏ sót vĩnh viễn khoảng thời gian của lần lỗi này (xem docstring run_apify_actor_sync)."""
    with patch("src.pipeline.collectors.facebook.run_apify_actor_sync", return_value=None):
        collector = FacebookApifyCollector(_config())
        result = collector.collect(limit=10)

    assert result == []
    assert collector.resolved_config_update is None


def test_passes_since_date_into_post_run_input_via_incremental_date_field():
    config = _config(since_date="2026-08-01T00:00:00+00:00", incremental_date_field="onlyPostsNewerThan")
    with patch(
        "src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect([])
    ) as mock_run:
        FacebookApifyCollector(config).collect(limit=10)

    called_input = mock_run.call_args.args[1]
    assert called_input["onlyPostsNewerThan"] == "2026-08-01T00:00:00+00:00"


def test_defaults_results_limit_when_not_set_in_post_run_input():
    with patch(
        "src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect([])
    ) as mock_run:
        FacebookApifyCollector(_config()).collect(limit=10)

    called_input = mock_run.call_args.args[1]
    assert called_input["resultsLimit"] == 10


def test_respects_explicit_results_limit_in_post_run_input():
    config = _config(post_run_input={"startUrls": [{"url": "x"}], "resultsLimit": 500})
    with patch(
        "src.pipeline.collectors.facebook.run_apify_actor_sync", side_effect=_run_side_effect([])
    ) as mock_run:
        FacebookApifyCollector(config).collect(limit=10)

    called_input = mock_run.call_args.args[1]
    assert called_input["resultsLimit"] == 500


def test_get_collector_dispatches_facebook():
    from src.pipeline.collectors import get_collector

    collector = get_collector("facebook", _config())
    assert isinstance(collector, FacebookApifyCollector)
