"""Classification Agent: sentiment + topic + severity + confidence (PRD 14)."""
from src.agents.state import AgentState
from src.models.schemas import Prediction
from src.services.llm_service import classify_post


def classification_node(state: AgentState) -> dict:
    predictions = [classify_post(post) for post in state.get("clean_posts", [])]
    negative = [p for p in predictions if p.sentiment == "negative" and p.severity_score >= 0.5]
    return {"predictions": predictions, "negative_predictions": negative}
