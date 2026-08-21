import logging
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from src.config import get_settings
from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)

# Trần an toàn số trang chi tiết tải mỗi seed_url/mỗi chu kỳ — seed_urls là trang mục lục do người
# tạo topic khai báo (không tự dò toàn bộ site), nhưng vẫn cần trần để 1 trang mục lục có rất nhiều
# link không kéo dài chu kỳ thu thập vô hạn.
MAX_ARTICLES_PER_SEED = 40
REQUEST_DELAY_SECONDS = 0.5  # giãn cách giữa các request — crawl lịch sự với trang công khai
REQUEST_TIMEOUT = 15.0

DEFAULT_CATEGORY_KEYWORDS: dict[str, str] = {
    "bieu-phi": "fee",
    "phi-dich-vu": "fee",
    "lai-suat": "fee",
    "bao-tri": "maintenance",
    "gian-doan": "maintenance",
    "nang-cap": "maintenance",
    "su-co": "incident",
    "canh-bao": "incident",
    "chinh-sach": "policy",
    "quy-dinh": "policy",
    "dieu-khoan": "policy",
    "san-pham": "product",
    "the-": "product",
    "tin-tuc": "notice",
    "thong-bao": "notice",
}

_NON_ARTICLE_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc", ".docx", ".xls", ".xlsx")


