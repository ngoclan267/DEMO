from src.pipeline.collectors.app_store import AppStoreCollector
from src.pipeline.collectors.bank_website import BankWebsiteCollector
from src.pipeline.collectors.base import BaseCollector, RawPost
from src.pipeline.collectors.facebook import FacebookApifyCollector
from src.pipeline.collectors.google_play import GooglePlayCollector
from src.pipeline.collectors.linkedin import LinkedInCollector
from src.pipeline.collectors.news import NewsApifyCollector
from src.pipeline.collectors.tiktok import TikTokApifyCollector

COLLECTORS_BY_SOURCE_TYPE: dict[str, type[BaseCollector]] = {
    "google_play": GooglePlayCollector,
    "app_store": AppStoreCollector,
    "linkedin": LinkedInCollector,
    "bank_website": BankWebsiteCollector,
    "facebook": FacebookApifyCollector,
    "news_article": NewsApifyCollector,
    "tiktok": TikTokApifyCollector,
}

# Nguồn ĐỐI CHIẾU (tài liệu chính thức của ngân hàng, hoặc tin bên thứ ba nhắc tới ngân hàng) —
# khác các nguồn còn lại đều là phản hồi khách hàng. runner.py dùng tập này để rẽ nhánh: dữ liệu thu
# được đi vào bảng official_documents thay vì posts/predictions/pain_points. news_article nằm ở đây
# (không phải phản hồi khách hàng) nhưng KHÁC bank_website ở category="news" — bị loader.py loại
# trừ khỏi knowledge base của Verification Agent (xem load_topic_documents), chỉ hiển thị cho
# người dùng xem, không tham gia đối chiếu "văn bản CHÍNH THỨC".
REFERENCE_SOURCE_TYPES: set[str] = {"bank_website", "news_article"}


def get_collector(source_type: str, config: dict) -> BaseCollector:
    try:
        collector_cls = COLLECTORS_BY_SOURCE_TYPE[source_type]
    except KeyError:
        raise ValueError(f"Không có collector cho source type: {source_type}") from None
    return collector_cls(config)


__all__ = [
    "BaseCollector",
    "RawPost",
    "GooglePlayCollector",
    "AppStoreCollector",
    "LinkedInCollector",
    "BankWebsiteCollector",
    "FacebookApifyCollector",
    "NewsApifyCollector",
    "TikTokApifyCollector",
    "COLLECTORS_BY_SOURCE_TYPE",
    "REFERENCE_SOURCE_TYPES",
    "get_collector",
]
