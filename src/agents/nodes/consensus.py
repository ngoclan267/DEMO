"""
Consensus Agent: danh gia lai ket qua cua Classification & Verification Agent.
Neu mau thuan -> chuyen sang trang thai "needs_review" thay vi ket luan chac chan (PRD 13, 14).
"""
from src.agents.state import AgentState
from src.models.schemas import ConsensusResult


def consensus_node(state: AgentState) -> dict:
    results = []
    for verification in state.get("verifications", []):
        agree = verification.status.value in ("verified",)
        final_confidence = verification.reliability_score if agree else verification.reliability_score * 0.5
        results.append(
            ConsensusResult(
                pain_point_id=verification.pain_point_id,
                agreement=agree,
                final_confidence=round(final_confidence, 2),
                notes="Dong thuan giua cac agent" if agree else "Can xem xet them truoc khi canh bao",
            )
        )
    return {"consensus_results": results}
