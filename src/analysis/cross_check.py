import logging

from src.analysis.classification import CLASSIFICATION_PROMPT
from src.analysis.llm import get_cross_check_llm, peek_model_for, record_usage
from src.analysis.schemas import ClassificationResult

logger = logging.getLogger(__name__)


def cross_check_classification(content: str) -> ClassificationResult | None:
    """Cross-Check Agent: phân loại ĐỘC LẬP lần 2 bằng model KHÁC HỌ với model đã phân loại lần đầu
    (Gemini <-> Gemma — xem get_cross_check_llm/peek_model_for trong src/analysis/llm.py) — dùng
    LẠI đúng CLASSIFICATION_PROMPT của Classification Agent (hỏi đúng 1 câu hỏi, chỉ khác model trả
    lời) để 2 kết quả thực sự so sánh được với nhau.

    CHỈ được gọi khi Consensus đã kết luận "needs_review" (xem graph.py::_should_cross_check) —
    không chạy cho MỌI post để không tốn quota vô ích trên các case đã đủ rõ ràng ngay từ đầu.

    Trả về None nếu cross-check không khả dụng (không có model nào thuộc họ đối lập được cấu hình)
    hoặc bản thân lượt gọi này lỗi/trả JSON không khớp schema — caller PHẢI coi None là "giữ nguyên
    kết quả cũ", không phải lỗi cần huỷ post (khác hẳn classify/verify/consensus, nơi lỗi = huỷ cả
    post) vì cross-check là lớp kiểm tra BỔ SUNG, không phải bước bắt buộc của pipeline chính."""
    primary_model = peek_model_for("classification")
    llm = get_cross_check_llm(primary_model, ClassificationResult, include_raw=True)
    if llm is None:
        return None
    try:
        response = llm.invoke(CLASSIFICATION_PROMPT.format(content=content))
    except Exception:
        logger.warning("Cross-Check Agent lỗi khi gọi model độc lập — bỏ qua, giữ nguyên kết luận gốc", exc_info=True)
        return None
    if response.get("parsing_error") is not None:
        logger.warning("Cross-Check Agent: model độc lập trả JSON không khớp schema — bỏ qua")
        return None
    result = response["parsed"]
    record_usage("cross_check", response.get("raw"), primary_model or "unknown")
    return result
