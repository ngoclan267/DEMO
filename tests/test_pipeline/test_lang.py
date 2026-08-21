from src.pipeline.processing.lang import detect_language


def test_detects_vietnamese():
    text = "Ứng dụng chuyển tiền rất nhanh nhưng thỉnh thoảng bị lỗi đăng nhập vào buổi tối."
    assert detect_language(text) == "vi"


def test_detects_english():
    text = "This banking app is great but it crashes every time I try to log in on Android."
    assert detect_language(text) == "en"


def test_short_text_falls_back_to_default():
    assert detect_language("ok") == "vi"


def test_empty_text_falls_back_to_default():
    assert detect_language("") == "vi"
