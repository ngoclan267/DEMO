import logging

from src.analysis.llm import get_structured_analysis_llm, record_usage
from src.analysis.schemas import ClassificationResult, SUGGESTED_TOPIC_LABELS
from src.config import get_settings

logger = logging.getLogger(__name__)

# Chèn vào CLASSIFICATION_PROMPT qua .replace() (không phải .format()) bên dưới — CLASSIFICATION_
# PROMPT vẫn cần giữ nguyên "{content}" làm placeholder cho .format(content=...) ở classify_post()
# VÀ ở cross_check.py (import thẳng constant này) — dùng chung 1 lượt .format() thứ 2 sẽ vỡ nếu
# format() ở đây đã "tiêu thụ" luôn dấu ngoặc nhọn.
_SUGGESTED_TOPIC_LIST = "\n".join(f"   - {label}" for label in SUGGESTED_TOPIC_LABELS)

CLASSIFICATION_PROMPT = """Bạn là chuyên gia phân tích phản hồi khách hàng cho ứng dụng ngân hàng \
di động tại Việt Nam. Đọc review dưới đây và phân loại theo đúng các tiêu chí:

1. sentiment: cảm xúc tổng thể (positive/neutral/negative)
2. topic_label: chủ đề CHÍNH của review. ƯU TIÊN chọn ĐÚNG MỘT trong các nhóm gợi ý sau nếu review \
thực sự khớp:
__SUGGESTED_TOPIC_LIST__
   Nếu review KHÔNG thực sự thuộc nhóm nào ở trên (vd bảo mật/xác thực OTP, tính năng mới, khuyến \
mãi/ưu đãi, giao diện/thiết kế, hiệu năng ứng dụng...), hãy tự đặt 1 nhãn chủ đề MỚI ngắn gọn (2-4 \
từ tiếng Việt, dạng cụm danh từ, viết thường) mô tả đúng bản chất vấn đề — nhiều review khác nhau \
nói CÙNG 1 vấn đề PHẢI dùng lại CÙNG 1 nhãn (nhãn này là khoá để gom nhóm Pain Point — đặt nhãn \
không nhất quán sẽ làm vỡ vụn 1 vấn đề thành nhiều nhóm nhỏ). KHÔNG ép review không thực sự liên \
quan vào 1 nhóm gợi ý chỉ vì phải chọn.
3. severity_score (0.0-1.0): mức độ nghiêm trọng của vấn đề đối với người dùng/ngân hàng
4. confidence_score (0.0-1.0): mức độ tự tin của bạn vào kết quả phân loại này
5. content_reliability: độ tin cậy của NỘI DUNG review, dựa DUY NHẤT trên tính cụ thể của mô tả.
   Đây KHÔNG phải đánh giá người viết có thật hay không — chỉ xét lời kể có đủ chi tiết để đội
   kỹ thuật lần ra vấn đề hay không:
   - high: nêu chi tiết kiểm chứng được — thao tác cụ thể, thời điểm, mã lỗi, số tiền, tên tính
     năng, thiết bị (vd "chuyển tiền 2 triệu lúc 9h sáng báo lỗi TR-05, trừ tiền nhưng không tới")
   - medium: có mô tả hiện tượng nhưng thiếu chi tiết (vd "hay bị văng khi mở app")
   - low: chung chung/cảm tính, không mô tả hiện tượng nào (vd "app tệ", "chán", "1 sao")
6. is_question: true nếu nội dung CHỦ YẾU là một câu hỏi/thắc mắc của khách (vd "app này có thu phí
   gì không?", "sao chưa thấy tiền về tài khoản?"), false nếu là nhận xét/phàn nàn/khen chê thông
   thường — ĐỘC LẬP với sentiment, 1 câu hỏi vẫn có thể mang giọng điệu tiêu cực/tích cực.

Review: "{content}"
""".replace("__SUGGESTED_TOPIC_LIST__", _SUGGESTED_TOPIC_LIST)


def classify_post(content: str) -> ClassificationResult:
    """Classification Agent: sentiment, chủ đề (ưu tiên 1 trong các nhóm gợi ý — xem
    SUGGESTED_TOPIC_LABELS — nhưng có thể tự đặt nhãn mới nếu hợp lý hơn), mức nghiêm trọng, độ
    tin cậy phân loại, và độ tin cậy nội dung.

    content_reliability được sinh CHUNG trong lượt gọi LLM này (thay vì tách agent riêng) vì quota
    Gemini free-tier là nút thắt thật của hệ thống — thêm 1 lượt gọi/post sẽ tăng ~33% lượng
    request mỗi chu kỳ mà không thêm thông tin nào mà model chưa đọc được ở đây."""
    llm = get_structured_analysis_llm(ClassificationResult, include_raw=True)
    response = llm.invoke(CLASSIFICATION_PROMPT.format(content=content))
    if response.get("parsing_error") is not None:
        # include_raw=True KHÔNG tự raise khi model trả JSON không khớp schema (khác hành vi mặc
        # định) — tự raise lại để giữ nguyên hành vi cũ, caller (graph.py::classify_node) đã có
        # try/except bao quanh coi đây là lỗi phân tích.
        raise response["parsing_error"]
    result = response["parsed"]
    record_usage("classification", response.get("raw"), get_settings().analysis_model_name)

    logger.info(
        "Classification: topic=%s sentiment=%s severity=%.2f confidence=%.2f reliability=%s",
        result.topic_label,
        result.sentiment,
        result.severity_score,
        result.confidence_score,
        result.content_reliability,
    )
    return result
