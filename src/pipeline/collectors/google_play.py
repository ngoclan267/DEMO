import logging

from google_play_scraper import Sort, reviews, search

from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)

# Khi query khớp gần như tuyệt đối với tên app (vd query "TPBank Mobile" cho đúng app tên
# "TPBank Mobile"), Google Play trả app đó dưới dạng "hero card" đặc biệt mà thư viện
# google-play-scraper không parse được appId (trả về None) — trong khi cùng app đó vẫn có đầy đủ
# appId nếu nó chỉ xuất hiện như một kết quả bình thường trong danh sách. Thử query "tên ngân
# hàng + hậu tố" trước (đã kiểm chứng thực tế né được kiểu hiển thị đặc biệt đó cho cả SHB Saha
# và TPBank Mobile) rồi mới thử query gốc.
_SEARCH_FALLBACK_SUFFIX = "ngân hàng số"
_SEARCH_HITS = 10
_MIN_TOKEN_LENGTH = 3  # bỏ từ quá ngắn (vd "mb", "vp") để tránh khớp nhầm
_PAGE_BATCH_SIZE = 200  # review mỗi lần gọi reviews() khi phân trang qua continuation_token


def _significant_tokens(text: str) -> set[str]:
    return {token.lower() for token in text.split() if len(token) >= _MIN_TOKEN_LENGTH}


