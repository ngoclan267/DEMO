import logging

from src.pipeline.collectors.base import BaseCollector, RawPost

logger = logging.getLogger(__name__)


class LinkedInCollector(BaseCollector):
    """Stub — LinkedIn chưa có collector thật ở phase này.

    LinkedIn không cung cấp API tìm kiếm bài viết/bình luận công khai theo từ khóa cho
    third-party, và scrape trực tiếp vi phạm ToS (dễ bị chặn IP / khoá tài khoản). Xem
    docs/linkedin_facebook_scraping_research.md để biết phân tích và hướng đi đề xuất cho
    giai đoạn mở rộng sau MVP.

    Interface giống hệt các collector khác để khi có giải pháp thật, chỉ cần thay nội dung
    `collect()` — không cần đổi gì ở runner/pipeline.
    """

    source_type = "linkedin"

    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        logger.warning(
            "LinkedInCollector chưa triển khai (source config=%s) — xem "
            "docs/linkedin_facebook_scraping_research.md",
            self.config,
        )
        return []
