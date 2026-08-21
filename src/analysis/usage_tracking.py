from uuid import UUID

from sqlalchemy.orm import Session

from src.analysis.llm import TokenUsage
from src.db.models import LLMUsage


def persist_usage_log(session: Session, usages: list[TokenUsage], *, user_id: UUID | None, topic_id: UUID | None) -> None:
    """Ghi các TokenUsage đã thu thập (xem pop_usage_log trong src/analysis/llm.py) thành các dòng
    `llm_usage` — gọi SAU khi 1 post/bài báo/nhóm pain point đã xử lý xong toàn bộ lệnh gọi LLM liên
    quan. KHÔNG tự commit — caller quyết định thời điểm commit, giống mọi nơi khác trong module này."""
    for usage in usages:
        session.add(
            LLMUsage(
                user_id=user_id,
                topic_id=topic_id,
                call_type=usage.call_type,
                model=usage.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        )
