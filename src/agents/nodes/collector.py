"""Collector Agent: thu thap du lieu tu Google Play, App Store, LinkedIn (PRD 14)."""
from src.agents.state import AgentState
from src.agents.tools.crawler_tools import crawl_source


def collector_node(state: AgentState) -> dict:
    posts = []
    source_configs = state.get("source_configs", {}) or {}
    for source in state.get("sources", []):
        source_config = source_configs.get(source)
        posts.extend(crawl_source(source, state.get("keywords", []), state["topic_id"], source_config))
    return {"raw_posts": posts}
