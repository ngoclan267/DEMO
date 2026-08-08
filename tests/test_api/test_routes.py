"""Kiem tra cac API endpoint chinh."""
from src.db import repository as repo
from src.models.schemas import PainPoint, Severity, VerificationStatus


def _seed_pain_point(topic_id):
    pp = PainPoint(
        topic_id=topic_id,
        title="Loi dang nhap / xac thuc",
        description="2 phan hoi tieu cuc lien quan den dang nhap.",
        post_count=2,
        trend="up",
        severity=Severity.HIGH,
        verification_status=VerificationStatus.NEEDS_REVIEW,
        confidence_score=0.8,
        sample_posts=["khong dang nhap duoc", "otp khong ve"],
    )
    repo.add_pain_points([pp])
    return pp


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_topics(client):
    resp = client.get("/api/v1/topics")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_create_topic(client):
    payload = {
        "name": "ACB",
        "keywords": ["acb"],
        "sources": ["google_play"],
        "alert_threshold": 10,
        "notifications_enabled": True,
    }
    resp = client.post("/api/v1/topics", json=payload)
    assert resp.status_code == 201
    assert resp.json()["name"] == "ACB"


def test_get_pain_points_for_topic(client):
    topics = client.get("/api/v1/topics").json()
    topic_id = topics[0]["id"]
    resp = client.get(f"/api/v1/topics/{topic_id}/pain-points")
    assert resp.status_code == 200


def test_list_notifications(client):
    resp = client.get("/api/v1/notifications")
    assert resp.status_code == 200


def test_get_posts_for_topic(client):
    topics = client.get("/api/v1/topics").json()
    topic_id = topics[0]["id"]
    resp = client.get(f"/api/v1/topics/{topic_id}/posts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_posts_for_unknown_topic_404s(client):
    resp = client.get("/api/v1/topics/00000000-0000-0000-0000-000000000099/posts")
    assert resp.status_code == 404


def test_update_pain_point_status(client):
    topics = client.get("/api/v1/topics").json()
    topic_id = topics[0]["id"]
    pp = _seed_pain_point(topic_id)

    resp = client.patch(f"/api/v1/pain-points/{pp.id}", json={
        "status": "resolved",
        "assignee": "Doi CSKH",
        "resolution_notes": "Da huong dan khach cai lai app.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["assignee"] == "Doi CSKH"
    assert data["resolved_at"] is not None

    resp2 = client.get(f"/api/v1/pain-points/{pp.id}")
    assert resp2.json()["status"] == "resolved"

    # mo lai -> resolved_at phai duoc xoa
    resp3 = client.patch(f"/api/v1/pain-points/{pp.id}", json={"status": "open"})
    assert resp3.json()["resolved_at"] is None


def test_update_pain_point_unknown_404s(client):
    resp = client.patch(
        "/api/v1/pain-points/00000000-0000-0000-0000-000000000099", json={"status": "open"}
    )
    assert resp.status_code == 404


def test_report_summary(client):
    topics = client.get("/api/v1/topics").json()
    topic_id = topics[0]["id"]
    _seed_pain_point(topic_id)

    resp = client.get("/api/v1/report/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "by_topic" in data
    assert data["total_negative"] >= 2
    assert any(row["topic_id"] == topic_id for row in data["by_topic"])
