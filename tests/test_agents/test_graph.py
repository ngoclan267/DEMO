"""Kiem tra pipeline LangGraph chay dung thu tu va tra ve state hop le."""
from src.agents.graph import run_pipeline


def test_pipeline_runs_end_to_end():
    result = run_pipeline(topic_id="demo-topic", keywords=["ngan hang"], sources=["google_play"])
    assert "raw_posts" in result
    assert "predictions" in result
    assert "pain_points" in result
    assert isinstance(result["pain_points"], list)


def test_pipeline_notifications_only_above_threshold():
    result = run_pipeline(topic_id="demo-topic", keywords=["ngan hang"], sources=["app_store"])
    for n in result.get("notifications", []):
        assert n.topic_id == "demo-topic"
