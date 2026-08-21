import logging
from datetime import datetime
from typing import Any

from src.pipeline.collectors.apify_base import apify_timestamp_now, run_apify_actor_sync
from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)

# Actor lấy COMMENT đã ổn định (do chính Apify duy trì) — giữ làm mặc định, hiếm khi cần đổi.
DEFAULT_COMMENT_ACTOR_ID = "apify/facebook-comments-scraper"
DEFAULT_COMMENT_FIELD_MAP = {"id": "commentId", "content": "text", "posted_at": "date", "url": "commentUrl"}

# Actor lấy BÀI VIẾT + số liệu tương tác trên 1 TRANG (Page) — do chính Apify duy trì (xác nhận qua
# apify.com/apify/facebook-posts-scraper), field output khớp DEFAULT_POST_FIELD_MAP bên dưới. Đây
# là mặc định của collector (giả định phổ biến nhất: doanh nghiệp theo dõi TRANG chính thức của
# mình) — nguồn theo dõi 1 NHÓM (Group) công khai thay vì trang phải tự đổi "post_actor_id" +
# "post_field_map" sang DEFAULT_GROUP_ACTOR_ID/DEFAULT_GROUP_FIELD_MAP bên dưới, vì Trang và Nhóm
# là 2 actor khác nhau trên Apify, field output KHÔNG giống nhau (vd "likes" vs "likesCount").
DEFAULT_POST_ACTOR_ID = "apify/facebook-posts-scraper"
DEFAULT_POST_FIELD_MAP = {
    "id": "postId",
    "content": "text",
    "posted_at": "time",
    "url": "url",
    "like_count": "likes",
    "comment_count": "comments",
    "share_count": "shares",
}
# apify/facebook-posts-scraper hỗ trợ lọc bài MỚI hơn 1 mốc thời gian qua trường input này (định
# dạng YYYY-MM-DD hoặc ISO) — đổi actor khác thì kiểm tra lại, không phải actor nào cũng hỗ trợ.
DEFAULT_INCREMENTAL_DATE_FIELD = "onlyPostsNewerThan"

