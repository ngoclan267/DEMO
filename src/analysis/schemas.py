from typing import Literal

from pydantic import BaseModel, Field

# Danh sách GỢI Ý (không còn là tập ĐÓNG) — Classification Agent ưu tiên dùng lại 1 trong các nhãn
# này khi review thực sự khớp, nhưng ĐƯỢC PHÉP tự đặt nhãn chủ đề mới hợp lý khi không nhóm nào
# khớp (xem CLASSIFICATION_PROMPT trong src/analysis/classification.py — trước đây ép "ĐÚNG MỘT
# trong 9 nhóm", giờ mở rộng được để không gán ép review vào 1 nhóm không thực sự phù hợp). Danh
# sách này vẫn là NGUỒN THAM CHIẾU DUY NHẤT cho các nhãn "lõi" — Pain Point Agent
# (src/analysis/pain_point.py) gom nhóm theo ĐÚNG CHUỖI topic_label bất kể nhãn đó có nằm trong
# danh sách gợi ý hay do model tự đặt, nên nhãn mới PHẢI ngắn gọn/nhất quán để không vỡ vụn cụm.
SUGGESTED_TOPIC_LABELS: tuple[str, ...] = (
    "lỗi đăng nhập",
    "khóa tài khoản",
    "lỗi giao dịch",
    "lỗi ứng dụng",
    "chăm sóc khách hàng",
    "thái độ nhân viên",
    "chính sách",
    "phí dịch vụ",
    "trải nghiệm sử dụng",
)


class ClassificationResult(BaseModel):
    """Structured output của Classification Agent — ghi vào predictions.sentiment/topic_label/
    severity_score/confidence_score."""

    sentiment: Literal["positive", "neutral", "negative"] = Field(description="Cảm xúc tổng thể của review")
    # str (không phải Literal[9] như trước) — topic_label giờ MỞ, model được tự đặt nhãn mới ngoài
    # SUGGESTED_TOPIC_LABELS khi hợp lý (xem prompt). max_length=50 khớp đúng cột
    # predictions.topic_label (String(50)) — chặn sớm ở tầng schema thay vì để INSERT DB lỗi vì
    # model lỡ trả về 1 nhãn quá dài.
    topic_label: str = Field(
        min_length=1,
        max_length=50,
        description=(
            "Chủ đề chính của review. Ưu tiên dùng lại đúng 1 nhãn trong danh sách gợi ý nếu review "
            "thực sự khớp; chỉ tự đặt nhãn MỚI khi không nhóm nào phù hợp. Nhãn mới phải ngắn gọn "
            "(2-4 từ tiếng Việt, dạng cụm danh từ) và NHẤT QUÁN — nhiều review khác nhau cùng nói về "
            "1 vấn đề phải dùng lại đúng cùng 1 nhãn, vì nhãn này là khoá để gom nhóm Pain Point."
        ),
    )
    severity_score: float = Field(ge=0.0, le=1.0, description="Mức độ nghiêm trọng: 0=không nghiêm trọng, 1=rất nghiêm trọng")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Độ tin cậy của model vào kết quả phân loại này")
    content_reliability: Literal["high", "medium", "low"] = Field(
        description=(
            "Độ tin cậy của NỘI DUNG review dựa trên tính cụ thể của mô tả (KHÔNG phải xác minh danh tính "
            "người viết). high: nêu được chi tiết kiểm chứng được (thao tác cụ thể, thời điểm, mã lỗi, số "
            "tiền, tên tính năng). medium: có mô tả hiện tượng nhưng thiếu chi tiết cụ thể. low: chung "
            "chung, cảm tính, không mô tả hiện tượng nào (vd 'app tệ', 'chán')."
        )
    )
    is_question: bool = Field(
        description=(
            "True nếu nội dung CHỦ YẾU là một câu hỏi/thắc mắc của khách (vd 'app này có thu phí gì "
            "không?', 'sao chưa thấy tiền về tài khoản?'), False nếu là nhận xét/phàn nàn/khen chê thông "
            "thường. ĐỘC LẬP với sentiment — 1 câu hỏi vẫn có thể mang giọng điệu tiêu cực/tích cực."
        )
    )


class ReferenceSource(BaseModel):
    """Một tài liệu tham chiếu mà Verification Agent tìm thấy khớp với review."""

    doc_id: str = Field(description="ID tài liệu trong knowledge base")
    title: str
    url: str
    relation: Literal["explains_as_policy", "confirms_issue"] = Field(
        description=(
            "explains_as_policy: tài liệu giải thích đây là hành vi đúng theo quy định/chính sách đã biết, "
            "không phải lỗi. confirms_issue: tài liệu xác nhận đây là sự cố/vấn đề có thật đã được ghi nhận."
        )
    )


class VerificationResult(BaseModel):
    """Structured output của Verification Agent — ghi vào predictions.reference_status/
    reference_sources/reference_confidence.

    Đây là ĐỐI CHIẾU VĂN BẢN chính thức, không phải xác minh danh tính khách hàng."""

    reference_status: Literal["matched", "no_match", "conflicting"] = Field(
        description=(
            "matched: tìm được tài liệu tham chiếu khớp rõ ràng. no_match: không tìm được tài liệu nào "
            "liên quan (bình thường với đa số bug thông thường). conflicting: các tài liệu tìm được mâu thuẫn nhau."
        )
    )
    reference_sources: list[ReferenceSource] = Field(default_factory=list)
    reference_confidence: float = Field(ge=0.0, le=1.0)


class SeedingResult(BaseModel):
    """Structured output của Seeding Agent — ghi vào predictions.is_seeding/seeding_reasoning. CHỈ
    gắn cờ CẢNH BÁO, KHÔNG tự loại bài khỏi tính pain point (khác is_spam/is_duplicate — xem
    src/pipeline/processing/spam.py, content_dedup.py) — để con người tự quyết định."""

    is_seeding: bool = Field(
        description="True nếu nghi ngờ đây là review/bình luận GIẢ MẠO, DÀN DỰNG (seeding) — không phải phàn nàn/khen thật."
    )
    reasoning: str = Field(description="Lý do ngắn gọn cho kết luận trên, kể cả khi is_seeding=False.")


class NewsSentimentResult(BaseModel):
    """Structured output của News Sentiment Agent — ghi vào official_documents.sentiment. Đơn giản
    hơn nhiều so với ClassificationResult (không có topic_label/severity/content_reliability/
    is_question): đây là tin BÊN THỨ BA về doanh nghiệp, không phải phản hồi khách hàng cần gom
    pain point hay đối chiếu chính sách — chỉ cần biết truyền thông đang đưa tin thế nào."""

    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description=(
            "Sắc thái ĐƯA TIN về doanh nghiệp trong bài báo — KHÔNG phải cảm xúc của người viết. "
            "positive: khen ngợi/tin vui (giải thưởng, tăng trưởng, sản phẩm được đón nhận tốt). "
            "neutral: thông tin thuần tuý, thông báo/sự kiện không rõ khen hay chê. "
            "negative: phê phán/tin xấu (sự cố, khiếu nại, vi phạm quy định, khủng hoảng truyền thông)."
        )
    )
