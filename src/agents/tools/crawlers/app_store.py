"""
App Store crawler - dung RSS Customer Reviews chinh thuc cua Apple.
Day la nguon cong khai, khong can dang nhap, khong vi pham ToS:
https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortby=mostrecent/json

Yeu cau: biet truoc App Store numeric id cua ung dung can theo doi
(vd: Techcombank Mobile -> tra cuu tren App Store -> lay id trong URL).
"""
from datetime import datetime
from uuid import UUID, uuid4

import httpx

from src.models.schemas import Post

RSS_URL = "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortby=mostrecent/json"


def crawl_app_store(app_id: str, topic_id: str, country: str = "vn", max_pages: int = 10) -> list[Post]:
    """
    Lay danh sach review tren App Store, moi nhat truoc. RSS cua Apple phan
    trang ~50 review/trang (toi da 10 trang chinh thuc); ban cu chi doc dung
    trang 1 nen luon dung yen o ~50 review gan nhat. Gio lap qua cac trang
    cho den khi het du lieu (trang tra ve rong) hoac cham max_pages.
    """
    posts: list[Post] = []
    for page in range(1, max_pages + 1):
        url = RSS_URL.format(country=country, app_id=app_id)
        if page > 1:
            url = url.replace("/json", f"/page={page}/json")

        try:
            resp = httpx.get(url, timeout=10, headers={"User-Agent": "SentinelSocialListening/1.0"})
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            break

        feed = data.get("feed", {}) or {}
        entries = feed.get("entry") or []
        if not isinstance(entries, list):
            entries = [entries] if entries else []
        # Trang 1 co 1 "entry" dau tien la thong tin app (khong phai review) khi
        # dung dang so nhieu - da duoc loc tu nhien vi khong co field content.

        if not entries:
            break

        for entry in entries:
            content = None
            if isinstance(entry, dict):
                content = entry.get("content", {}).get("label") or entry.get("title", {}).get("label")
                author = entry.get("author", {}).get("name", {}).get("label")
                updated = entry.get("updated", {}).get("label")
            else:
                author = None
                updated = None

            if not content:
                continue
            try:
                published_at = datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else datetime.utcnow()
            except ValueError:
                published_at = datetime.utcnow()

            posts.append(Post(
                id=uuid4(),
                topic_id=UUID(topic_id) if _is_uuid(topic_id) else uuid4(),
                source="app_store",
                author=author,
                content=content,
                published_at=published_at,
            ))

    return posts


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
