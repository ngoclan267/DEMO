from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawPost:
    """Một bản ghi thô do Collector Agent thu thập được, trước khi qua Processing Agent."""

    external_id: str
    content: str
    posted_at: datetime | None
    raw: dict[str, Any] = field(default_factory=dict)
    # Phản hồi của nhà phát triển/ngân hàng cho review này (nếu có) — hiện chỉ Google Play trả về
    # được (repliedAt/replyContent qua google-play-scraper); App Store RSS feed công khai không có
    # trường này nên luôn là None với app_store collector.
    reply_content: str | None = None
    reply_at: datetime | None = None
    # Số liệu tương tác — hiện chỉ FacebookApifyCollector điền cho bài viết (xem
    # src/pipeline/collectors/facebook.py); None với mọi collector khác.
    like_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    # external_id (trong CÙNG 1 lượt collect() này) của bài viết Facebook mà đây là 1 COMMENT của
    # nó — Processing Agent (xem src/pipeline/processing/pipeline.py) resolve thành parent_post_id
    # (UUID nội bộ) sau khi bài viết cha đã được upsert. None = bản ghi độc lập (bài viết gốc, hoặc
    # post/review của collector không có khái niệm bài viết-comment).
    parent_external_id: str | None = None
    # Link trực tiếp tới bài viết/comment gốc trên nền tảng nguồn (vd permalink Facebook) — hiện
    # chỉ FacebookApifyCollector điền; None với collector khác (Google Play/App Store không có
    # permalink từng review riêng, chỉ có trang app — xem _build_app_url trong routes_dashboard.py).
    source_url: str | None = None


class BaseCollector(ABC):
    """Giao diện chung cho mọi nguồn thu thập (Google Play, App Store, LinkedIn, ...).

    Mỗi collector nhận `config` từ cột `sources.config` (JSONB) và trả về danh sách
    `RawPost` — không tự ghi DB, không tự làm sạch dữ liệu (đó là việc của Processing Agent).
    """

    source_type: str

    def __init__(self, config: dict[str, Any]):
        self.config = config
        # Set bởi collector con sau khi tự resolve id app từ 1 "query" tên ngân hàng (vd
        # package_name/app_id) — caller (xem src/pipeline/runner.py) đọc lại và lưu vào
        # Source.config trong DB, để lần sau dùng thẳng id thay vì phải search lại, và để dashboard
        # dựng được link thẳng tới trang app thay vì trang tìm kiếm.
        self.resolved_config_update: dict[str, Any] | None = None

    @abstractmethod
    def collect(self, limit: int = 100, known_ids: set[str] | None = None) -> list[RawPost]:
        """Lấy tối đa `limit` bài/review mới nhất từ nguồn.

        `known_ids` là tập external_id đã có trong DB cho đúng source này (nếu biết) — cho phép
        collector dừng phân trang sớm ngay khi bắt kịp dữ liệu cũ (chế độ incremental), thay vì
        luôn phải quét lại từ đầu mỗi chu kỳ.
        """
        raise NotImplementedError
