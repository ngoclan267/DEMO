from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.collectors import get_collector
from src.pipeline.collectors.app_store import SEARCH_URL, AppStoreCollector
from src.pipeline.collectors.google_play import GooglePlayCollector
from src.pipeline.collectors.linkedin import LinkedInCollector


def test_google_play_collector_maps_reviews_and_skips_empty_content():
    fake_reviews = [
        {"reviewId": "r1", "content": "App tốt nhưng đăng nhập chậm", "at": datetime(2026, 1, 1), "score": 4},
        {"reviewId": "r2", "content": "   ", "at": datetime(2026, 1, 2), "score": 1},
    ]

    with patch("src.pipeline.collectors.google_play.reviews", return_value=(fake_reviews, None)) as mock_reviews:
        collector = GooglePlayCollector({"package_name": "vn.shb.saha.mbanking"})
        result = collector.collect(limit=50)

    assert mock_reviews.call_args.kwargs["count"] == 50
    assert len(result) == 1
    assert result[0].external_id == "r1"
    assert result[0].content == "App tốt nhưng đăng nhập chậm"
    assert result[0].raw["score"] == 4


def test_google_play_collector_survives_source_structure_change():
    """Rủi ro: Google Play đổi cấu trúc review (field bị đổi tên/xóa) — 1 review lỗi cấu trúc chỉ
    được mất chính nó, không được kéo mất luôn các review hợp lệ khác trong cùng batch."""
    malformed_batch = [
        {"reviewId": "r1", "content": "App tốt", "at": None},
        {"content": "Thiếu reviewId do đổi cấu trúc API"},  # thiếu "reviewId"
        {"reviewId": "r3", "content": "App ổn", "at": None},
    ]

    with patch("src.pipeline.collectors.google_play.reviews", return_value=(malformed_batch, None)):
        collector = GooglePlayCollector({"package_name": "test.pkg"})
        result = collector.collect(limit=10)

    assert [r.external_id for r in result] == ["r1", "r3"]


def test_google_play_collector_requires_package_name():
    collector = GooglePlayCollector({})
    with pytest.raises(ValueError):
        collector.collect()


def test_google_play_collector_resolves_package_name_via_query():
    # Lần search đầu (đúng tên app) mô phỏng "hero card" của Google Play — không có appId.
    # Lần search thứ hai (tên ngân hàng + hậu tố) mới ra appId thật, giống hành vi thực tế đã
    # kiểm chứng thủ công với "TPBank Mobile".
    hero_card_results = [{"appId": None, "title": "TPBank Mobile", "developer": "TPBank"}]
    resolved_results = [{"appId": "com.tpb.mb.gprsandroid", "title": "TPBank Mobile", "developer": "TPBank"}]
    fake_reviews = [{"reviewId": "r1", "content": "Ổn định", "at": datetime(2026, 1, 1)}]

    with (
        patch(
            "src.pipeline.collectors.google_play.search", side_effect=[hero_card_results, resolved_results]
        ) as mock_search,
        patch("src.pipeline.collectors.google_play.reviews", return_value=(fake_reviews, None)) as mock_reviews,
    ):
        collector = GooglePlayCollector({"query": "TPBank Mobile", "lang": "vi", "country": "vn"})
        result = collector.collect(limit=10)

    assert len(result) == 1
    assert mock_reviews.call_args.args[0] == "com.tpb.mb.gprsandroid"
    assert mock_search.call_count == 2


def test_google_play_collector_paginates_across_batches_using_continuation_token():
    batch1 = [{"reviewId": f"r{i}", "content": f"noi dung {i}", "at": datetime(2026, 1, 1)} for i in range(3)]
    batch2 = [{"reviewId": f"r{i}", "content": f"noi dung {i}", "at": datetime(2026, 1, 1)} for i in range(3, 5)]
    token = object()

    with patch(
        "src.pipeline.collectors.google_play.reviews",
        side_effect=[(batch1, token), (batch2, None)],
    ) as mock_reviews:
        collector = GooglePlayCollector({"package_name": "vn.shb.saha.mbanking"})
        result = collector.collect(limit=10)

    assert len(result) == 5
    assert mock_reviews.call_count == 2
    assert mock_reviews.call_args_list[1].kwargs["continuation_token"] is token


def test_google_play_collector_stops_early_when_batch_fully_known():
    batch = [{"reviewId": "r1", "content": "cũ rồi", "at": datetime(2026, 1, 1)}]

    with patch(
        "src.pipeline.collectors.google_play.reviews", return_value=(batch, object())
    ) as mock_reviews:
        collector = GooglePlayCollector({"package_name": "vn.shb.saha.mbanking"})
        result = collector.collect(limit=100, known_ids={"r1"})

    assert result == []
    mock_reviews.assert_called_once()


def test_google_play_collector_returns_empty_when_query_unresolvable():
    no_match_results = [{"appId": None, "title": "Something else", "developer": "X"}]

    with (
        patch("src.pipeline.collectors.google_play.search", return_value=no_match_results),
        patch("src.pipeline.collectors.google_play.reviews") as mock_reviews,
    ):
        collector = GooglePlayCollector({"query": "TPBank Mobile"})
        result = collector.collect()

    assert result == []
    mock_reviews.assert_not_called()