class GooglePlayCollector(BaseCollector):
    """Thu thập review từ Google Play qua thư viện `google-play-scraper` (không cần API key).

    Phân trang qua `continuation_token` để lấy được nhiều hơn 1 batch — Google Play có thể có
    hàng nghìn review, không giới hạn cứng như App Store. Nếu có `known_ids` (external_id đã có
    trong DB), dừng phân trang ngay khi gặp một trang mà mọi review đều đã biết — đây là cơ chế
    incremental: lần đầu thu thập sẽ đi sâu (backfill) theo `limit`, các chu kỳ sau chỉ còn lấy
    review MỚI rồi dừng sớm, tránh phải quét lại toàn bộ và giảm rủi ro bị chặn vì gọi quá nhiều.

    `config` cần MỘT trong hai kiểu:
      - {"package_name": "vn.shb.saha.mbanking", "lang": "vi", "country": "vn"} — biết chính xác
        package thì dùng thẳng, không cần search.
      - {"query": "SHB Saha", "lang": "vi", "country": "vn"} — chỉ có tên ngân hàng: tự search
        Google Play và CHỈ chọn app mà tiêu đề chứa đủ mọi từ khoá có nghĩa của query (vd query
        "TPBank Mobile" bắt buộc tiêu đề chứa cả "tpbank" và "mobile" — để không lấy nhầm app
        khác cùng hãng như "TPBank Biz"). Log lại app đã chọn để đối chiếu thủ công.
    """

    source_type = "google_play"

    def resolve_identity(self) -> dict[str, str] | None:
        """Tự tìm package_name thật từ 'query' (tên ngân hàng), KHÔNG fetch review nào — dùng để
        nhận diện app đã được crawl ở 1 topic khác chưa (xem cross_topic_dedup.py) TRƯỚC khi quyết
        định backfill đầy đủ từ đầu hay đồng bộ lại từ nguồn đã có. None nếu config đã có
        package_name sẵn (không cần resolve) hoặc không tìm được app khớp."""
        if self.config.get("package_name"):
            return None
        query = self.config.get("query")
        if not query:
            return None
        package_name = self._resolve_package_name(query, self.config.get("lang", "vi"), self.config.get("country", "vn"))
        return {"package_name": package_name} if package_name else None

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        lang = self.config.get("lang", "vi")
        country = self.config.get("country", "vn")
        known_ids = known_ids or set()

        package_name = self.config.get("package_name")
        if not package_name:
            query = self.config.get("query")
            if not query:
                raise ValueError("Source config cần 'package_name' hoặc 'query' cho google_play collector")
            package_name = self._resolve_package_name(query, lang, country)
            if not package_name:
                return []
            self.resolved_config_update = {"package_name": package_name}

        raw_posts: list[RawPost] = []
        continuation_token = None
        new_total = 0  # chỉ đếm review MỚI — quyết định khi nào dừng backfill, tách biệt khỏi
        # các review ĐÃ BIẾT được thêm lại chỉ để cập nhật phản hồi mới (xem is_known bên dưới).

        while new_total < limit:
            try:
                batch, continuation_token = reviews(
                    package_name,
                    lang=lang,
                    country=country,
                    sort=Sort.NEWEST,
                    count=min(_PAGE_BATCH_SIZE, limit - new_total),
                    continuation_token=continuation_token,
                )
            except Exception:
                logger.exception("Lỗi khi thu thập Google Play review cho package=%s", package_name)
                break

            if not batch:
                break

            new_in_batch = 0
            for review in batch:
                # Google Play có thể đổi cấu trúc review bất cứ lúc nào (trường bị đổi tên/xóa) —
                # 1 review lỗi cấu trúc chỉ nên mất chính nó, không được kéo mất cả batch còn lại.
                try:
                    review_id = review["reviewId"]
                except (KeyError, TypeError):
                    logger.warning("Bỏ qua 1 review thiếu 'reviewId' (có thể do đổi cấu trúc API): %r", review)
                    continue

                content = (review.get("content") or "").strip()
                if not content:
                    continue
                reply_content = (review.get("replyContent") or "").strip() or None

                # Review đã có trong DB (known_ids) bình thường được bỏ qua (đây là cốt lõi của chế
                # độ incremental — không quét lại toàn bộ mỗi chu kỳ). Nhưng nếu ngân hàng VỪA trả
                # lời một review cũ đã biết, review đó vẫn xuất hiện lại ở đây (trong phạm vi các
                # trang còn được quét trước khi bắt kịp dữ liệu cũ) — cho đi qua để cập nhật
                # reply_content/reply_at (xem upsert_posts: DO UPDATE riêng 2 cột này, không đụng
                # nội dung review gốc). Không tính vào new_in_batch/new_total vì đây không phải
                # review mới, không nên ảnh hưởng tới quyết định dừng backfill.
                is_known = review_id in known_ids
                if is_known and reply_content is None:
                    continue

                raw_posts.append(
                    RawPost(
                        external_id=review_id,
                        content=content,
                        posted_at=review.get("at"),
                        raw=review,
                        reply_content=reply_content,
                        reply_at=review.get("repliedAt") if reply_content else None,
                    )
                )
                if not is_known:
                    new_in_batch += 1
                    new_total += 1
                    if new_total >= limit:
                        break

            if new_in_batch == 0:
                # Cả trang này đều là review đã có trong DB -> đã bắt kịp dữ liệu cũ, dừng sớm.
                logger.info(
                    "Google Play package=%s: đã bắt kịp dữ liệu đã thu thập, dừng phân trang sớm",
                    package_name,
                )
                break

            if continuation_token is None:
                break  # Google Play báo hết review

        return raw_posts

    def _resolve_package_name(self, query: str, lang: str, country: str) -> str | None:
        core_token = query.split()[0] if query.split() else query
        required_tokens = _significant_tokens(query)
        search_queries = list(
            dict.fromkeys(
                [
                    f"{core_token} {_SEARCH_FALLBACK_SUFFIX}",
                    query,
                    f"{query} {_SEARCH_FALLBACK_SUFFIX}",
                ]
            )
        )

        for search_query in search_queries:
            try:
                candidates = search(search_query, lang=lang, country=country, n_hits=_SEARCH_HITS)
            except Exception:
                logger.exception("Lỗi khi search Google Play cho query=%r", search_query)
                continue

            for candidate in candidates:
                app_id = candidate.get("appId")
                title_tokens = _significant_tokens(candidate.get("title") or "")
                if app_id and required_tokens and required_tokens.issubset(title_tokens):
                    logger.info(
                        "Search Google Play %r -> chọn app %r (packageName=%s, developer=%s)",
                        query,
                        candidate.get("title"),
                        app_id,
                        candidate.get("developer"),
                    )
                    return app_id

        logger.warning("Không tìm được app Google Play khớp đủ với query=%r", query)
        return None
