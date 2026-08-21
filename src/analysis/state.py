from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from src.analysis.knowledge_base.loader import KnowledgeDoc
from src.analysis.schemas import ClassificationResult, SeedingResult, VerificationResult


class AnalysisState(TypedDict, total=False):
    """State schema cho LangGraph: classify -> detect_seeding -> verify -> consensus, chạy trên 1
    Post."""

    post_id: UUID
    content: str
    # Tài liệu tham chiếu crawl được của TOPIC này (đã lọc còn liên quan) — caller
    # (_analyze_post_standalone) tự truy vấn DB rồi đưa vào state ban đầu, để verify_node vẫn là hàm
    # thuần trên state, không tự mở DB session bên trong graph.
    topic_docs: list[KnowledgeDoc]
    # Số bài viết CÙNG topic nội dung/giọng văn tương tự đăng gần đây — caller tự truy vấn DB trước
    # (src/pipeline/processing/seeding.py::count_similar_recent_posts) rồi đưa vào state ban đầu,
    # cùng triết lý với topic_docs ở trên (node phân tích thuần, không tự mở session).
    similar_post_count: int
    classification: ClassificationResult
    # None nếu Seeding Agent lỗi/nuốt lỗi (xem graph.py::detect_seeding_node) — không chặn pipeline.
    seeding: SeedingResult
    verification: VerificationResult
    consensus_status: str
    reasoning: str
    final_confidence: float
    # None = chưa cross-check (xem graph.py::_should_cross_check, src/analysis/cross_check.py).
    # True/False = đã cross-check, model độc lập thứ 2 có đồng thuận hay không.
    cross_check_agreed: bool | None
    error: str
    quota_exhausted: bool
