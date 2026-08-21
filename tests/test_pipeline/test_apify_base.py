from unittest.mock import MagicMock, patch

from src.pipeline.collectors.apify_base import run_apify_actor_sync


def _fake_settings(token: str) -> MagicMock:
    settings = MagicMock()
    settings.apify_api_token = token
    return settings


def _fake_response(items) -> MagicMock:
    response = MagicMock()
    response.json.return_value = items
    response.raise_for_status.return_value = None
    return response


def test_returns_none_without_token():
    with patch("src.pipeline.collectors.apify_base.get_settings", return_value=_fake_settings("")):
        result = run_apify_actor_sync("apify/facebook-comments-scraper", {"startUrls": []})
    assert result is None


def test_calls_correct_url_and_replaces_slash_with_tilde():
    with (
        patch("src.pipeline.collectors.apify_base.get_settings", return_value=_fake_settings("tok")),
        patch("httpx.Client.post", return_value=_fake_response([{"text": "ok"}])) as mock_post,
    ):
        result = run_apify_actor_sync("apify/facebook-comments-scraper", {"resultsLimit": 5})

    assert result == [{"text": "ok"}]
    call_args = mock_post.call_args
    assert call_args.args[0] == "https://api.apify.com/v2/actors/apify~facebook-comments-scraper/run-sync-get-dataset-items"
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
    assert call_args.kwargs["json"] == {"resultsLimit": 5}


def test_returns_none_on_request_error():
    with (
        patch("src.pipeline.collectors.apify_base.get_settings", return_value=_fake_settings("tok")),
        patch("httpx.Client.post", side_effect=Exception("network error")),
    ):
        result = run_apify_actor_sync("apify/facebook-comments-scraper", {})
    assert result is None


def test_returns_none_when_response_not_a_list():
    with (
        patch("src.pipeline.collectors.apify_base.get_settings", return_value=_fake_settings("tok")),
        patch("httpx.Client.post", return_value=_fake_response({"error": "unexpected"})),
    ):
        result = run_apify_actor_sync("apify/facebook-comments-scraper", {})
    assert result is None
