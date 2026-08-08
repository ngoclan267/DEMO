"""
Crawler tools cho Collector Agent.

Nguon ho tro (theo cau hinh moi Topic - xem src/models/schemas.py):
  - app_store  -> RSS Customer Reviews chinh thuc cua Apple (cong khai)
  - google_play -> thu vien google-play-scraper (doc trang review cong khai)
  - facebook   -> Meta Graph API, CHI cho Page ma doanh nghiep quan tri
  - instagram  -> Meta Graph API, CHI cho Business/Creator account quan tri

LinkedIn: MVP chua trien khai crawler that (LinkedIn han che rat chat viec
truy cap noi dung cong khai qua API/scraping voi ben thu ba); danh sach
'linkedin' trong Topic duoc giu lai cho lo trinh sau khi co doi tac API.

Khong co che do "xoay tai khoan" hay ne chan bot cho bat ky nguon nao -
day la gioi han co chu dich, khong phai thieu sot.
"""
import logging

from src.models.schemas import Post
from src.agents.tools.crawlers import (
    crawl_app_store, crawl_google_play, crawl_facebook_page, crawl_instagram_business,
)

logger = logging.getLogger(__name__)


def crawl_source(source: str, keywords: list[str], topic_id: str, source_config: dict | None = None) -> list[Post]:
    """
    Crawl du lieu phan hoi that tu mot nguon da cau hinh cho Topic.

    source_config vi du:
      app_store:  {"app_id": "1548623362", "country": "vn"}
      google_play:{"app_id": "vn.com.techcombank.bb.app"}
      facebook:   {"page_id": "...", "access_token": "..."}
      instagram:  {"ig_user_id": "...", "access_token": "..."}

    Neu thieu source_config hoac nguon chua duoc trien khai (vd linkedin),
    tra ve danh sach rong va ghi log canh bao - KHONG fabricate du lieu gia.
    """
    cfg = source_config or {}

    try:
        if source == "app_store" and cfg.get("app_id"):
            return crawl_app_store(cfg["app_id"], topic_id, country=cfg.get("country", "vn"))

        if source == "google_play" and cfg.get("app_id"):
            return crawl_google_play(cfg["app_id"], topic_id, country=cfg.get("country", "vn"))

        if source == "facebook" and cfg.get("page_id") and cfg.get("access_token"):
            return crawl_facebook_page(cfg["page_id"], cfg["access_token"], topic_id)

        if source == "instagram" and cfg.get("ig_user_id") and cfg.get("access_token"):
            return crawl_instagram_business(cfg["ig_user_id"], cfg["access_token"], topic_id)

    except RuntimeError as exc:
        logger.warning("Crawl that bai cho nguon %s (topic %s): %s", source, topic_id, exc)
        return []

    logger.warning(
        "Bo qua nguon '%s' cho topic %s: chua co source_config hop le hoac chua duoc trien khai crawler that.",
        source, topic_id,
    )
    return []
