import uuid
from datetime import UTC, datetime, timedelta

from src.pipeline.processing.cross_topic_dedup import group_followers, source_identity


def _id() -> uuid.UUID:
    return uuid.uuid4()


def test_source_identity_google_play_uses_package_name():
    assert source_identity("google_play", {"package_name": "com.tpb.mb.gprsandroid"}) == "com.tpb.mb.gprsandroid"


def test_source_identity_app_store_uses_app_id():
    assert source_identity("app_store", {"app_id": "450464147"}) == "450464147"


def test_source_identity_unresolved_config_returns_none():
    """Source vẫn còn ở dạng {"query": "..."} (chưa tự resolve được package_name/app_id thật) thì
    chưa xác định được định danh — không được coi là trùng với source khác một cách vội vàng."""
    assert source_identity("google_play", {"query": "TPBank Mobile"}) is None


def test_source_identity_unsupported_type_returns_none():
    assert source_identity("bank_website", {"seed_urls": ["http://tpb.vn"]}) is None
    assert source_identity("facebook", {"page_url": "https://facebook.com/tpbank"}) is None


def test_group_followers_picks_earliest_as_canonical():
    now = datetime.now(UTC)
    older, newer, newest = _id(), _id(), _id()
    sources = [
        (newer, "google_play", {"package_name": "vn.shb.saha.mbanking"}, now),
        (older, "google_play", {"package_name": "vn.shb.saha.mbanking"}, now - timedelta(days=2)),
        (newest, "google_play", {"package_name": "vn.shb.saha.mbanking"}, now + timedelta(days=1)),
    ]

    followers = group_followers(sources)

    assert followers == {newer: older, newest: older}
    assert older not in followers


def test_group_followers_ignores_solo_sources():
    """Source không trùng định danh với ai không xuất hiện trong kết quả — vẫn tự crawl bình
    thường (không phải follower của chính nó)."""
    now = datetime.now(UTC)
    solo = _id()
    sources = [(solo, "google_play", {"package_name": "com.tpb.mb.gprsandroid"}, now)]

    assert group_followers(sources) == {}


def test_group_followers_does_not_cross_source_types():
    """Cùng chuỗi định danh nhưng KHÁC loại nguồn (vd trùng tình cờ) không được coi là cùng 1 app —
    package_name và app_id là 2 không gian định danh độc lập."""
    now = datetime.now(UTC)
    gp_id, as_id = _id(), _id()
    sources = [
        (gp_id, "google_play", {"package_name": "450464147"}, now),
        (as_id, "app_store", {"app_id": "450464147"}, now - timedelta(days=1)),
    ]

    assert group_followers(sources) == {}


def test_group_followers_keeps_separate_groups_for_different_apps():
    now = datetime.now(UTC)
    tpb_old, tpb_new = _id(), _id()
    shb_old, shb_new = _id(), _id()
    sources = [
        (tpb_new, "google_play", {"package_name": "com.tpb.mb.gprsandroid"}, now),
        (tpb_old, "google_play", {"package_name": "com.tpb.mb.gprsandroid"}, now - timedelta(days=1)),
        (shb_new, "google_play", {"package_name": "vn.shb.saha.mbanking"}, now),
        (shb_old, "google_play", {"package_name": "vn.shb.saha.mbanking"}, now - timedelta(days=1)),
    ]

    followers = group_followers(sources)

    assert followers == {tpb_new: tpb_old, shb_new: shb_old}
