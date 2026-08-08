"""
Verification Agent: thanh phan quan trong nhat cua he thong (PRD 14).
Doi voi cac phan hoi tieu cuc, tim kiem thong bao chinh thuc / van ban phap ly /
thong cao bao chi de kiem chung truoc khi ket luan day la loi cua doanh nghiep.
"""
from src.agents.state import AgentState
from src.models.schemas import VerificationResult
from src.services.llm_service import verify_negative_signal


def verification_node(state: AgentState) -> dict:
    results = [verify_negative_signal(p) for p in state.get("negative_predictions", [])]
    return {"verifications": results}
