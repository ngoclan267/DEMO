import logging
from dataclasses import dataclass

from src.analysis.llm import extract_text, get_analysis_llm, record_usage
from src.analysis.schemas import ClassificationResult, VerificationResult
from src.config import get_settings

logger = logging.getLogger(__name__)

# Ngưỡng confidence để tin vào Classification một mình khi Verification không tìm được nguồn nào
# (trường hợp bình thường cho đa số bug — không phải review nào cũng có văn bản chính thức nhắc tới).
CONFIDENCE_THRESHOLD_FOR_UNVERIFIED = 0.6

REASONING_PROMPT = """Bạn vừa phân tích 1 review khách hàng ngân hàng qua 2 bước:

1. Classification: chủ đề="{topic_label}", cảm xúc={sentiment}, mức độ nghiêm trọng={severity_score}, \
độ cụ thể của mô tả={content_reliability}
2. Đối chiếu văn bản chính thức: kết quả={reference_status}, nguồn tham chiếu={reference_titles}

Kết luận cuối (Consensus): {consensus_status}

Hãy viết 1-2 câu tiếng Việt giải thích ngắn gọn LÝ DO cho kết luận này, để nhân viên ngân hàng đọc \
hiểu ngay. KHÔNG nhắc tới việc "chưa xác thực/chưa xác minh" — việc xác minh danh tính khách hàng \
là bước riêng, không liên quan tới kết luận này. Review gốc: "{content}"
"""


@dataclass
class ConsensusResult:
    consensus_status: str  # confirmed | dismissed | needs_review
    reasoning: str
    final_confidence: float
    # None = chưa cross-check (case đủ rõ ràng ngay từ đầu, không cần — xem
    # graph.py::_should_cross_check). True/False = đã cross-check (xem apply_cross_check bên dưới),
    # model độc lập thứ 2 có đồng thuận hay không.
    cross_check_agreed: bool | None = None


def route_consensus_status(classification: ClassificationResult, verification: VerificationResult) -> str:
    """Quy tắc xác định consensus_status — THUẦN LOGIC, không qua LLM, để kết quả ổn định và
    test được (đúng yêu cầu: nếu mâu thuẫn thì 'cần xem xét' thay vì kết luận chắc chắn).

    CHÚ Ý: hàm này cố ý KHÔNG nhận trạng thái xác minh danh tính khách hàng làm đầu vào. Danh tính
    (predictions.verification_status) là thông tin ngữ cảnh hiển thị cho người đọc, không phải căn
    cứ suy luận — trộn 2 thứ này chính là nguyên nhân cũ khiến giao diện hiện "Chưa xác minh" cạnh
    "Xác nhận là vấn đề thật" và bị hiểu là mâu thuẫn."""
    if verification.reference_status == "conflicting":
        return "needs_review"

    if verification.reference_status == "matched":
        relations = {src.relation for src in verification.reference_sources}
        if "explains_as_policy" in relations:
            return "dismissed"  # không phải lỗi sản phẩm — là khoảng trống truyền thông chính sách
        if "confirms_issue" in relations:
            return "confirmed"
        return "needs_review"  # khớp văn bản nhưng không rõ quan hệ -> an toàn là cần xem xét

    # no_match: không có văn bản nào để đối chiếu (trường hợp phổ biến nhất). Dựa vào độ cụ thể của
    # nội dung: lời kể mơ hồ ("app tệ") không đủ căn cứ để kết luận là vấn đề thật, dù model phân
    # loại có tự tin đến đâu.
    if classification.content_reliability == "low":
        return "needs_review"
    if classification.confidence_score >= CONFIDENCE_THRESHOLD_FOR_UNVERIFIED:
        return "confirmed"
    return "needs_review"


def compute_final_confidence(
    classification: ClassificationResult, verification: VerificationResult, consensus_status: str
) -> float:
    if consensus_status == "needs_review":
        return min(classification.confidence_score, verification.reference_confidence)
    if verification.reference_status == "matched":
        return max(classification.confidence_score, verification.reference_confidence)
    return classification.confidence_score


