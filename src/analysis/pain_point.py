import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.analysis.department_routing import auto_route_pain_point
from src.analysis.llm import extract_text, get_analysis_llm, pop_usage_log, record_usage, reset_usage_log
from src.analysis.usage_tracking import persist_usage_log
from src.config import get_settings
from src.db.models import PainPoint, PainPointPost, Post, Prediction, Topic
from src.notifications.service import check_and_notify
from src.sla import CLOSED_LIFECYCLE_STATUSES, compute_due_at

logger = logging.getLogger(__name__)

TREND_WINDOW_DAYS = 7
TREND_CHANGE_THRESHOLD = 0.2  # +/-20% để tránh coi dao động nhỏ là xu hướng
SAMPLE_POST_COUNT = 3


def compute_trend(recent_count: int, prior_count: int) -> str:
    """So sánh số post trong 2 khoảng thời gian liên tiếp để xác định xu hướng."""
    if prior_count == 0:
        return "increasing" if recent_count > 0 else "stable"
    change_ratio = (recent_count - prior_count) / prior_count
    if change_ratio > TREND_CHANGE_THRESHOLD:
        return "increasing"
    if change_ratio < -TREND_CHANGE_THRESHOLD:
        return "decreasing"
    return "stable"


def aggregate_reference_status(reference_statuses: list[str]) -> str:
    """PainPoint.reference_status — gộp kết quả ĐỐI CHIẾU VĂN BẢN của các post thành viên trong
    cụm (không phải xác minh danh tính, cũng không phải trạng thái xử lý)."""
    if not reference_statuses:
        return "no_match"
    if "conflicting" in reference_statuses:
        return "conflicting"
    matched_count = reference_statuses.count("matched")
    no_match_count = reference_statuses.count("no_match")
    if matched_count > 0 and no_match_count > 0:
        return "conflicting"  # trong cùng 1 nhóm mà chỗ khớp văn bản chỗ không -> cần người xem lại
    return "matched" if matched_count > 0 else "no_match"


