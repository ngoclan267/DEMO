from src.pipeline.processing.spam import is_spam


def test_near_empty_text_is_spam():
    assert is_spam("ok") is True


def test_normal_review_is_not_spam():
    text = "Ứng dụng dùng khá ổn định, chuyển tiền nhanh nhưng đôi khi bị lỗi đăng nhập."
    assert is_spam(text) is False


def test_excessive_caps_is_spam():
    assert is_spam("APP NAY LUA DAO KHONG NEN TAI VE DUNG NGAY LAP TUC") is True


def test_repeated_characters_is_spam():
    text = "Toi danh gia app nay rat te " + "a" * 10 + " khong nen dung"
    assert is_spam(text) is True


def test_multiple_urls_is_spam():
    text = "Xem them tai http://spam1.com va http://spam2.com nhe ban oi"
    assert is_spam(text) is True


def test_single_url_is_not_automatically_spam():
    text = "Chi tiet loi xem tai https://example.com/bug-report nhe ban"
    assert is_spam(text) is False