def _fake_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_app_store_collector_maps_reviews_and_skips_non_review_entries():
    review_entry = {
        "id": {"label": "999"},
        "author": {"name": {"label": "user1"}},
        "im:rating": {"label": "5"},
        "title": {"label": "Tuyệt vời"},
        "content": {"label": "Ứng dụng dễ dùng"},
        "updated": {"label": "2026-08-06T09:33:59-07:00"},
    }
    non_review_entry = {"im:name": {"label": "SHB Saha"}}  # entry app-level, không phải review
    page1 = _fake_response({"feed": {"entry": [non_review_entry, review_entry]}})
    empty_page = _fake_response({"feed": {"entry": []}})

    with patch("httpx.Client.get", side_effect=[page1, empty_page]):
        collector = AppStoreCollector({"app_id": "1661457183", "country": "vn"})
        result = collector.collect(limit=10)

    assert len(result) == 1
    assert result[0].external_id == "999"
    assert result[0].content == "Tuyệt vời\nỨng dụng dễ dùng"
    assert result[0].posted_at == datetime(2026, 8, 6, 9, 33, 59, tzinfo=timezone(timedelta(hours=-7)))


def test_app_store_collector_handles_missing_or_malformed_updated_field():
    missing_updated = {
        "id": {"label": "1"},
        "author": {"name": {"label": "u1"}},
        "im:rating": {"label": "5"},
        "content": {"label": "OK"},
    }
    malformed_updated = {
        "id": {"label": "2"},
        "author": {"name": {"label": "u2"}},
        "im:rating": {"label": "4"},
        "content": {"label": "Fine"},
        "updated": {"label": "not-a-date"},
    }
    page1 = _fake_response({"feed": {"entry": [missing_updated, malformed_updated]}})
    empty_page = _fake_response({"feed": {"entry": []}})

    with patch("httpx.Client.get", side_effect=[page1, empty_page]):
        collector = AppStoreCollector({"app_id": "1661457183", "country": "vn"})
        result = collector.collect(limit=10)

    assert len(result) == 2
    assert all(post.posted_at is None for post in result)


def test_app_store_collector_retries_transiently_empty_first_page():
    review_entry = {
        "id": {"label": "1"},
        "author": {"name": {"label": "u"}},
        "im:rating": {"label": "5"},
        "title": {"label": "Tot"},
        "content": {"label": "Ổn định"},
    }
    empty_first_attempt = _fake_response({"feed": {"entry": []}})
    populated_retry = _fake_response({"feed": {"entry": [review_entry]}})
    empty_page2 = _fake_response({"feed": {"entry": []}})

    with (
        patch("httpx.Client.get", side_effect=[empty_first_attempt, populated_retry, empty_page2]),
        patch("src.pipeline.collectors.app_store.time.sleep"),
    ):
        collector = AppStoreCollector({"app_id": "123", "country": "vn"})
        result = collector.collect(limit=10)

    assert len(result) == 1
    assert result[0].external_id == "1"


def test_app_store_collector_stops_early_when_page_fully_known():
    review_entry = {
        "id": {"label": "1"},
        "author": {"name": {"label": "u"}},
        "im:rating": {"label": "5"},
        "title": {"label": "Tot"},
        "content": {"label": "Ổn định"},
    }
    page1 = _fake_response({"feed": {"entry": [review_entry]}})

    with patch("httpx.Client.get", return_value=page1) as mock_get:
        collector = AppStoreCollector({"app_id": "123", "country": "vn"})
        result = collector.collect(limit=100, known_ids={"1"})

    assert result == []
    assert mock_get.call_count == 1


def test_app_store_collector_requires_app_id():
    collector = AppStoreCollector({})
    with pytest.raises(ValueError):
        collector.collect()


def test_app_store_collector_resolves_app_id_via_query():
    search_response = _fake_response(
        {"results": [{"trackId": 450464147, "trackName": "TPBank Mobile", "sellerName": "TienPhong Bank"}]}
    )
    review_entry = {
        "id": {"label": "1"},
        "author": {"name": {"label": "u"}},
        "im:rating": {"label": "5"},
        "title": {"label": "Tot"},
        "content": {"label": "Ổn định"},
    }
    page1 = _fake_response({"feed": {"entry": [review_entry]}})
    empty_page = _fake_response({"feed": {"entry": []}})

    with patch("httpx.Client.get", side_effect=[search_response, page1, empty_page]) as mock_get:
        collector = AppStoreCollector({"query": "TPBank Mobile", "country": "vn"})
        result = collector.collect(limit=10)

    assert len(result) == 1
    assert result[0].external_id == "1"
    first_call = mock_get.call_args_list[0]
    assert first_call.args[0] == SEARCH_URL


def test_app_store_collector_returns_empty_when_query_unresolvable():
    search_response = _fake_response({"results": []})

    with patch("httpx.Client.get", return_value=search_response):
        collector = AppStoreCollector({"query": "NoSuchBank"})
        result = collector.collect()

    assert result == []


def test_linkedin_collector_returns_empty_stub():
    collector = LinkedInCollector({"any": "config"})
    assert collector.collect() == []


def test_get_collector_dispatches_by_source_type():
    collector = get_collector("google_play", {"package_name": "x"})
    assert isinstance(collector, GooglePlayCollector)


def test_get_collector_raises_for_unknown_type():
    with pytest.raises(ValueError):
        get_collector("unknown_source", {})