def run_pain_point_agent(session: Session, topic: Topic, min_posts: int | None = None) -> list[PainPoint]:
    """Pain Point Agent: gom post đã có prediction theo (topic, topic_label) — topic_label là ranh
    giới cụm tự nhiên. topic_label không còn giới hạn ở 9 nhóm cố định (Classification Agent có thể
    tự đặt nhãn mới ngoài SUGGESTED_TOPIC_LABELS khi hợp lý — xem src/analysis/schemas.py), nhưng
    việc gom nhóm ở đây vẫn dựa vào so khớp CHUỖI CHÍNH XÁC — nhãn mới không nhất quán giữa các
    review cùng vấn đề sẽ tự tách thành nhiều PainPoint riêng thay vì gộp lại. Nhóm đạt ngưỡng
    alert_threshold của Topic mới tạo/cập nhật PainPoint.

    CHỈ gom review sentiment=negative — "pain point" (điểm đau) đúng nghĩa là vấn đề khách hàng
    đang gặp, không phải mọi review thuộc cùng 1 chủ đề bất kể cảm xúc. Trước đây gom cả review
    tích cực/trung lập cùng nhóm topic_label, nên vd nhóm "trải nghiệm sử dụng" có thể đầy nhóm
    được tạo chỉ vì có nhiều review KHEN chung chủ đề, không phải vì đó là vấn đề thật."""
    threshold = min_posts if min_posts is not None else topic.alert_threshold

    rows = (
        session.query(Post, Prediction)
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(Post.topic_id == topic.id, Prediction.consensus_status.isnot(None), Prediction.sentiment == "negative")
        .all()
    )

    groups: dict[str, list[tuple[Post, Prediction]]] = defaultdict(list)
    for post, prediction in rows:
        if prediction.topic_label:
            groups[prediction.topic_label].append((post, prediction))

    # Từng nhóm xử lý độc lập — 1 nhóm lỗi (vd LLM tạo mô tả bị rate-limit, xem
    # _upsert_pain_point) không được làm mất kết quả của các nhóm khác đã xử lý xong trong cùng
    # lượt chạy. Trước đây dùng list comprehension: 1 exception ở bất kỳ đâu làm rớt toàn bộ,
    # session.commit() không bao giờ chạy tới -> post_count/trend/status đã tính đúng cũng bị mất.
    pain_points = []
    reset_usage_log()
    for topic_label, items in groups.items():
        if len(items) < threshold:
            continue
        try:
            pain_points.append(_upsert_pain_point(session, topic, topic_label, items))
        except Exception:
            logger.exception(
                "Lỗi khi tạo/cập nhật pain point '%s' (topic=%s) — bỏ qua nhóm này, tiếp tục nhóm khác",
                topic_label,
                topic.name,
            )
            session.rollback()
    # 1 lượt reset/pop cho CẢ topic (không phải từng pain point riêng) — _generate_description là
    # lệnh gọi LLM duy nhất trong vòng lặp trên, và mọi pain point ở đây đều cùng topic_id/user_id
    # nên gộp lại ghi 1 lần cho gọn, không đổi ý nghĩa dữ liệu.
    persist_usage_log(session, pop_usage_log(), user_id=topic.user_id, topic_id=topic.id)

    session.commit()

    for pain_point in pain_points:
        try:
            check_and_notify(session, pain_point)
        except Exception:
            # Gửi email qua SMTP có thể lỗi (mạng, xác thực...) — không để 1 lần gửi lỗi làm mất
            # thông báo của các pain point khác, hay tệ hơn là làm crash cả chu kỳ phân tích (topic
            # sau trong vòng lặp của run_analysis_cycle sẽ không được xử lý pain point nếu lỗi này
            # văng ra tới đó). Pain point đã được lưu ở trên rồi, chỉ mất mỗi thông báo lần này.
            logger.exception(
                "Lỗi khi gửi notification cho pain_point='%s' (topic=%s) — bỏ qua, tiếp tục", pain_point.title, topic.name
            )
            session.rollback()

        try:
            auto_route_pain_point(session, pain_point, topic)
        except Exception:
            # Tự nuốt lỗi ở nội bộ auto_route_pain_point rồi (LLM/notification) — bọc thêm 1 lớp ở
            # đây phòng lỗi bất ngờ khác (vd DB tạm thời), cùng triết lý cô lập lỗi từng pain point
            # với check_and_notify ở trên.
            logger.exception(
                "Lỗi khi tự động phân việc phòng ban cho pain_point='%s' (topic=%s) — bỏ qua, tiếp tục",
                pain_point.title,
                topic.name,
            )
            session.rollback()

    return pain_points


