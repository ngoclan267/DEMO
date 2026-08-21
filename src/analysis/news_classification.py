import logging

from src.analysis.llm import get_structured_analysis_llm, record_usage
from src.analysis.schemas import NewsSentimentResult
from src.config import get_settings

logger = logging.getLogger(__name__)

NEWS_SENTIMENT_PROMPT = """Bạn là chuyên gia phân tích truyền thông cho ngân hàng tại Việt Nam. Đọc \
tiêu đề và nội dung bài báo dưới đây, đánh giá SẮC THÁI ĐƯA TIN về doanh nghiệp được nhắc tới:

- positive: khen ngợi, tin vui (vd đạt giải thưởng, tăng trưởng tốt, sản phẩm mới được đón nhận)
- neutral: thông tin thuần tuý, thông báo/sự kiện, không rõ khen hay chê
- negative: phê phán, tin xấu (vd sự cố, khiếu nại khách hàng, vi phạm quy định, khủng hoảng truyền thông)

Tiêu đề: "{title}"
Nội dung: "{content}"
"""

# Bài báo có thể rất dài (toàn văn) — cắt bớt để giữ prompt gọn, vẫn đủ ngữ cảnh đánh giá sắc thái
# (thường lộ rõ ngay ở phần đầu bài, không cần đọc hết).
_MAX_CONTENT_CHARS = 2000


def classify_news_sentiment(title: str, content: str) -> NewsSentimentResult:
    """News Sentiment Agent: sắc thái đưa tin (tích cực/trung lập/tiêu cực) cho 1 bài báo bên thứ
    ba — nhẹ hơn nhiều so với Classification Agent dùng cho phản hồi khách hàng (xem
    src/analysis/classification.py), CHỈ 1 field, không qua Verification/Consensus/Pain Point vì
    đây không phải phản hồi khách hàng cần gom case."""
    llm = get_structured_analysis_llm(NewsSentimentResult, include_raw=True)
    response = llm.invoke(NEWS_SENTIMENT_PROMPT.format(title=title, content=content[:_MAX_CONTENT_CHARS]))
    if response.get("parsing_error") is not None:
        raise response["parsing_error"]
    result = response["parsed"]
    record_usage("news_sentiment", response.get("raw"), get_settings().analysis_model_name)

    logger.info("News Sentiment: title=%s sentiment=%s", title[:60], result.sentiment)
    return result
