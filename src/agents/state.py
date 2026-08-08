"""
Shared state schema for the LangGraph pipeline.
Flow (see docs/architecture_diagram.md):
Collector -> Processing -> Classification -> Verification -> Consensus -> PainPoint -> Notification
"""
from typing import Annotated, TypedDict
from operator import add

from src.models.schemas import Post, Prediction, VerificationResult, ConsensusResult, PainPoint, Notification


class AgentState(TypedDict, total=False):
    topic_id: str
    keywords: list[str]
    sources: list[str]
    source_configs: dict[str, dict]

    raw_posts: Annotated[list[Post], add]
    clean_posts: Annotated[list[Post], add]
    predictions: Annotated[list[Prediction], add]

    negative_predictions: list[Prediction]
    verifications: Annotated[list[VerificationResult], add]
    consensus_results: Annotated[list[ConsensusResult], add]

    pain_points: Annotated[list[PainPoint], add]
    notifications: Annotated[list[Notification], add]

    errors: Annotated[list[str], add]
