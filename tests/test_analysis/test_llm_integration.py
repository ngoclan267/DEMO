"""Test gọi LLM (Gemini) thật — bỏ qua tự động nếu chưa cấu hình GEMINI_API_KEY thật, cùng kiểu
với tests/test_db/test_models.py (Postgres thật) ở Phase 1.

Kịch bản chính theo đúng yêu cầu: "tin đồn/chính sách mới" — khách phàn nàn tài khoản bị khoá,
nhưng thực ra là do quy định xác thực sinh trắc học (Thông tư 17/2024/TT-NHNN) chứ không phải bug.
"""

import pytest

from src.analysis.classification import classify_post
from src.analysis.graph import analysis_graph
from src.analysis.verification import verify_post
from src.config import get_settings

_settings = get_settings()
pytestmark = pytest.mark.skipif(
    not _settings.gemini_api_key or _settings.gemini_api_key == "your-gemini-key-here",
    reason="Chưa cấu hình GEMINI_API_KEY thật — bỏ qua test gọi LLM thật",
)

ACCOUNT_LOCKED_REVIEW = "Tài khoản tôi tự nhiên bị khóa, không đăng nhập được, không hiểu lý do gì!"
GENUINE_BUG_REVIEW = "App bị crash liên tục mỗi khi tôi bấm chuyển tiền, rất khó chịu."


def test_classification_returns_valid_structured_output():
    result = classify_post(ACCOUNT_LOCKED_REVIEW)
    # topic_label không còn là tập đóng (xem src/analysis/schemas.py::SUGGESTED_TOPIC_LABELS) —
    # chỉ kiểm tra đúng contract schema (chuỗi ngắn gọn, không rỗng), không assert membership vào
    # 1 danh sách cố định. Review này là ca "khoá tài khoản" rõ ràng nên model vẫn nên chọn đúng
    # nhãn gợi ý đó trong thực tế, nhưng test không ép cứng điều đó.
    assert 0 < len(result.topic_label) <= 50
    assert result.sentiment in {"positive", "neutral", "negative"}
    assert 0.0 <= result.severity_score <= 1.0
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.content_reliability in {"high", "medium", "low"}


def test_verification_finds_policy_explanation_for_account_lockout():
    result = verify_post(ACCOUNT_LOCKED_REVIEW, topic_label="khóa tài khoản")
    assert result.reference_status == "matched"
    assert any(src.relation == "explains_as_policy" for src in result.reference_sources)


def test_verification_finds_nothing_for_generic_bug():
    result = verify_post(GENUINE_BUG_REVIEW, topic_label="lỗi ứng dụng")
    assert result.reference_status == "no_match"
    assert result.reference_sources == []


def test_full_graph_dismisses_account_lockout_as_policy_not_bug():
    state = analysis_graph.invoke({"content": ACCOUNT_LOCKED_REVIEW})
    assert not state.get("error")
    assert state["consensus_status"] == "dismissed"
    assert state["reasoning"]


def test_full_graph_does_not_dismiss_genuine_bug():
    state = analysis_graph.invoke({"content": GENUINE_BUG_REVIEW})
    assert not state.get("error")
    assert state["consensus_status"] != "dismissed"
