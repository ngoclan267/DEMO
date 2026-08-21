import logging

from langgraph.graph import END, StateGraph

from src.analysis.classification import classify_post
from src.analysis.consensus import ConsensusResult, apply_cross_check, resolve_consensus
from src.analysis.cross_check import cross_check_classification
from src.analysis.llm import is_quota_error
from src.analysis.seeding_detection import detect_seeding
from src.analysis.state import AnalysisState
from src.analysis.verification import verify_post

logger = logging.getLogger(__name__)


def classify_node(state: AnalysisState) -> dict:
    try:
        return {"classification": classify_post(state["content"])}
    except Exception as exc:
        return {"error": str(exc), "quota_exhausted": is_quota_error(exc)}


def detect_seeding_node(state: AnalysisState) -> dict:
    """Seeding Agent — tín hiệu BỔ SUNG (cảnh báo), không phải điều kiện tiên quyết của pipeline
    chính. Lỗi ở đây (kể cả hết quota) KHÔNG được huỷ post — giữ is_seeding mặc định False (xem
    _analyze_post_standalone), chỉ log cảnh báo, cùng triết lý với cross_check_node."""
    try:
        result = detect_seeding(state["content"], state.get("similar_post_count", 0))
        return {"seeding": result}
    except Exception:
        logger.warning("Seeding Agent lỗi, bỏ qua cảnh báo seeding cho post này", exc_info=True)
        return {}


def verify_node(state: AnalysisState) -> dict:
    try:
        classification = state["classification"]
        verification = verify_post(state["content"], classification.topic_label, state.get("topic_docs"))
        return {"verification": verification}
    except Exception as exc:
        return {"error": str(exc), "quota_exhausted": is_quota_error(exc)}


def consensus_node(state: AnalysisState) -> dict:
    try:
        result = resolve_consensus(state["content"], state["classification"], state["verification"])
        return {
            "consensus_status": result.consensus_status,
            "reasoning": result.reasoning,
            "final_confidence": result.final_confidence,
        }
    except Exception as exc:
        return {"error": str(exc), "quota_exhausted": is_quota_error(exc)}


def cross_check_node(state: AnalysisState) -> dict:
    """Chỉ được ROUTE tới đây khi consensus_status=="needs_review" (xem _should_cross_check) — lớp
    kiểm tra BỔ SUNG, không phải bước bắt buộc của pipeline chính. Lỗi ở đây (kể cả cross-check
    không khả dụng vì chưa cấu hình OPENAI_API_KEY) KHÔNG được huỷ post — giữ nguyên kết luận
    consensus đã có, chỉ log cảnh báo, khác hẳn 3 node trên (lỗi ở đó = huỷ cả post)."""
    try:
        cross_check_result = cross_check_classification(state["content"])
        if cross_check_result is None:
            return {}
        current = ConsensusResult(
            consensus_status=state["consensus_status"],
            reasoning=state["reasoning"],
            final_confidence=state["final_confidence"],
        )
        updated = apply_cross_check(state["classification"], state["verification"], current, cross_check_result)
        return {
            "consensus_status": updated.consensus_status,
            "reasoning": updated.reasoning,
            "final_confidence": updated.final_confidence,
            "cross_check_agreed": updated.cross_check_agreed,
        }
    except Exception:
        logger.warning("Cross-Check Agent lỗi, giữ nguyên kết luận consensus gốc", exc_info=True)
        return {}


def _route_after(state: AnalysisState, next_node: str) -> str:
    return END if state.get("error") else next_node


def _should_cross_check(state: AnalysisState) -> str:
    if state.get("error"):
        return END
    # Chỉ cross-check case CẦN XEM XÉT — case đã "confirmed"/"dismissed" ngay từ Consensus đủ rõ
    # ràng, cross-check thêm chỉ tốn quota vô ích mà không đổi được gì (xem apply_cross_check).
    if state.get("consensus_status") == "needs_review":
        return "cross_check"
    return END


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("classify", classify_node)
    graph.add_node("detect_seeding", detect_seeding_node)
    graph.add_node("verify", verify_node)
    graph.add_node("consensus", consensus_node)
    graph.add_node("cross_check", cross_check_node)

    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", lambda s: _route_after(s, "detect_seeding"))
    # detect_seeding_node tự nuốt lỗi (không set state["error"]) — luôn đi tiếp verify, không cần
    # routing có điều kiện như các node khác.
    graph.add_edge("detect_seeding", "verify")
    graph.add_conditional_edges("verify", lambda s: _route_after(s, "consensus"))
    graph.add_conditional_edges("consensus", _should_cross_check)
    graph.add_edge("cross_check", END)

    return graph.compile()


analysis_graph = build_analysis_graph()
