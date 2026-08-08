"""
Google Play crawler - dung thu vien `google-play-scraper`.
Thu vien nay doc du lieu tu cac trang review CONG KHAI cua Google Play
(khong can dang nhap, khong xoay tai khoan, khong ne co che chong bot).

Luu y trach nhiem: van nen tuan thu robots.txt / dieu khoan cua Google Play,
gioi han tan suat goi (rate limit) va chi thu thap du lieu can thiet cho
muc dich social listening cua doanh nghiep so huu ung dung hoac giam sat
thuong hieu cua chinh minh/doi thu mot cach hop ly.
"""
from datetime import datetime
from uuid import UUID, uuid4

from src.models.schemas import Post

try:
    from google_play_scraper import reviews, Sort
except ImportError:  # thu vien optional - chi can khi thuc su crawl
    reviews = None
    Sort = None


def crawl_google_play(
    app_id: str, topic_id: str, lang: str = "vi", country: str = "vn",
    count: int = 40, max_total: int = 300, page_size: int = 100,
) -> list[Post]:
    """
    Lay danh sach review tren Google Play, moi nhat truoc, phan trang qua
    continuation_token cua thu vien de dao sau vao lich su thay vi chi lay
    dung 40 review moi nhat moi lan (gioi han cu khien du lieu gan nhu dung
    yen qua tung chu ky crawl). Dung lai khi da du `max_total`, het du lieu
    (continuation_token rong / 1 trang tra ve 0 ket qua), hoac Google chan.
    """
    if reviews is None:
        raise RuntimeError(
            "Thieu thu vien google-play-scraper. Cai dat: pip install google-play-scraper"
        )

    posts: list[Post] = []
    token = None
    target = max(count, max_total)
    while len(posts) < target:
        try:
            result, token = reviews(
                app_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=min(page_size, target - len(posts)),
                continuation_token=token,
            )
        except Exception:
            break

        if not result:
            break

        for r in result:
            posts.append(Post(
                id=uuid4(),
                topic_id=UUID(topic_id) if _is_uuid(topic_id) else uuid4(),
                source="google_play",
                author=r.get("userName"),
                content=r.get("content", ""),
                published_at=r.get("at") or datetime.utcnow(),
            ))

        if token is None:
            break

    return posts


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
