import logging

from src.analysis.knowledge_base.loader import KnowledgeDoc, format_knowledge_base_for_prompt, load_knowledge_base
from src.analysis.llm import get_structured_analysis_llm, record_usage
from src.analysis.schemas import VerificationResult
from src.config import get_settings

logger = logging.getLogger(__name__)

VERIFICATION_PROMPT = """Bạn là chuyên gia đối chiếu thông tin cho ngân hàng. Dưới đây là một \
review của khách hàng và một kho tài liệu tham chiếu (quy định của Ngân hàng Nhà nước, thông báo \
chính thức của ngân hàng). Nhiệm vụ: xác định xem review này có được giải thích bởi tài liệu nào \
trong kho hay không.

QUAN TRỌNG:
- Nếu tìm được tài liệu giải thích đây là hành vi ĐÚNG THEO QUY ĐỊNH/CHÍNH SÁCH đã biết (không \
phải lỗi ứng dụng) -> reference_status="matched", relation="explains_as_policy".
- Nếu tìm được tài liệu XÁC NHẬN đây là sự cố/vấn đề có thật đã được ghi nhận chính thức -> \
reference_status="matched", relation="confirms_issue".
- Nếu KHÔNG tìm được tài liệu nào thực sự liên quan -> reference_status="no_match", \
reference_sources=[]. Đây là kết quả BÌNH THƯỜNG cho phần lớn review (lỗi kỹ thuật thông thường \
không có văn bản chính thức nào nhắc tới) — không được cố gán ép một tài liệu không thực sự liên quan.
- Nếu các tài liệu tìm được mâu thuẫn nhau về cách giải thích -> reference_status="conflicting".

CHÚ Ý: nhiệm vụ của bạn CHỈ là đối chiếu với kho văn bản. Không đánh giá người viết review có phải \
khách hàng thật hay không — việc đó thuộc bước xác minh danh tính qua CRM, nằm ngoài phạm vi này.

Chủ đề đã phân loại: {topic_label}

Review: "{content}"

Kho tài liệu tham chiếu:
{knowledge_base}
"""


def verify_post(content: str, topic_label: str, topic_docs: list[KnowledgeDoc] | None = None) -> VerificationResult:
    """Verification Agent: đối chiếu review với kho tài liệu tham chiếu (quy định NHNN, thông báo
    chính thức ngân hàng) — kho nhỏ nên đưa thẳng vào prompt, không cần bước retrieval riêng.

    `topic_docs`: tài liệu crawl được từ website CHÍNH ngân hàng đang xét (đã lọc còn liên quan qua
    select_relevant_docs), gộp thêm vào kho tĩnh toàn cục bên dưới. None (mặc định) giữ nguyên hành
    vi cũ — chỉ dùng kho tĩnh, để không phá vỡ các lệnh gọi/test hiện có.

    Đây là đối chiếu VĂN BẢN, không phải xác minh danh tính khách hàng."""
    combined_docs = load_knowledge_base() + (topic_docs or [])

    llm = get_structured_analysis_llm(VerificationResult, include_raw=True)
    prompt = VERIFICATION_PROMPT.format(
        topic_label=topic_label,
        content=content,
        knowledge_base=format_knowledge_base_for_prompt(combined_docs),
    )
    response = llm.invoke(prompt)
    if response.get("parsing_error") is not None:
        raise response["parsing_error"]
    result = response["parsed"]
    record_usage("verification", response.get("raw"), get_settings().analysis_model_name)

    logger.info(
        "Reference check: status=%s nguồn=%d confidence=%.2f",
        result.reference_status,
        len(result.reference_sources),
        result.reference_confidence,
    )
    return result