def _upsert_pain_point(session: Session, topic: Topic, topic_label: str, items: list) -> PainPoint:
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(days=TREND_WINDOW_DAYS)
    prior_cutoff = now - timedelta(days=TREND_WINDOW_DAYS * 2)

    recent_count = sum(1 for post, _ in items if post.collected_at and post.collected_at >= recent_cutoff)
    prior_count = sum(
        1 for post, _ in items if post.collected_at and prior_cutoff <= post.collected_at < recent_cutoff
    )
    trend = compute_trend(recent_count, prior_count)

    severity_scores = [p.severity_score for _, p in items if p.severity_score is not None]
    confidence_scores = [p.final_confidence for _, p in items if p.final_confidence is not None]
    reference_statuses = [p.reference_status for _, p in items if p.reference_status]
    source_types = sorted({post.source.type for post, _ in items if post.source})

    pain_point = session.query(PainPoint).filter_by(topic_id=topic.id, title=topic_label).first()
    if pain_point is None:
        pain_point = PainPoint(topic_id=topic.id, title=topic_label)
        session.add(pain_point)

    # Mô tả là do LLM viết (văn bản diễn giải cho người đọc) — KHÔNG được để lỗi/rate-limit của
    # riêng bước này chặn mất các trường cốt lõi bên dưới (post_count/trend/severity/status), vốn
    # tính hoàn toàn từ dữ liệu đã có sẵn, không phụ thuộc LLM. Lỗi thì giữ mô tả cũ (nếu có) thay
    # vì làm rớt luôn cả pain point.
    #
    # Chỉ gọi LLM khi CÓ GÌ MỚI để mô tả lại (case mới hoặc post_count đổi) — trước đây gọi lại
    # MỖI chu kỳ cho MỌI pain point dù không đổi gì, nên khi quota Gemini hết (rất hay xảy ra ở
    # free-tier), pain point đứng đầu vòng lặp "ăn" hết thời gian retry, các topic phía sau (vd TP
    # Bank/TPBank Mobile) không bao giờ được xử lý trong 1 chu kỳ dù dữ liệu đã đủ ngưỡng từ lâu.
    needs_new_description = pain_point.description is None or pain_point.post_count != len(items)
    if needs_new_description:
        try:
            pain_point.description = _generate_description(topic_label, items)
        except Exception:
            logger.warning(
                "Lỗi khi tạo mô tả pain point '%s' (topic=%s) qua LLM — giữ mô tả cũ, vẫn cập nhật các trường còn lại",
                topic_label,
                topic.name,
            )
            if pain_point.description is None:
                pain_point.description = f"{len(items)} phản hồi thuộc nhóm '{topic_label}'."
    pain_point.post_count = len(items)
    pain_point.trend = trend
    pain_point.sources = source_types
    pain_point.severity_avg = sum(severity_scores) / len(severity_scores) if severity_scores else None
    pain_point.confidence_avg = sum(confidence_scores) / len(confidence_scores) if confidence_scores else None
    pain_point.reference_status = aggregate_reference_status(reference_statuses)

    # Hạn SLA tính lại mỗi chu kỳ khi case còn mở: severity_avg thay đổi theo phản hồi mới nên có
    # thể nhảy bậc (vd trung bình -> nghiêm trọng thì hạn rút từ 72h xuống 24h). Case đã đóng thì
    # giữ nguyên hạn cũ để không viết lại lịch sử. Case có due_at_overridden=True nghĩa là quản lý
    # đã tự đặt hạn riêng (xem PATCH .../lifecycle) — auto-recompute phải bỏ qua, không được ghi đè.
    if pain_point.lifecycle_status not in CLOSED_LIFECYCLE_STATUSES and not pain_point.due_at_overridden:
        pain_point.due_at = compute_due_at(pain_point.created_at or now, pain_point.severity_avg)

    session.flush()

    # Link lại representative sample posts (idempotent qua các lần chạy).
    session.query(PainPointPost).filter_by(pain_point_id=pain_point.id).delete()
    sample_items = sorted(items, key=lambda x: x[1].severity_score or 0, reverse=True)[:SAMPLE_POST_COUNT]
    for post, _ in sample_items:
        session.add(PainPointPost(pain_point_id=pain_point.id, post_id=post.id, is_sample=True))

    logger.info(
        "Pain point '%s' (topic=%s): %d post, trend=%s, đối chiếu văn bản=%s",
        topic_label,
        topic.name,
        len(items),
        trend,
        pain_point.reference_status,
    )
    return pain_point


def _generate_description(topic_label: str, items: list) -> str:
    llm = get_analysis_llm(temperature=0.3)
    sample_texts = "\n".join(f"- {post.content[:200]}" for post, _ in items[:5])
    prompt = (
        f"Tóm tắt ngắn gọn (2-3 câu tiếng Việt) vấn đề chung của {len(items)} phản hồi khách hàng "
        f"ngân hàng về chủ đề '{topic_label}' dựa trên các ví dụ sau:\n{sample_texts}"
    )
    response = llm.invoke(prompt)
    record_usage("pain_point_description", response, get_settings().analysis_model_name)
    return extract_text(response.content)