def resolve_consensus(
    content: str, classification: ClassificationResult, verification: VerificationResult
) -> ConsensusResult:
    """Consensus Agent: đối chiếu Classification vs Verification. Routing là rule-based (xem
    route_consensus_status); LLM chỉ sinh phần giải thích (reasoning) bằng tiếng Việt."""
    consensus_status = route_consensus_status(classification, verification)
    final_confidence = compute_final_confidence(classification, verification, consensus_status)
    reasoning = _generate_reasoning(content, classification, verification, consensus_status)

    logger.info("Consensus: status=%s final_confidence=%.2f", consensus_status, final_confidence)
    return ConsensusResult(consensus_status=consensus_status, reasoning=reasoning, final_confidence=final_confidence)


def _generate_reasoning(
    content: str,
    classification: ClassificationResult,
    verification: VerificationResult,
    consensus_status: str,
) -> str:
    llm = get_analysis_llm(temperature=0.3)
    prompt = REASONING_PROMPT.format(
        topic_label=classification.topic_label,
        sentiment=classification.sentiment,
        severity_score=classification.severity_score,
        content_reliability=classification.content_reliability,
        reference_status=verification.reference_status,
        reference_titles=[src.title for src in verification.reference_sources],
        consensus_status=consensus_status,
        content=content,
    )
    response = llm.invoke(prompt)
    record_usage("consensus", response, get_settings().analysis_model_name)
    return extract_text(response.content)


def apply_cross_check(
    classification: ClassificationResult,
    verification: VerificationResult,
    consensus: ConsensusResult,
    cross_check: ClassificationResult,
) -> ConsensusResult:
    """Áp kết quả Cross-Check Agent (phân loại độc lập lần 2, xem src/analysis/cross_check.py) vào
    kết luận needs_review đã có — THUẦN LOGIC như route_consensus_status(), không qua LLM, để kết
    quả ổn định/test được.

    Cross-check CHỈ có thẩm quyền trên phần PHÂN LOẠI (sentiment/topic_label) — KHÔNG được tự ý
    "giải quyết" trường hợp needs_review phát sinh từ reference_status=="conflicting", vì đó là mâu
    thuẫn giữa các TÀI LIỆU tham chiếu, hoàn toàn ngoài phạm vi của việc phân loại lại review 1 lần
    nữa (phân loại lại 10 lần cũng không làm 2 tài liệu chính sách hết mâu thuẫn với nhau).

    - reference_status=="conflicting": giữ nguyên needs_review, chỉ bổ sung ghi chú minh bạch là đã
      cross-check (không đổi kết luận).
    - 2 model ĐỒNG THUẬN (cùng sentiment VÀ cùng topic_label): nâng lên "confirmed" — 2 model độc
      lập cùng kết luận là tín hiệu mạnh hơn hẳn 1 model tự tin một mình.
    - 2 model BẤT ĐỒNG: giữ nguyên "needs_review", nhưng ghi rõ ĐIỂM bất đồng trong reasoning — tín
      hiệu cụ thể hơn hẳn cho người xem lại, thay vì chỉ 1 câu chung chung như trước khi có
      cross-check."""
    agreed = classification.sentiment == cross_check.sentiment and classification.topic_label == cross_check.topic_label

    if verification.reference_status == "conflicting":
        note = (
            " [Cross-check: đã đối chiếu bằng model độc lập thứ 2, nhưng vẫn cần xem xét vì tài "
            "liệu tham chiếu mâu thuẫn nhau — việc này ngoài phạm vi phân loại lại.]"
        )
        return ConsensusResult(
            consensus_status=consensus.consensus_status,
            reasoning=consensus.reasoning + note,
            final_confidence=consensus.final_confidence,
            cross_check_agreed=agreed,
        )

    if agreed:
        note = (
            f' [Cross-check: model độc lập thứ 2 đồng thuận (cùng "{cross_check.sentiment}" / '
            f'"{cross_check.topic_label}") — nâng độ tin cậy.]'
        )
        return ConsensusResult(
            consensus_status="confirmed",
            reasoning=consensus.reasoning + note,
            final_confidence=max(consensus.final_confidence, cross_check.confidence_score),
            cross_check_agreed=True,
        )

    note = (
        f' [Cross-check: model độc lập thứ 2 KHÔNG đồng thuận (kết quả khác: "{cross_check.sentiment}" / '
        f'"{cross_check.topic_label}") — cần người xem lại trực tiếp.]'
    )
    return ConsensusResult(
        consensus_status="needs_review",
        reasoning=consensus.reasoning + note,
        final_confidence=min(consensus.final_confidence, cross_check.confidence_score),
        cross_check_agreed=False,
    )
