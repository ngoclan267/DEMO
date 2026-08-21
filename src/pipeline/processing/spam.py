import re

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{6,}")  # cùng 1 ký tự lặp lại >= 7 lần liên tiếp

MIN_CONTENT_LENGTH = 3
CAPS_RATIO_THRESHOLD = 0.8
CAPS_CHECK_MIN_LENGTH = 10
MAX_URLS = 2


def is_spam(text: str) -> bool:
    """Phát hiện spam bằng heuristic đơn giản, có thể giải thích được (không dùng model ML —
    việc đó thuộc về Classification Agent ở phase sau). Đánh dấu `is_spam=True` thay vì loại
    bỏ bản ghi, để không mất dữ liệu."""
    stripped = text.strip()

    if len(stripped) < MIN_CONTENT_LENGTH:
        return True

    if len(stripped) >= CAPS_CHECK_MIN_LENGTH:
        alpha_chars = [c for c in stripped if c.isalpha()]
        if alpha_chars:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio >= CAPS_RATIO_THRESHOLD:
                return True

    if _REPEATED_CHAR_RE.search(stripped):
        return True

    if len(_URL_RE.findall(stripped)) >= MAX_URLS:
        return True

    return False
