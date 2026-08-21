from src.analysis.consensus import compute_final_confidence, route_consensus_status
from src.analysis.schemas import ClassificationResult, ReferenceSource, VerificationResult


def _classification(**overrides) -> ClassificationResult:
    defaults = {
        "sentiment": "negative",
        "topic_label": "khóa tài khoản",
        "severity_score": 0.8,
        "confidence_score": 0.9,
        "content_reliability": "high",
        "is_question": False,
    }
    defaults.update(overrides)
    return ClassificationResult(**defaults)


def _verification(**overrides) -> VerificationResult:
    defaults = {
        "reference_status": "no_match",
        "reference_sources": [],
        "reference_confidence": 0.5,
    }
    defaults.update(overrides)
    return VerificationResult(**defaults)


def test_conflicting_reference_always_needs_review():
    result = route_consensus_status(_classification(), _verification(reference_status="conflicting"))
    assert result == "needs_review"


def test_matched_policy_explanation_is_dismissed():
    verification = _verification(
        reference_status="matched",
        reference_sources=[
            ReferenceSource(
                doc_id="circular-17-2024", title="Thông tư 17/2024", url="https://x", relation="explains_as_policy"
            )
        ],
    )
    assert route_consensus_status(_classification(), verification) == "dismissed"


def test_matched_confirmed_issue_is_confirmed():
    verification = _verification(
        reference_status="matched",
        reference_sources=[
            ReferenceSource(doc_id="outage-notice", title="Thông báo sự cố", url="https://x", relation="confirms_issue")
        ],
    )
    assert route_consensus_status(_classification(), verification) == "confirmed"


def test_no_match_with_high_confidence_is_confirmed():
    classification = _classification(confidence_score=0.8)
    assert route_consensus_status(classification, _verification()) == "confirmed"


def test_no_match_with_low_confidence_needs_review():
    classification = _classification(confidence_score=0.3)
    assert route_consensus_status(classification, _verification()) == "needs_review"


def test_no_match_with_vague_content_needs_review_despite_high_confidence():
    """Lời kể mơ hồ ("app tệ") không đủ căn cứ kết luận là vấn đề thật, dù model rất tự tin khi
    phân loại nó vào một nhóm chủ đề."""
    classification = _classification(confidence_score=0.95, content_reliability="low")
    assert route_consensus_status(classification, _verification()) == "needs_review"


def test_identity_verification_never_affects_conclusion():
    """Xác minh danh tính khách hàng (predictions.verification_status) KHÔNG phải đầu vào của
    kết luận — đây chính là chỗ trước đây bị trộn lẫn, khiến giao diện hiện "Chưa xác minh" cạnh
    "Xác nhận là vấn đề thật" và bị đọc thành mâu thuẫn. Ràng buộc bằng test: route_consensus_status
    không nhận tham số danh tính nào, nên cùng đầu vào phải luôn cho cùng kết quả."""
    import inspect

    params = set(inspect.signature(route_consensus_status).parameters)
    assert params == {"classification", "verification"}
    assert not hasattr(_verification(), "verification_status")


def test_final_confidence_needs_review_takes_min():
    classification = _classification(confidence_score=0.9)
    verification = _verification(reference_status="conflicting", reference_confidence=0.4)
    assert compute_final_confidence(classification, verification, "needs_review") == 0.4


def test_final_confidence_matched_takes_max():
    classification = _classification(confidence_score=0.6)
    verification = _verification(reference_status="matched", reference_confidence=0.95)
    assert compute_final_confidence(classification, verification, "confirmed") == 0.95
