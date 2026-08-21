import logging
from datetime import datetime
from typing import Any

from src.pipeline.collectors.apify_base import apify_timestamp_now, run_apify_actor_sync
from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)

# KHÔNG có actor Apify "chính thức" (namespace apify/) cho TikTok — khác Facebook. Actor cộng đồng
# uy tín nhất hiện có (237K user, 4.77 sao, ~92% lượt chạy thành công — xác nhận qua apify.com/
# clockworks/tiktok-scraper) dùng làm mặc định, giống cách news_article đã làm với actor cộng đồng.
DEFAULT_POST_ACTOR_ID = "clockworks/tiktok-scraper"
DEFAULT_POST_FIELD_MAP = {
    "id": "id",
    "content": "text",
    "posted_at": "createTimeISO",
    "url": "webVideoUrl",
    "like_count": "diggCount",
    "comment_count": "commentCount",
    "share_count": "shareCount",
}
# clockworks/tiktok-scraper hỗ trợ lọc video MỚI hơn 1 mốc thời gian qua trường input này — đổi
# actor khác thì kiểm tra lại, không phải actor nào cũng hỗ trợ.
DEFAULT_INCREMENTAL_DATE_FIELD = "oldestPostDateUnified"
DEFAULT_RESULTS_LIMIT = 100

