import logging

from src.analysis.llm import get_structured_analysis_llm, record_usage
from src.analysis.schemas import SeedingResult
from src.config import get_settings
from src.pipeline.processing.seeding import SEEDING_CLUSTER_WINDOW_HOURS

logger = logging.getLogger(__name__)

SEEDING_PROMPT = """Bạn là chuyên gia phát hiện review/bình luận GIẢ MẠO, DÀN DỰNG (seeding) — nội \
dung được viết ra để thao túng đánh giá (khen ảo để PR, hoặc chê ảo để bôi nhọ), khác hẳn phàn nàn/\
khen THẬT của khách hàng thật.

Dấu hiệu THƯỜNG GẶP của seeding (không phải lúc nào cũng đủ cả, cân nhắc TỔNG THỂ):
- Giọng văn khen/chê MỘT CHIỀU bất thường, thiếu chi tiết cụ thể — không mô tả hiện tượng/thao tác \
thật, chỉ có cảm thán chung chung kiểu quảng cáo.
- Câu chữ mang tính TEMPLATE — nhiều review na ná nhau về cấu trúc câu, chỉ đổi vài từ.
- Nhắc tên sản phẩm/thương hiệu một cách không tự nhiên, như đang PR chứ không phải mô tả trải \
nghiệm cá nhân.

QUAN TRỌNG: 1 CỤM bài đăng dồn dập trong thời gian ngắn KHÔNG tự động là seeding — có thể là phản \
ứng THẬT của nhiều khách hàng trước 1 sự cố có thật (vd app sập, lỗi giao dịch hàng loạt). Chỉ kết \
luận is_seeding=True khi giọng văn/nội dung CŨNG có dấu hiệu giả tạo như trên, không chỉ dựa vào \
việc có nhiều bài tương tự đăng gần nhau.

Review cần đánh giá: "{content}"

Bối cảnh: có {similar_count} bài viết khác nội dung/giọng văn tương tự được đăng trong \
{window_hours} giờ gần đây trên cùng chủ đề này.
"""


def detect_seeding(content: str, similar_count: int) -> SeedingResult:
    """Seeding Agent — kết hợp giọng văn (LLM chấm trực tiếp) với ngữ cảnh cụm bài dồn dập
    (similar_count, tính bởi src/pipeline/processing/seeding.py::count_similar_recent_posts) để LLM
    tự cân nhắc, không kết luận chỉ dựa 1 tín hiệu đơn lẻ."""
    llm = get_structured_analysis_llm(SeedingResult, include_raw=True)
    prompt = SEEDING_PROMPT.format(
        content=content, similar_count=similar_count, window_hours=SEEDING_CLUSTER_WINDOW_HOURS
    )
    response = llm.invoke(prompt)
    if response.get("parsing_error") is not None:
        raise response["parsing_error"]
    result = response["parsed"]
    record_usage("seeding_detection", response.get("raw"), get_settings().analysis_model_name)

    if result.is_seeding:
        logger.info("Seeding Agent: nghi ngờ seeding — %s", result.reasoning)
    return result
