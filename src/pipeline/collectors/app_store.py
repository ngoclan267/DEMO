import logging
import time
from datetime import datetime

import httpx

from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)

RSS_URL = "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
SEARCH_URL = "https://itunes.apple.com/search"
MAX_PAGES = 10  # Apple's public customer-review feed caps out around ~500 reviews (10 pages x 50)
PAGE_SIZE = 50
SEARCH_LIMIT = 5
_MIN_TOKEN_LENGTH = 3  # bỏ từ quá ngắn để tránh khớp nhầm

# Đã gặp thực tế: cùng URL trang 1 trả 0 entry, gọi lại vài giây sau trả 50 entry — feed RSS
# công khai của Apple không ổn định, có lúc phản hồi rỗng dù app có hàng nghìn rating (kiểm
# chứng qua trường userRatingCount của iTunes Search API). Vì vậy trang 1 rỗng không được coi là
# "app chưa có review" ngay — thử lại vài lần trước khi kết luận.
_PAGE1_RETRY_ATTEMPTS = 3
_PAGE1_RETRY_DELAY_SECONDS = 2.0


def _significant_tokens(text: str) -> set[str]:
    return {token.lower() for token in text.split() if len(token) >= _MIN_TOKEN_LENGTH}


def _parse_updated(entry: dict) -> datetime | None:
    label = entry.get("updated", {}).get("label")
    if not label:
        return None
    try:
        return datetime.fromisoformat(label)
    except ValueError:
        logger.warning("Không parse được ngày 'updated' của review App Store: %r", label)
        return None


