from langdetect import DetectorFactory, LangDetectException, detect

from src.config import get_settings

# langdetect dùng lấy mẫu xác suất nội bộ; cố định seed để kết quả lặp lại được giữa các lần chạy.
DetectorFactory.seed = 0

MIN_CHARS_FOR_DETECTION = 3


def detect_language(text: str) -> str:
    """Nhận diện ngôn ngữ; văn bản quá ngắn hoặc không xác định được sẽ fallback về
    ngôn ngữ mặc định của hệ thống (`default_lang`, mặc định 'vi')."""
    default_lang = get_settings().default_lang

    if not text or len(text.strip()) < MIN_CHARS_FOR_DETECTION:
        return default_lang

    try:
        return detect(text)
    except LangDetectException:
        return default_lang
