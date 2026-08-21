from src.pipeline.processing.clean import clean_text


def test_strips_html_tags():
    assert clean_text("<p>Ứng dụng <b>rất tốt</b></p>") == "Ứng dụng rất tốt"


def test_unescapes_html_entities():
    assert clean_text("Kh&ocirc;ng &amp; kh&ocirc;ng") == "Không & không"


def test_collapses_whitespace():
    assert clean_text("  App   lỗi\n\n đăng nhập  ") == "App lỗi đăng nhập"


def test_empty_input_returns_empty_string():
    assert clean_text("") == ""
    assert clean_text(None) == ""
