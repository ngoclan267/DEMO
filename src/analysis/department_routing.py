import logging

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.analysis.llm import get_structured_analysis_llm, record_usage
from src.config import get_settings
from src.db.models import PainPoint, PainPointEvent, Topic, TopicMember
from src.notifications.service import notify_department_assignment

logger = logging.getLogger(__name__)

DEPARTMENT_ROUTING_PROMPT = """Bạn giúp phân việc xử lý pain point (vấn đề khách hàng đang gặp) cho \
đúng phòng ban của ngân hàng. Dưới đây là 1 pain point và danh sách CÁC PHÒNG BAN THẬT đang có nhân \
viên xử lý case ở ngân hàng này.

QUAN TRỌNG: CHỈ được chọn ĐÚNG 1 tên trong danh sách cho trước (copy y hệt, không tự đặt tên mới, \
không suy diễn ra phòng ban không có trong danh sách). Nếu không phòng ban nào trong danh sách thực \
sự phù hợp, trả về department=null — KHÔNG được ép chọn đại 1 phòng ban không liên quan.

Pain point: "{title}"
Mô tả: "{description}"

Danh sách phòng ban đang có ở ngân hàng này:
{departments}
"""


class DepartmentMatch(BaseModel):
    department: str | None = Field(
        description=(
            "Tên phòng ban PHÙ HỢP NHẤT, copy y hệt 1 trong danh sách cho trước. "
            "null nếu không phòng ban nào trong danh sách thực sự phù hợp."
        )
    )
    reasoning: str = Field(description="Lý do ngắn gọn cho lựa chọn trên.")


def auto_route_pain_point(session: Session, pain_point: PainPoint, topic: Topic) -> None:
    """Tự động gán PHÒNG BAN (không chọn người cụ thể) cho pain point mới/chưa có phòng ban — gọi
    từ src/analysis/pain_point.py::run_pain_point_agent ngay sau khi upsert + check_and_notify,
    cùng cách check_and_notify gate theo Topic.notify_enabled. Không tự chọn assigned_user_id — cả
    phòng ban nhận thông báo, ai xử lý trước tự nhận qua LifecyclePanel có sẵn (quyết định sản phẩm
    đã chốt, xem plan)."""
    if not topic.auto_assign_enabled:
        return
    if pain_point.department is not None:
        # Đã có phòng ban (do người dùng tự chọn tay hoặc chu kỳ trước đã tự động gán) — không ghi
        # đè, tôn trọng quyết định đã có.
        return

    departments = sorted(
        {
            department
            for (department,) in session.query(TopicMember.department)
            .filter(TopicMember.topic_id == topic.id, TopicMember.department.isnot(None))
            .distinct()
            .all()
        }
    )
    if not departments:
        # Chưa nhân viên nào trong chủ đề được gán phòng ban — không có gì để định tuyến tới.
        return

    try:
        match = _match_department(pain_point, departments)
    except Exception:
        logger.warning(
            "Lỗi khi tự động chọn phòng ban cho pain_point='%s' (topic=%s) — bỏ qua, để trống cho xử lý thủ công",
            pain_point.title,
            topic.name,
            exc_info=True,
        )
        return

    if match.department is None or match.department not in departments:
        logger.info(
            "Không tìm được phòng ban phù hợp cho pain_point='%s' (topic=%s) — để trống", pain_point.title, topic.name
        )
        return

    pain_point.department = match.department
    session.add(
        PainPointEvent(
            pain_point_id=pain_point.id,
            # user_id=None — hành động của HỆ THỐNG, không phải người dùng thao tác (khác mọi
            # PainPointEvent khác trong routes_dashboard.py::update_pain_point_lifecycle).
            user_id=None,
            note=f"Hệ thống tự động gán phòng ban \"{match.department}\": {match.reasoning}",
        )
    )
    session.commit()
    logger.info(
        "Tự động gán phòng ban '%s' cho pain_point='%s' (topic=%s)", match.department, pain_point.title, topic.name
    )

    try:
        notify_department_assignment(session, pain_point, match.department)
    except Exception:
        # Gửi thông báo lỗi (mạng, SMTP/Brevo...) không được làm mất việc gán phòng ban đã lưu ở
        # trên — cùng triết lý check_and_notify trong run_pain_point_agent.
        logger.exception(
            "Lỗi khi gửi thông báo phân việc phòng ban cho pain_point='%s' (topic=%s) — bỏ qua",
            pain_point.title,
            topic.name,
        )
        session.rollback()


def _match_department(pain_point: PainPoint, departments: list[str]) -> DepartmentMatch:
    llm = get_structured_analysis_llm(DepartmentMatch, include_raw=True)
    prompt = DEPARTMENT_ROUTING_PROMPT.format(
        title=pain_point.title,
        description=pain_point.description or "",
        departments="\n".join(f"- {d}" for d in departments),
    )
    response = llm.invoke(prompt)
    if response.get("parsing_error") is not None:
        raise response["parsing_error"]
    result = response["parsed"]
    record_usage("department_routing", response.get("raw"), get_settings().analysis_model_name)
    return result
