"""
Tu dong chay lai pipeline (crawl that -> phan tich -> luu) cho tat ca Topic
theo chu ky pipeline_interval_minutes (PRD 10: 15-30 phut/chu ky), thay vi
phai goi tay POST /run-pipeline moi lan.

Dung BackgroundScheduler (thread rieng) vi toan bo pipeline la sync (httpx,
google-play-scraper, SQLAlchemy sync engine) - khong lam nghen event loop
cua FastAPI.
"""
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from src.config import get_settings
from src.db import repository as repo
from src.services.pipeline_runner import run_pipeline_for_topic

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
JOB_ID = "auto_crawl_pipeline"


def run_all_topics() -> None:
    for topic in repo.list_topics():
        try:
            stats = run_pipeline_for_topic(topic)
        except Exception:
            logger.exception("Auto-pipeline that bai cho topic %s (%s)", topic.name, topic.id)
            continue
        logger.info("Auto-pipeline topic=%s: %s", topic.name, stats)


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    if not settings.enable_scheduler:
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_all_topics,
        trigger="interval",
        minutes=settings.pipeline_interval_minutes,
        id=JOB_ID,
        next_run_time=datetime.now(),  # chay ngay 1 lan luc khoi dong, roi lap lai theo chu ky
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Da bat scheduler: tu dong crawl moi %s phut.", settings.pipeline_interval_minutes)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