# Actor lấy bài viết trên 1 NHÓM (Group) công khai — cũng do chính Apify duy trì (xác nhận qua
# apify.com/apify/facebook-groups-scraper), nhưng field output KHÁC actor Trang ở trên. Dùng khi
# "startUrls" trỏ vào URL dạng facebook.com/groups/... — set "post_actor_id" +
# "post_field_map" = DEFAULT_GROUP_FIELD_MAP trong Source.config để dùng đúng actor này.
DEFAULT_GROUP_ACTOR_ID = "apify/facebook-groups-scraper"
DEFAULT_GROUP_FIELD_MAP = {
    "id": "id",
    "content": "text",
    "posted_at": "time",
    "url": "url",
    "like_count": "likesCount",
    "comment_count": "commentsCount",
    "share_count": "sharesCount",
}
DEFAULT_RESULTS_LIMIT = 100
# Trần comment lấy CHO MỖI bài viết — mỗi bài viết tốn 1 lượt gọi actor comment riêng (xem
# apify_base.py), nên phải giới hạn rõ ràng dù người tạo source không tự đặt "resultsLimit" trong
# comment_run_input, tránh 1 bài viết nhiều nghìn comment kéo dài/tốn phí cả chu kỳ.
DEFAULT_COMMENTS_PER_POST_LIMIT = 50


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Không parse được ngày của item Facebook: %r", value)
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FacebookApifyCollector(BaseCollector):
    """Thu thập BÀI VIẾT (kèm số lượt like/comment/share) và COMMENT của từng bài, CÔNG KHAI trên
    Facebook, qua Apify — nhà cung cấp thu thập dữ liệu bên thứ ba (đúng hướng đi đã chọn trong
    docs/linkedin_facebook_scraping_research.md mục 5), KHÔNG tự scrape Facebook trực tiếp.

    Cả bài viết lẫn comment đều đi vào bảng `posts` như review bình thường (giống google_play/
    app_store), chạy qua đúng Classification/Verification/Consensus hiện có — comment biết bài viết
    cha của nó qua `Post.parent_post_id` (xem src/db/models.py), gắn tự động ở Processing Agent (xem
    src/pipeline/processing/pipeline.py::ProcessResult.parent_external_id_by_external_id) sau khi bài
    viết cha đã được upsert.

    `config`:
      - "post_run_input" (BẮT BUỘC): input truyền cho actor bài viết, vd
        {"startUrls": [{"url": "https://www.facebook.com/TPBank"}]} cho TRANG, hoặc
        {"startUrls": [{"url": "https://www.facebook.com/groups/..."}]} cho NHÓM. LUÔN nên tự đặt
        "resultsLimit" trong đây; nếu không, collector tự đặt DEFAULT_RESULTS_LIMIT.
      - "post_actor_id" / "post_field_map" (tuỳ chọn): mặc định dùng actor CHÍNH THỨC của Apify cho
        TRANG (DEFAULT_POST_ACTOR_ID/DEFAULT_POST_FIELD_MAP). Nguồn là 1 NHÓM công khai (URL dạng
        facebook.com/groups/...) thì phải tự đổi 2 field này sang DEFAULT_GROUP_ACTOR_ID/
        DEFAULT_GROUP_FIELD_MAP — actor Trang và Nhóm KHÁC nhau, field output cũng khác nhau (vd
        "likes" vs "likesCount"), dùng nhầm actor sẽ trả về rỗng dù URL hợp lệ.
      - "post_field_map" giá trị override tuỳ chỉnh: {"id": ..., "content": ..., "posted_at": ...,
        "url": ..., "like_count": ..., "comment_count": ..., "share_count": ...}. "url" là URL bài
        viết, dùng làm startUrls khi gọi actor comment bên dưới.
      - "comment_actor_id" (tuỳ chọn, mặc định "apify/facebook-comments-scraper"), "comment_run_input"
        (tuỳ chọn, input NỀN cho actor comment — "startUrls"/"resultsLimit" collector tự ghép/đặt cho
        từng bài viết, không cần khai trong config), "comment_field_map" (tuỳ chọn, mặc định
        DEFAULT_COMMENT_FIELD_MAP).
      - "incremental_date_field" (tuỳ chọn, mặc định "onlyPostsNewerThan" — trường actor mặc định hỗ
        trợ để chỉ trả bài MỚI hơn 1 mốc thời gian). Đổi actor khác thì kiểm tra lại actor đó có hỗ
        trợ tương đương không, đặt rỗng nếu không hỗ trợ.

    CHỈ áp dụng cho trang/nhóm CÔNG KHAI — nhóm/trang riêng tư cần tài khoản đăng nhập, nằm ngoài
    phạm vi (xem rủi ro dùng tài khoản thật ở docs/linkedin_facebook_scraping_research.md mục 2).

    CHI PHÍ: mỗi bài viết tốn THÊM 1 lượt gọi actor comment riêng (Apify không hỗ trợ lấy comment
    của nhiều bài viết trong 1 lượt gọi) — số bài viết mỗi chu kỳ càng nhiều thì thời gian/phí càng
    tăng tuyến tính. Luôn crawl LẠI comment cho MỌI bài viết trả về (kể cả bài đã biết từ chu kỳ
    trước) vì bài cũ vẫn có thể phát sinh comment mới — chưa có cơ chế incremental theo comment,
    "incremental_date_field" (nếu actor bài viết hỗ trợ) là cách chính để giới hạn số bài viết xử lý
    mỗi chu kỳ, gián tiếp giới hạn luôn số lượt gọi actor comment.

    Incremental: giống các collector Apify khác — tự lưu mốc thời gian chạy gần nhất vào
    Source.config qua `resolved_config_update` sẵn có, truyền lại cho actor bài viết ở
    "incremental_date_field" nếu có cấu hình. `known_ids` lọc thêm phòng khi actor trả về vài kết quả
    trùng (áp dụng cho cả bài viết lẫn comment, dùng chung 1 tập external_id vì cùng share source)."""

    source_type = "facebook"

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        post_run_input = self.config.get("post_run_input")
        if not post_run_input:
            raise ValueError("Source config cần 'post_run_input' cho facebook collector")
        post_actor_id = self.config.get("post_actor_id") or DEFAULT_POST_ACTOR_ID

        post_field_map = {**DEFAULT_POST_FIELD_MAP, **(self.config.get("post_field_map") or {})}
        comment_actor_id = self.config.get("comment_actor_id") or DEFAULT_COMMENT_ACTOR_ID
        comment_field_map = {**DEFAULT_COMMENT_FIELD_MAP, **(self.config.get("comment_field_map") or {})}
        comment_run_input_base = self.config.get("comment_run_input") or {}
        known_ids = known_ids or set()

        effective_post_input = dict(post_run_input)
        effective_post_input.setdefault("resultsLimit", min(limit, DEFAULT_RESULTS_LIMIT))
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
            post_url = item.get(post_field_map.get("url", "url"))

            raw_posts.append(
                RawPost(
                    external_id=post_external_id,
                    content=post_content,
                    posted_at=_parse_date(item.get(post_field_map["posted_at"])),
                    raw=item,
                    like_count=_parse_int(item.get(post_field_map.get("like_count", "likes"))),
                    comment_count=_parse_int(item.get(post_field_map.get("comment_count", "comments"))),
                    share_count=_parse_int(item.get(post_field_map.get("share_count", "shares"))),
                    source_url=post_url,
                )
            )

            if not post_url:
                continue
            comment_input = {
                **comment_run_input_base,
                "startUrls": [{"url": post_url}],
            }
            comment_input.setdefault("resultsLimit", DEFAULT_COMMENTS_PER_POST_LIMIT)
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
                        source_url=comment.get(comment_field_map.get("url", "commentUrl")),
                    )
                )

        # Lưu lại mốc thời gian chạy chu kỳ này — chu kỳ sau chỉ hỏi actor bài viết phần MỚI hơn mốc
        # này (nếu actor hỗ trợ "incremental_date_field"), giảm số bài viết xử lý và gián tiếp giảm
        # số lượt gọi actor comment mỗi chu kỳ.
        self.resolved_config_update = {"since_date": apify_timestamp_now()}

        return raw_posts
