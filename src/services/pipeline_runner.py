"""
Chay 1 chu ky pipeline that (crawl -> ... -> notification) cho MOT Topic va
luu ket qua vao SQLite. Dung chung boi API endpoint (goi tay) va scheduler
(tu dong theo pipeline_interval_minutes) - xem src/api/routes.py, src/scheduler.py.
"""
from src.agents.graph import run_pipeline
from src.db import repository as repo
from src.models.schemas import Topic


def run_pipeline_for_topic(topic: Topic) -> dict:
    result = run_pipeline(str(topic.id), topic.keywords, topic.sources, topic.source_configs)

    raw_posts = result.get("raw_posts", [])
    predictions = result.get("predictions", [])
    pain_points = result.get("pain_points", [])
    notifications = result.get("notifications", [])

    posts_saved = repo.save_posts(raw_posts)
    repo.save_post_classifications(predictions)
    repo.add_pain_points(pain_points)
    repo.add_notifications(notifications)

    return {
        "posts_crawled": len(raw_posts),
        "posts_saved_new": posts_saved,
        "pain_points_found": len(pain_points),
        "notifications_sent": len(notifications),
    }
