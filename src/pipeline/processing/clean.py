import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(raw: str) -> str:
    """Làm sạch văn bản thô: bỏ thẻ HTML, giải mã HTML entity, chuẩn hóa Unicode (NFC),
    và gộp khoảng trắng thừa."""
    if not raw:
        return ""

    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text
