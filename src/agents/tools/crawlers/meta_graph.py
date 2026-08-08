"""
Facebook / Instagram - CHI dung Meta Graph API chinh thuc.

QUAN TRONG - gioi han that cua nen tang (khong phai gioi han ky thuat):
- Graph API chi tra ve du lieu cua Page / Instagram Business account ma
  chinh doanh nghiep (hoac user cap quyen) SO HUU / QUAN TRI.
- Khong the "crawl" binh luan/bai viet cong khai tu cac trang khac theo
  tu khoa tu do nhu Google Play/App Store - Meta khong cung cap API cho
  muc dich do, va scraping ngoai API vi pham Dieu khoan dich vu cua Meta.
- Vi vay voi MVP, Facebook/Instagram chi phu hop de:
    (a) doanh nghiep tu giam sat binh luan tren chinh Page/tai khoan cua ho, hoac
    (b) mo rong sau nay bang cach mua du lieu tu cac nha cung cap social-listening
        da duoc Meta cap phep (vi du: cac doi tac trong Meta Partner Program).

Yeu cau: Page Access Token (hoac User Access Token voi quyen
`pages_read_engagement`, `instagram_basic`, `instagram_manage_comments`)
duoc cap qua Meta App da duoc App Review.
"""
from datetime import datetime
from uuid import UUID, uuid4

import httpx

from src.models.schemas import Post

GRAPH_BASE = "https://graph.facebook.com/v20.0"


def crawl_facebook_page(page_id: str, access_token: str, topic_id: str, limit: int = 25) -> list[Post]:
    """
    Lay cac binh luan tren cac bai viet gan day cua MOT Page ma doanh nghiep
    quan tri (khong phai crawl toan mang xa hoi).
    """
    posts: list[Post] = []
    if not access_token:
        raise RuntimeError("Thieu Page Access Token - xem huong dan Meta Graph API o dau file nay.")

    try:
        feed_resp = httpx.get(
            f"{GRAPH_BASE}/{page_id}/feed",
            params={"access_token": access_token, "limit": limit, "fields": "id,created_time"},
            timeout=10,
        )
        feed_resp.raise_for_status()
        feed = feed_resp.json().get("data", [])
    except httpx.HTTPError:
        return posts

    for item in feed:
        post_fb_id = item["id"]
        try:
            c_resp = httpx.get(
                f"{GRAPH_BASE}/{post_fb_id}/comments",
                params={"access_token": access_token, "fields": "message,from,created_time"},
                timeout=10,
            )
            c_resp.raise_for_status()
            comments = c_resp.json().get("data", [])
        except httpx.HTTPError:
            continue

        for c in comments:
            if not c.get("message"):
                continue
            posts.append(Post(
                id=uuid4(),
                topic_id=UUID(topic_id) if _is_uuid(topic_id) else uuid4(),
                source="facebook",
                author=c.get("from", {}).get("name"),
                content=c["message"],
                published_at=_parse_time(c.get("created_time")),
            ))
    return posts


def crawl_instagram_business(ig_user_id: str, access_token: str, topic_id: str, limit: int = 25) -> list[Post]:
    """
    Lay cac binh luan tren cac media gan day cua MOT Instagram Business/Creator
    account ma doanh nghiep quan tri (yeu cau lien ket voi mot Facebook Page).
    """
    posts: list[Post] = []
    if not access_token:
        raise RuntimeError("Thieu Access Token - xem huong dan Meta Graph API o dau file nay.")

    try:
        media_resp = httpx.get(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={"access_token": access_token, "limit": limit, "fields": "id,timestamp"},
            timeout=10,
        )
        media_resp.raise_for_status()
        media_items = media_resp.json().get("data", [])
    except httpx.HTTPError:
        return posts

    for item in media_items:
        media_id = item["id"]
        try:
            c_resp = httpx.get(
                f"{GRAPH_BASE}/{media_id}/comments",
                params={"access_token": access_token, "fields": "text,username,timestamp"},
                timeout=10,
            )
            c_resp.raise_for_status()
            comments = c_resp.json().get("data", [])
        except httpx.HTTPError:
            continue

        for c in comments:
            if not c.get("text"):
                continue
            posts.append(Post(
                id=uuid4(),
                topic_id=UUID(topic_id) if _is_uuid(topic_id) else uuid4(),
                source="instagram",
                author=c.get("username"),
                content=c["text"],
                published_at=_parse_time(c.get("timestamp")),
            ))
    return posts


def _parse_time(value) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.utcnow()


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
