"""
FastAPI endpoints - xem docs/guide cho dac ta chi tiet.
Cac route bam sat man hinh trong luong nguoi dung: Workspace, Dashboard,
Pain Point detail, Trung tam thong bao, Cai dat tai khoan (xem flow diagram).

Du lieu duoc luu that trong SQLite qua src/db/repository.py: Topics duoc seed
voi app_id That da xac minh tren Google Play / App Store; PainPoint va
Notification chi duoc tao khi mot chu ky pipeline that (crawl -> phan loai ->
kiem chung) chay xong, khong con du lieu mo phong dung san.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.config import get_settings
from src.models.schemas import (
    Topic, TopicCreate, PainPoint, PainPointUpdate, Notification, Post, ReportSummary, TopicTrend,
)
from src.db import repository as repo
from src.services.pipeline_runner import run_pipeline_for_topic

router = APIRouter()


@router.get("/topics", response_model=list[Topic], tags=["topics"])
def list_topics():
    """Danh sach chu de theo doi cua workspace hien tai."""
    return repo.list_topics()


@router.post("/topics", response_model=Topic, status_code=201, tags=["topics"])
def create_topic(payload: TopicCreate):
    """Tao chu de theo doi moi (ten, tu khoa, nguon du lieu that, nguong canh bao)."""
    topic = Topic(owner_id=repo.DEMO_OWNER_ID, **payload.model_dump())
    return repo.create_topic(topic)


@router.get("/topics/{topic_id}", response_model=Topic, tags=["topics"])
def get_topic(topic_id: UUID):
    topic = repo.get_topic(str(topic_id))
    if not topic:
        raise HTTPException(status_code=404, detail="Khong tim thay chu de")
    return topic


@router.get("/topics/{topic_id}/pain-points", response_model=list[PainPoint], tags=["dashboard"])
def get_pain_points(topic_id: UUID):
    """Danh sach pain point cho dashboard cua mot chu de (tu ket qua pipeline that)."""
    return repo.list_pain_points(str(topic_id))


@router.get("/topics/{topic_id}/posts", response_model=list[Post], tags=["dashboard"])
def get_posts(topic_id: UUID, source: str | None = None, limit: int = 200):
    """
    Danh sach phan hoi (review) THAT da crawl duoc cho chu de - noi dung goc,
    tac gia, nguon, thoi gian - de nguoi dung tu doi chieu voi Pain Point/
    phan loai cua he thong thay vi chi nhin so lieu tong hop.
    """
    topic = repo.get_topic(str(topic_id))
    if not topic:
        raise HTTPException(status_code=404, detail="Khong tim thay chu de")
    return repo.list_posts(str(topic_id), source=source, limit=limit)


@router.get("/topics/{topic_id}/trend", response_model=TopicTrend, tags=["dashboard"])
def get_topic_trend(topic_id: UUID, days: int = 30):
    """
    Xu huong phan hoi tieu cuc THAT theo ngay (published_at cua tung review da
    crawl), dung de ve bieu do so sanh cac chu ky/thang - thay cho sparkline gia
    truoc day. `days` gioi han so ngay gan nhat (mac dinh 30, toi da 365).
    """
    topic = repo.get_topic(str(topic_id))
    if not topic:
        raise HTTPException(status_code=404, detail="Khong tim thay chu de")
    days = max(1, min(days, 365))
    points = repo.get_topic_trend(str(topic_id), days=days)
    return TopicTrend(topic_id=topic_id, points=points)


@router.get("/pain-points/{pain_point_id}", response_model=PainPoint, tags=["dashboard"])
def get_pain_point(pain_point_id: UUID):
    pain_point = repo.get_pain_point(str(pain_point_id))
    if not pain_point:
        raise HTTPException(status_code=404, detail="Khong tim thay pain point")
    return pain_point


@router.patch("/pain-points/{pain_point_id}", response_model=PainPoint, tags=["respond"])
def update_pain_point(pain_point_id: UUID, payload: PainPointUpdate):
    """
    Respond: cap nhat trang thai xu ly (moi/dang xu ly/da xu ly), nguoi/doi phu
    trach va ghi chu xu ly cho mot Pain Point - lop nghiep vu con nguoi thao
    tac tren ket qua pipeline (khong phai output cua agent nao).
    """
    pain_point = repo.update_pain_point(str(pain_point_id), payload)
    if not pain_point:
        raise HTTPException(status_code=404, detail="Khong tim thay pain point")
    return pain_point


@router.get("/report/summary", response_model=ReportSummary, tags=["report"])
def get_report_summary():
    """
    Report: tong hop KPI cross-topic (Command Center) - tong phan hoi tieu
    cuc, so case theo trang thai, thoi gian xu ly trung binh, ty le dung SLA,
    va bang so sanh giua cac chu de (ngan hang) dang theo doi.
    """
    settings = get_settings()
    return repo.get_report_summary(settings.sla_response_hours)


@router.get("/notifications", response_model=list[Notification], tags=["notifications"])
def list_notifications():
    """Trung tam thong bao - lich su canh bao that tren tat ca chu de."""
    return repo.list_notifications()


@router.post("/topics/{topic_id}/run-pipeline", tags=["agents"])
def trigger_pipeline(topic_id: UUID):
    """
    Kich hoat mot chu ky xu ly that cho chu de (Collector -> ... -> Notification),
    dung dung source_configs (app_id/token that) da cau hinh tren Topic.
    Ket qua (Post/PainPoint/Notification) duoc luu vao SQLite de Dashboard doc lai.
    Trong production, buoc nay chay tu dong theo lich (15-30 phut / chu ky).
    """
    topic = repo.get_topic(str(topic_id))
    if not topic:
        raise HTTPException(status_code=404, detail="Khong tim thay chu de")

    return run_pipeline_for_topic(topic)


@router.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