def _normalize_url(url: str) -> str:
    """Bỏ fragment (#...) và chuẩn hoá dấu '/' cuối — cùng 1 trang không bị coi là 2 external_id
    khác nhau chỉ vì khác fragment/dấu gạch chéo cuối URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))


# Số ký tự <p> tối thiểu để một ancestor của <h1> được coi là "khối nội dung chính" — đủ lớn để bỏ
# qua các khối trung gian gần như rỗng (vd chỉ có 1 dòng breadcrumb), đủ nhỏ để nhận cả thông báo
# ngắn (vd "Ngân hàng tạm ngừng giao dịch từ 22h00 đến 06h00 ngày mai." ~55 ký tự).
_MIN_ARTICLE_TEXT_LENGTH = 40
_MAX_ANCESTOR_DEPTH = 8


def _extract_main_text(soup: BeautifulSoup) -> str:
    """Ưu tiên khối ancestor GẦN NHẤT của <h1> có đủ nội dung <p> — thực tế kiểm chứng trên trang
    ngân hàng thật cho thấy heuristic "quét toàn trang, lấy khối nhiều <p> nhất" (cách cũ) hay chọn
    nhầm 1 banner/CTA lặp lại ở NHIỀU trang (vd "Đăng ký tài khoản online...") thay vì nội dung riêng
    của từng trang, vì banner đó đôi khi có tổng độ dài <p> lớn hơn nội dung thật. Bám theo <h1> (tiêu
    đề trang) và đi ngược lên tổ tiên gần nhất có đủ nội dung tránh được nhầm lẫn này vì banner dùng
    chung thường nằm NGOÀI khối chứa <h1>.

    Chỉ rơi về cách quét toàn trang (fallback) khi trang không có <h1> hoặc không tìm được tổ tiên
    nào đủ nội dung trong _MAX_ANCESTOR_DEPTH cấp — vẫn tốt hơn bỏ qua trang."""
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    h1 = soup.find("h1")
    if h1 is not None:
        node = h1.parent
        depth = 0
        while node is not None and depth < _MAX_ANCESTOR_DEPTH:
            paragraphs = node.find_all("p", recursive=True) if hasattr(node, "find_all") else []
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            if len(text) >= _MIN_ARTICLE_TEXT_LENGTH:
                return text
            node = node.parent
            depth += 1

    return _extract_largest_paragraph_cluster(soup)


def _extract_largest_paragraph_cluster(soup: BeautifulSoup) -> str:
    """Fallback: quét toàn trang, lấy khối có tổng độ dài text trong <p> lớn nhất — dùng khi trang
    không có <h1> rõ ràng để bám theo (xem _extract_main_text)."""
    candidates = soup.find_all(["article", "main", "div", "section"])
    best_text = ""
    best_len = 0
    for candidate in candidates:
        paragraphs = candidate.find_all("p", recursive=True)
        text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
        if len(text) > best_len:
            best_len = len(text)
            best_text = text

    if best_text:
        return best_text
    # Không tìm được khối nào có <p> — rơi về toàn bộ text của <body> (vẫn tốt hơn bỏ qua trang).
    body = soup.find("body")
    return body.get_text(" ", strip=True) if body else soup.get_text(" ", strip=True)


def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return ""


def _extract_published_at(soup: BeautifulSoup) -> datetime | None:
    meta = soup.find("meta", attrs={"property": "article:published_time"}) or soup.find(
        "meta", attrs={"name": "article:published_time"}
    )
    candidates: list[str] = []
    if meta and meta.get("content"):
        candidates.append(meta["content"])
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        candidates.append(time_tag["datetime"])

    for raw_value in candidates:
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _categorize(url: str, title: str, category_keywords: dict[str, str] | None) -> str:
    keywords = category_keywords or DEFAULT_CATEGORY_KEYWORDS
    haystack = f"{url} {title}".lower()
    for keyword, category in keywords.items():
        if keyword.lower() in haystack:
            return category
    return "other"


def _is_article_link(url: str, allowed_domains: set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc not in allowed_domains:
        return False
    if parsed.path.lower().endswith(_NON_ARTICLE_EXTENSIONS):
        return False
    return True


class BankWebsiteCollector(BaseCollector):
    """Thu thập thông báo/chính sách/biểu phí/sự cố/bảo trì/sản phẩm CHÍNH THỨC từ website ngân
    hàng — làm nguồn ĐỐI CHIẾU cho Verification Agent (xem
    src/analysis/knowledge_base/loader.py::load_topic_documents), KHÔNG phải phản hồi khách hàng.

    `config`:
      - "seed_urls" (bắt buộc): danh sách URL trang mục lục (tin tức/thông báo/biểu phí/sản phẩm...)
        do người tạo topic khai báo. Cố ý KHÔNG tự dò toàn bộ site — chỉ đọc link xuất hiện trên
        chính các trang mục lục này, để phạm vi crawl luôn rõ ràng và có kiểm soát.
      - "allowed_domains" (tuỳ chọn): giới hạn domain được coi là link bài viết hợp lệ; mặc định suy
        ra từ domain của chính các seed_urls.
      - "category_keywords" (tuỳ chọn): ghi đè DEFAULT_CATEGORY_KEYWORDS để phân loại tài liệu theo
        từ khoá trong URL/tiêu đề — không tốn quota LLM (cùng triết lý tiết kiệm quota đã áp dụng ở
        Classification Agent).

    Giới hạn đã biết ở giai đoạn này: chỉ phát hiện trang MỚI (URL chưa có trong known_ids). Trang
    đã biết nhưng bị ngân hàng sửa nội dung (vd cập nhật biểu phí) chưa được tự phát hiện lại — việc
    re-check định kỳ nội dung cũ sẽ bổ sung sau, không chặn khả năng dùng làm nguồn đối chiếu ngay.
    """

    source_type = "bank_website"

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        seed_urls = self.config.get("seed_urls")
        if not seed_urls:
            raise ValueError("Source config cần 'seed_urls' cho bank_website collector")
        known_ids = known_ids or set()

        allowed_domains = set(self.config.get("allowed_domains") or [])
        if not allowed_domains:
            allowed_domains = {urlparse(u).netloc for u in seed_urls}

        category_keywords = self.config.get("category_keywords")
        headers = {"User-Agent": get_settings().bank_website_user_agent}

        raw_posts: list[RawPost] = []
        seen_in_run: set[str] = set()

        # follow_redirects=True: bắt buộc — trang chủ ngân hàng hầu hết redirect http->https hoặc
        # apex->www (vd http://tpb.vn -> https://tpb.vn/); mặc định httpx KHÔNG tự theo redirect, và
        # raise_for_status() trên response 3xx sẽ tự báo lỗi nhắc bật cờ này thay vì âm thầm trả nội
        # dung rỗng.
        with httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as client:
            for seed_url in seed_urls:
                if len(raw_posts) >= limit:
                    break
                article_links = self._discover_article_links(client, seed_url, allowed_domains)

                fetched_for_seed = 0
                for link in article_links:
                    if len(raw_posts) >= limit or fetched_for_seed >= MAX_ARTICLES_PER_SEED:
                        break
                    if link in seen_in_run or link in known_ids:
                        continue
                    seen_in_run.add(link)

                    doc = self._fetch_article(client, link, category_keywords)
                    if doc is not None:
                        raw_posts.append(doc)
                        fetched_for_seed += 1
                    time.sleep(REQUEST_DELAY_SECONDS)

        return raw_posts

    def _discover_article_links(self, client: httpx.Client, seed_url: str, allowed_domains: set[str]) -> list[str]:
        try:
            response = client.get(seed_url)
            response.raise_for_status()
        except Exception:
            logger.exception("Lỗi khi tải trang mục lục bank_website: %s", seed_url)
            return []

        # Resolve link tương đối theo URL CUỐI CÙNG sau redirect (response.url), không phải seed_url
        # gốc — nhiều trang ngân hàng redirect http->https hoặc apex->www (vd http://tpb.vn ->
        # https://tpb.vn/); dùng seed_url gốc để resolve sẽ tạo ra 2 biến thể URL (http/https) khác
        # nhau cho CÙNG 1 trang giữa các lần chạy, phá vỡ dedup theo (topic_id, url).
        base_url = str(response.url)
        soup = BeautifulSoup(response.text, "html.parser")
        links: list[str] = []
        seen = set()
        for anchor in soup.find_all("a", href=True):
            absolute = _normalize_url(urljoin(base_url, anchor["href"]))
            if absolute == _normalize_url(base_url):
                continue
            if not _is_article_link(absolute, allowed_domains):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    def _fetch_article(
        self, client: httpx.Client, url: str, category_keywords: dict[str, str] | None
    ) -> RawPost | None:
        try:
            response = client.get(url)
            response.raise_for_status()
        except Exception:
            logger.exception("Lỗi khi tải bài viết bank_website: %s", url)
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        content = _extract_main_text(soup)
        if not content:
            return None
        title = _extract_title(soup)

        return RawPost(
            external_id=url,
            content=content,
            posted_at=_extract_published_at(soup),
            raw={
                "title": title,
                "category": _categorize(url, title, category_keywords),
                "source_url": url,
            },
        )