class AppStoreCollector(BaseCollector):
    """Thu thập review từ App Store qua RSS feed công khai của Apple (không cần API key).

    Dùng feed JSON chính thức `itunes.apple.com/.../rss/customerreviews/...` thay vì scrape HTML
    trang store — ổn định hơn nhiều vì đây là endpoint công khai Apple cung cấp sẵn.

    Mỗi entry có trường `updated` (ISO 8601, có timezone offset, vd "2026-08-06T09:33:59-07:00")
    dùng làm `posted_at` — đây là ngày Apple ghi nhận review lần cuối (đăng mới hoặc sửa), không
    tách biệt được 2 trường hợp đó, nhưng review sửa lại là cực hiếm nên coi là ngày đăng hợp lý.

    `config` cần MỘT trong hai kiểu:
      - {"app_id": "1661457183", "country": "vn"} — biết chính xác app_id thì dùng thẳng.
      - {"query": "SHB Saha", "country": "vn"} — chỉ có tên ngân hàng: tự search qua iTunes
        Search API công khai của Apple và CHỈ chọn app mà tiêu đề chứa đủ mọi từ khoá có nghĩa
        của query (vd query "TPBank Mobile" bắt buộc tiêu đề chứa cả "tpbank" và "mobile" — để
        không lấy nhầm app khác cùng hãng như "TPBank Biz"). Log lại app đã chọn.
    """

    source_type = "app_store"

    def resolve_identity(self) -> dict[str, str] | None:
        """Tự tìm app_id thật từ 'query' (tên ngân hàng), KHÔNG fetch review nào — dùng để nhận
        diện app đã được crawl ở 1 topic khác chưa (xem cross_topic_dedup.py) TRƯỚC khi quyết định
        backfill đầy đủ từ đầu hay đồng bộ lại từ nguồn đã có. None nếu config đã có app_id sẵn
        (không cần resolve) hoặc không tìm được app khớp."""
        if self.config.get("app_id"):
            return None
        query = self.config.get("query")
        if not query:
            return None
        app_id = self._resolve_app_id(query, self.config.get("country", "vn"))
        return {"app_id": app_id} if app_id else None

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        country = self.config.get("country", "vn")
        known_ids = known_ids or set()

        app_id = self.config.get("app_id")
        if not app_id:
            query = self.config.get("query")
            if not query:
                raise ValueError("Source config cần 'app_id' hoặc 'query' cho app_store collector")
            app_id = self._resolve_app_id(query, country)
            if not app_id:
                return []
            self.resolved_config_update = {"app_id": app_id}

        raw_posts: list[RawPost] = []
        seen_ids: set[str] = set()

        with httpx.Client(timeout=15.0) as client:
            for page in range(1, MAX_PAGES + 1):
                if len(raw_posts) >= limit:
                    break

                attempts = _PAGE1_RETRY_ATTEMPTS if page == 1 else 1
                entries: list[dict] | None = None
                for attempt in range(attempts):
                    if attempt > 0:
                        time.sleep(_PAGE1_RETRY_DELAY_SECONDS)
                    entries = self._fetch_entries(client, country, app_id, page)
                    if entries is None:  # lỗi request thật sự — không retry
                        break
                    if entries:
                        break
                    logger.info(
                        "App Store trang %s app_id=%s rỗng (lần %d/%d) — thử lại nếu còn lượt",
                        page,
                        app_id,
                        attempt + 1,
                        attempts,
                    )

                if not entries:
                    break

                new_in_page = 0
                for entry in entries:
                    # Entry đầu của trang 1 đôi khi là metadata của app, không phải review thật —
                    # chỉ nhận entry có đủ "author" và "im:rating" (đặc trưng của một review).
                    if "author" not in entry or "im:rating" not in entry:
                        continue

                    review_id = entry.get("id", {}).get("label")
                    if not review_id or review_id in seen_ids:
                        continue
                    seen_ids.add(review_id)

                    if review_id in known_ids:
                        continue
                    new_in_page += 1

                    title = entry.get("title", {}).get("label", "").strip()
                    body = entry.get("content", {}).get("label", "").strip()
                    content = f"{title}\n{body}".strip() if title else body
                    if not content:
                        continue

                    raw_posts.append(
                        RawPost(
                            external_id=review_id,
                            content=content,
                            posted_at=_parse_updated(entry),
                            raw=entry,
                        )
                    )
                    if len(raw_posts) >= limit:
                        break

                if known_ids and new_in_page == 0:
                    # Cả trang này đều là review đã có trong DB -> đã bắt kịp dữ liệu cũ (chế độ
                    # incremental), dừng sớm thay vì quét hết tới MAX_PAGES mỗi chu kỳ.
                    logger.info("App Store app_id=%s: đã bắt kịp dữ liệu đã thu thập, dừng phân trang sớm", app_id)
                    break

        return raw_posts

    def _fetch_entries(self, client: httpx.Client, country: str, app_id: str, page: int) -> list[dict] | None:
        """Trả về danh sách entry, [] nếu feed rỗng thật, hoặc None nếu request lỗi."""
        url = RSS_URL.format(country=country, page=page, app_id=app_id)
        try:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logger.exception("Lỗi khi thu thập App Store review app_id=%s trang=%s", app_id, page)
            return None
        return payload.get("feed", {}).get("entry", [])

    def _resolve_app_id(self, query: str, country: str) -> str | None:
        required_tokens = _significant_tokens(query)
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(
                    SEARCH_URL,
                    params={"term": query, "country": country, "entity": "software", "limit": SEARCH_LIMIT},
                )
                response.raise_for_status()
                candidates = response.json().get("results", [])
        except Exception:
            logger.exception("Lỗi khi search App Store cho query=%r", query)
            return None

        for candidate in candidates:
            track_id = candidate.get("trackId")
            title_tokens = _significant_tokens(candidate.get("trackName") or "")
            if track_id and required_tokens and required_tokens.issubset(title_tokens):
                logger.info(
                    "Search App Store %r -> chọn app %r (trackId=%s, seller=%s)",
                    query,
                    candidate.get("trackName"),
                    track_id,
                    candidate.get("sellerName"),
                )
                return str(track_id)

        logger.warning("Không tìm được app App Store khớp đủ với query=%r", query)
        return None
