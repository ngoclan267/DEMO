from src.pipeline.processing.priority import estimate_priority


def test_estimate_priority_zero_for_neutral_content():
    assert estimate_priority("Ứng dụng ổn định, không có gì để phàn nàn", {}) == 0.0


def test_estimate_priority_boosted_by_negative_keywords():
    score = estimate_priority("App lỗi liên tục, bị trừ tiền mà giao dịch không thành công, quá tệ", {})
    assert score > 0.0


def test_estimate_priority_boosted_by_claim_signal():
    score_with_claim = estimate_priority("Ngân hàng thu phí 50k mà không thông báo trước, đúng là lãi suất cắt cổ", {})
    score_without_claim = estimate_priority("Ứng dụng dùng bình thường", {})
    assert score_with_claim > score_without_claim


def test_estimate_priority_boosted_by_low_rating_google_play():
    low = estimate_priority("bình thường", {"score": 1})
    high_rating = estimate_priority("bình thường", {"score": 5})
    assert low > high_rating


def test_estimate_priority_boosted_by_low_rating_app_store():
    low = estimate_priority("bình thường", {"im:rating": {"label": "1"}})
    high_rating = estimate_priority("bình thường", {"im:rating": {"label": "5"}})
    assert low > high_rating


def test_estimate_priority_capped_at_one():
    content = "lỗi mất tiền lừa đảo tệ chậm không nhận được trừ tiền khóa tài khoản " * 5
    score = estimate_priority(content, {"score": 1})
    assert score <= 1.0


def test_estimate_priority_handles_missing_raw():
    assert estimate_priority("nội dung bất kỳ", None) >= 0.0
