"""Notification Service: gui email / thong bao website khi vuot nguong (PRD 12.4)."""
from src.agents.state import AgentState
from src.models.schemas import Notification
from src.config import get_settings


def notification_node(state: AgentState) -> dict:
    settings = get_settings()
    notifications = []
    for pp in state.get("pain_points", []):
        if pp.post_count >= settings.negative_alert_threshold:
            notifications.append(
                Notification(
                    topic_id=pp.topic_id,
                    pain_point_id=pp.id,
                    channel="both",
                    title=pp.title,
                    message=pp.description,
                )
            )
    return {"notifications": notifications}
