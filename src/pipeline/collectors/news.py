import logging
from datetime import datetime
from typing import Any

from src.pipeline.collectors.apify_base import apify_timestamp_now, run_apify_actor_sync
from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)

# KHÔNG có actor Apify "chính thức" ổn định cho tin tức (khác Facebook —
# "apify/facebook-comments-scraper" do chính Apify duy trì). Google News scraper trên Apify Store
# là actor CỘNG ĐỒNG (vd "scrapesage/google-news-scraper"), input/output khác nhau tuỳ actor — vì
# vậy "actor_id"/"run_input" LUÔN bắt buộc trong Source.config, không hardcode default nào ở đây.
DEFAULT_FIELD_MAP = {"id": "url", "content": "title", "posted_at": "date"}
DEFAULT_INCREMENTAL_DATE_FIELD = ""  # phần lớn actor tin tức không hỗ trợ lọc theo ngày qua input
DEFAULT_RESULTS_LIMIT = 100


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Không parse được ngày của bài báo: %r", value)
        return None


class NewsApifyCollector(BaseCollector):
    """Thu thập bài báo/tin tức CÔNG KHAI nhắc tới ngân hàng qua Apify — nhà cung cấp thu thập dữ
    liệu bên thứ ba (đúng hướng đi đã chọn trong docs/linkedin_facebook_scraping_research.md mục
    5), KHÔNG tự scrape trực tiếp.

    Đây KHÔNG phải phản hồi khách hàng — là tin BÊN THỨ BA, đi vào bảng `official_documents` (xem
    REFERENCE_SOURCE_TYPES trong __init__.py) với category="news", tách biệt khỏi văn bản CHÍNH
    THỨC của ngân hàng (`bank_website`). Bị loại trừ khỏi knowledge base của Verification Agent
    (xem src/analysis/knowledge_base/loader.py::load_topic_documents) — chỉ để người dùng xem, tín
    hiệu "vấn đề đã lên báo chưa", không tham gia đối chiếu/suy luận AI.

    `config`:
      - "actor_id" (bắt buộc): actor Apify tìm tin tức theo từ khoá — chọn 1 actor thật trên Apify
        Store (mục News, vd "scrapesage/google-news-scraper") vì không có actor chính thức ổn định
        để hardcode. Field_map bên dưới là PHỎNG ĐOÁN hợp lý, kiểm tra lại theo output thật của
        actor đã chọn, chỉnh qua "field_map" nếu khác.
      - "run_input" (bắt buộc): input truyền thẳng cho actor — field tuỳ actor đã chọn (xác nhận
        thật với "scrapesage/google-news-scraper": {"searchTerms": ["TPBank"], "maxItems": 100}).
        LUÔN nên tự đặt trần kết quả trong đây; nếu không, collector tự đặt DEFAULT_RESULTS_LIMIT.
      - "field_map" (tuỳ chọn): override tên trường output — {"id": ..., "content": ...,
        "posted_at": ...}. Mặc định dùng "url" làm id (ổn định hơn dùng title) và "title" làm nội
        dung (đa số actor tin tức chỉ trả tiêu đề+mô tả ngắn qua trang kết quả tìm kiếm, không phải
        toàn văn bài báo).
      - "incremental_date_field" (tuỳ chọn): tên trường input actor dùng để lọc tin MỚI hơn 1 mốc
        thời gian, nếu actor đã chọn hỗ trợ. Mặc định rỗng (không phải actor tin tức nào cũng có).

    Incremental: giống FacebookApifyCollector — Apify chạy actor như hộp đen, collector tự lưu mốc
    thời gian chạy gần nhất vào Source.config qua `resolved_config_update` sẵn có, truyền lại cho
    actor ở "incremental_date_field" nếu có cấu hình. `known_ids` lọc thêm phòng khi actor trả về
    vài kết quả trùng URL."""

    source_type = "news_article"

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        actor_id = self.config.get("actor_id")
        run_input = self.config.get("run_input")
        if not actor_id or not run_input:
            raise ValueError("Source config cần 'actor_id' và 'run_input' cho news_article collector")

        field_map = {**DEFAULT_FIELD_MAP, **(self.config.get("field_map") or {})}
        incremental_date_field = self.config.get("incremental_date_field", DEFAULT_INCREMENTAL_DATE_FIELD)
        known_ids = known_ids or set()

        effective_input = dict(run_input)
        effective_input.setdefault("resultsLimit", min(limit, DEFAULT_RESULTS_LIMIT))
        since_date = self.config.get("since_date")
        if since_date and incremental_date_field:
            effective_input.setdefault(incremental_date_field, since_date)

        items = run_apify_actor_sync(actor_id, effective_input)
        if items is None:
            # Lỗi thật (thiếu token/mạng/API) — KHÔNG được đẩy since_date tới, nếu không lần chạy
            # sau sẽ vĩnh viễn bỏ sót khoảng thời gian của lần lỗi này (xem docstring
            # run_apify_actor_sync). Trả rỗng, giữ nguyên config cũ để thử lại đúng mốc ở chu kỳ sau.
            return []

        raw_posts: list[RawPost] = []
        for item in items:
            external_id = item.get(field_map["id"])
            content = (item.get(field_map["content"]) or "").strip()
            if not external_id or not content:
                continue
            external_id = str(external_id)
            if external_id in known_ids:
                continue

            raw_posts.append(
                RawPost(
                    external_id=external_id,
                    content=content,
                    posted_at=_parse_date(item.get(field_map["posted_at"])),
                    # category="news" -> process_raw_documents (reference_docs.py) tự lưu đúng cột
                    # category của official_documents; title dùng cho tiêu đề hiển thị.
                    raw={**item, "title": item.get("title") or content[:255], "category": "news"},
                )
            )
            if len(raw_posts) >= limit:
                break

        self.resolved_config_update = {"since_date": apify_timestamp_now()}

        return raw_posts