# Actor comment cùng nhà phát triển (Clockworks) với actor bài viết — tách riêng vì Apify không hỗ
# trợ lấy cả video lẫn comment trong 1 lượt gọi.
DEFAULT_COMMENT_ACTOR_ID = "clockworks/tiktok-comments-scraper"
DEFAULT_COMMENT_FIELD_MAP = {
    "id": "cid",
    "content": "text",
    "posted_at": "createTimeISO",
    # TikTok không có permalink riêng cho từng comment (khác Facebook) — dùng lại URL video làm
    # link "xem trên TikTok" cho comment, vẫn đưa được người xem tới đúng ngữ cảnh video dù không
    # tự cuộn tới đúng comment.
    "url": "videoWebUrl",
}
# Trần comment lấy CHO MỖI video — mỗi video tốn 1 lượt gọi actor comment riêng (xem apify_base.py),
# nên phải giới hạn rõ ràng dù người tạo source không tự đặt trong comment_run_input.
DEFAULT_COMMENTS_PER_POST_LIMIT = 50


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Không parse được ngày của item TikTok: %r", value)
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TikTokApifyCollector(BaseCollector):
    """Thu thập VIDEO (kèm số lượt like/comment/share) và COMMENT của từng video, CÔNG KHAI trên
    TikTok, qua Apify — nhà cung cấp thu thập dữ liệu bên thứ ba (cùng hướng đi đã chọn cho Facebook,
    xem docs/linkedin_facebook_scraping_research.md mục 5), KHÔNG tự scrape TikTok trực tiếp.

    Cả video lẫn comment đều đi vào bảng `posts` như review bình thường (giống google_play/
    app_store/facebook), chạy qua đúng Classification/Verification/Consensus hiện có — comment biết
    video cha của nó qua `Post.parent_post_id` (xem src/db/models.py), gắn tự động ở Processing
    Agent (xem src/pipeline/processing/pipeline.py::ProcessResult.parent_external_id_by_external_id)
    sau khi video cha đã được upsert.

    `config`:
      - "post_run_input" (BẮT BUỘC): input truyền cho actor video, vd
        {"profiles": ["tpbank"], "resultsPerPage": 50} (theo hồ sơ) — cũng có thể dùng "postURLs" để
        chỉ định thẳng video cụ thể thay vì cả hồ sơ. LUÔN nên tự đặt "resultsPerPage" trong đây;
        nếu không, collector tự đặt DEFAULT_RESULTS_LIMIT.
      - "post_actor_id" (tuỳ chọn, mặc định "clockworks/tiktok-scraper" — actor CỘNG ĐỒNG uy tín
        nhất hiện có cho TikTok, KHÔNG có actor chính thức do Apify duy trì). "post_field_map"
        (tuỳ chọn): override tên trường output — {"id": ..., "content": ..., "posted_at": ...,
        "url": ..., "like_count": ..., "comment_count": ..., "share_count": ...}.
      - "comment_actor_id" (tuỳ chọn, mặc định "clockworks/tiktok-comments-scraper"),
        "comment_run_input" (tuỳ chọn, input NỀN cho actor comment — "postURLs"/"commentsPerPost"
        collector tự ghép/đặt cho từng video, không cần khai trong config), "comment_field_map"
        (tuỳ chọn, mặc định DEFAULT_COMMENT_FIELD_MAP).
      - "incremental_date_field" (tuỳ chọn, mặc định "oldestPostDateUnified" — trường actor mặc
        định hỗ trợ để chỉ trả video MỚI hơn 1 mốc thời gian). Đổi actor khác thì kiểm tra lại actor
        đó có hỗ trợ tương đương không, đặt rỗng nếu không hỗ trợ.

    CHỈ áp dụng cho hồ sơ CÔNG KHAI — hồ sơ riêng tư trả lỗi rõ ràng từ actor (không phải lỗi thầm
    lặng), collector coi như 0 kết quả cho hồ sơ đó (không crash cả chu kỳ vì 1 hồ sơ lỗi).

    CHI PHÍ: mỗi video tốn THÊM 1 lượt gọi actor comment riêng (Apify không hỗ trợ lấy comment của
    nhiều video trong 1 lượt gọi) — số video mỗi chu kỳ càng nhiều thì thời gian/phí càng tăng
    tuyến tính. Luôn crawl LẠI comment cho MỌI video trả về (kể cả video đã biết từ chu kỳ trước) vì
    video cũ vẫn có thể phát sinh comment mới — chưa có cơ chế incremental theo comment,
    "incremental_date_field" là cách chính để giới hạn số video xử lý mỗi chu kỳ, gián tiếp giới hạn
    luôn số lượt gọi actor comment.

    Incremental: giống các collector Apify khác — tự lưu mốc thời gian chạy gần nhất vào
    Source.config qua `resolved_config_update` sẵn có, truyền lại cho actor video ở
    "incremental_date_field" nếu có cấu hình. `known_ids` lọc thêm phòng khi actor trả về vài kết
    quả trùng (áp dụng cho cả video lẫn comment, dùng chung 1 tập external_id vì cùng share
    source)."""

    source_type = "tiktok"

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        post_run_input = self.config.get("post_run_input")
        if not post_run_input:
            raise ValueError("Source config cần 'post_run_input' cho tiktok collector")
        post_actor_id = self.config.get("post_actor_id") or DEFAULT_POST_ACTOR_ID

        post_field_map = {**DEFAULT_POST_FIELD_MAP, **(self.config.get("post_field_map") or {})}
        comment_actor_id = self.config.get("comment_actor_id") or DEFAULT_COMMENT_ACTOR_ID
        comment_field_map = {**DEFAULT_COMMENT_FIELD_MAP, **(self.config.get("comment_field_map") or {})}
        comment_run_input_base = self.config.get("comment_run_input") or {}
        known_ids = known_ids or set()

        effective_post_input = dict(post_run_input)
        effective_post_input.setdefault("resultsPerPage", min(limit, DEFAULT_RESULTS_LIMIT))
        since_date = self.config.get("since_date")
        incremental_date_field = self.config.get("incremental_date_field", DEFAULT_INCREMENTAL_DATE_FIELD)
        if since_date and incremental_date_field:
            effective_post_input.setdefault(incremental_date_field, since_date)

        post_items = run_apify_actor_sync(post_actor_id, effective_post_input)
        if post_items is None:
            # Lỗi thật (thiếu token/mạng/API) — KHÔNG được đẩy since_date tới, nếu không lần chạy
            # sau sẽ vĩnh viễn bỏ sót khoảng thời gian của lần lỗi này.
            return []

        raw_posts: list[RawPost] = []
        for item in post_items:
            post_external_id = item.get(post_field_map["id"])
            post_content = (item.get(post_field_map["content"]) or "").strip()
            if not post_external_id or not post_content:
                continue
            post_external_id = str(post_external_id)
            post_url = item.get(post_field_map.get("url", "webVideoUrl"))

            raw_posts.append(
                RawPost(
                    external_id=post_external_id,
                    content=post_content,
                    posted_at=_parse_date(item.get(post_field_map["posted_at"])),
                    raw=item,
                    like_count=_parse_int(item.get(post_field_map.get("like_count", "diggCount"))),
                    comment_count=_parse_int(item.get(post_field_map.get("comment_count", "commentCount"))),
                    share_count=_parse_int(item.get(post_field_map.get("share_count", "shareCount"))),
                    source_url=post_url,
                )
            )

            if not post_url:
                continue
            comment_input = {
                **comment_run_input_base,
                "postURLs": [post_url],
            }
            comment_input.setdefault("commentsPerPost", DEFAULT_COMMENTS_PER_POST_LIMIT)
            comment_items = run_apify_actor_sync(comment_actor_id, comment_input)
            if not comment_items:
                continue

            for comment in comment_items:
                comment_external_id = comment.get(comment_field_map["id"])
                comment_content = (comment.get(comment_field_map["content"]) or "").strip()
                if not comment_external_id or not comment_content:
                    continue
                comment_external_id = str(comment_external_id)
                if comment_external_id in known_ids:
                    continue

                raw_posts.append(
                    RawPost(
                        external_id=comment_external_id,
                        content=comment_content,
                        posted_at=_parse_date(comment.get(comment_field_map["posted_at"])),
                        raw=comment,
                        parent_external_id=post_external_id,
                        source_url=comment.get(comment_field_map.get("url", "videoWebUrl")) or post_url,
                    )
                )

        # Lưu lại mốc thời gian chạy chu kỳ này — chu kỳ sau chỉ hỏi actor video phần MỚI hơn mốc
        # này (nếu actor hỗ trợ "incremental_date_field"), giảm số video xử lý và gián tiếp giảm số
        # lượt gọi actor comment mỗi chu kỳ.
        self.resolved_config_update = {"since_date": apify_timestamp_now()}

        return raw_posts
