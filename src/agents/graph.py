"""
LangGraph state graph noi cac agent theo dung luong trong PRD (muc 10, 16):

Nguon du lieu -> Collector -> DB -> Classification -> Verification
              -> Consensus -> Pain Point -> Notification -> Dashboard/Email
"""
try:
    from langgraph.graph import StateGraph, START, END
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    StateGraph = None
    START = "__start__"
    END = "__end__"

from src.agents.state import AgentState
from src.agents.nodes import (
    collector_node, processing_node, classification_node,
    verification_node, consensus_node, pain_point_node, notification_node,
)


def build_graph():
    if StateGraph is None:
        def fallback_graph(state: dict):
            return {**state, "messages": []}

        return fallback_graph

    graph = StateGraph(AgentState)

    graph.add_node("collector", collector_node)
    graph.add_node("processing", processing_node)
    graph.add_node("classification", classification_node)
    graph.add_node("verification", verification_node)
    graph.add_node("consensus", consensus_node)
    graph.add_node("pain_point", pain_point_node)
    graph.add_node("notification", notification_node)

    graph.add_edge(START, "collector")
    graph.add_edge("collector", "processing")
    graph.add_edge("processing", "classification")
    graph.add_edge("classification", "verification")
    graph.add_edge("verification", "consensus")
    graph.add_edge("consensus", "pain_point")
    graph.add_edge("pain_point", "notification")
    graph.add_edge("notification", END)

    return graph.compile()


# Compiled singleton used by the API layer / scheduler.
social_listening_graph = build_graph()


def run_pipeline(topic_id: str, keywords: list[str], sources: list[str], source_configs: dict | None = None) -> AgentState:
    """Chay mot chu ky xu ly (15-30 phut theo PRD 10) cho mot chu de theo doi."""
    initial_state: AgentState = {
        "topic_id": topic_id,
        "keywords": keywords,
        "sources": sources,
        "source_configs": source_configs or {},
    }
    return social_listening_graph.invoke(initial_state)
