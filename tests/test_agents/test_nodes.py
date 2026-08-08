"""Unit test cho tung agent node rieng le."""
from uuid import uuid4
from datetime import datetime

from src.agents.nodes.processing import processing_node
from src.agents.nodes.classification import classification_node
from src.agents.nodes.collector import collector_node
from src.models.schemas import Post


def _make_post(content: str) -> Post:
    return Post(topic_id=uuid4(), source="google_play", content=content, published_at=datetime.utcnow())


def test_processing_node_removes_duplicates():
    posts = [_make_post("loi dang nhap"), _make_post("loi dang nhap"), _make_post("tot")]
    result = processing_node({"raw_posts": posts})
    assert len(result["clean_posts"]) == 2


def test_classification_node_flags_negative_predictions():
    posts = [_make_post("khong dang nhap duoc, that vong qua")]
    result = classification_node({"clean_posts": posts})
    assert len(result["predictions"]) == 1
    assert "negative_predictions" in result


def test_collector_node_passes_source_config_to_crawler(monkeypatch):
    captured = {}

    def fake_crawl_source(source, keywords, topic_id, source_config=None):
        captured["source"] = source
        captured["source_config"] = source_config
        return [Post(topic_id=uuid4(), source=source, content="real crawl", published_at=datetime.utcnow())]

    monkeypatch.setattr("src.agents.nodes.collector.crawl_source", fake_crawl_source)

    topic_id = str(uuid4())
    state = {
        "topic_id": topic_id,
        "keywords": ["techcombank"],
        "sources": ["google_play"],
        "source_configs": {"google_play": {"app_id": "com.example.app"}},
    }

    result = collector_node(state)

    assert captured["source"] == "google_play"
    assert captured["source_config"] == {"app_id": "com.example.app"}
    assert len(result["raw_posts"]) == 1
