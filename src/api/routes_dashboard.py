import logging
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from src.api.deps import get_accessible_topic, is_topic_participant
from src.api.schemas_dashboard import (
    DashboardSummary,
    HourlyTrendPoint,
    LifecycleUpdateRequest,
    PainPointEventResponse,
    PainPointSummary,
    PeriodComparisonResponse,
    PeriodStats,
    PeriodTrendPoint,
    PostDetail,
    PostSummary,
    SourceRef,
    TrendPoint,
)
from src.auth.dependencies import get_current_user
from src.db.models import OfficialDocument, PainPoint, PainPointEvent, Post, Prediction, Source, Topic, TopicMember, User
from src.db.session import get_db
from src.logging_config import VN_TZ
from src.notifications.service import notify_assignment, notify_resolution
from src.sla import CLOSED_LIFECYCLE_STATUSES, SEVERITY_RANGES, compute_due_at, is_breached, severity_bucket

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])

DUE_SOON_HOURS = 24  # ngưỡng "sắp đến hạn" hiển thị trên dashboard
TREND_DAYS = 30  # cửa sổ mặc định cho biểu đồ xu hướng — xem get_dashboard/get_pain_point_trend


def _build_app_url(source: Source | None) -> str | None:
    """Nguồn (source) ở mức app, không phải permalink từng review — Google Play/App Store không
    cung cấp permalink review riêng lẻ. Nếu Source.config đã có package_name/app_id (khai báo trực
    tiếp) thì trỏ thẳng vào trang app; nếu chỉ có "query" (source tự tìm bằng tên ngân hàng — xem
    src/pipeline/collectors/) thì trỏ vào trang kết quả tìm kiếm tương ứng."""
    if source is None:
        return None
    config = source.config or {}
    country = config.get("country", "us")

    if source.type == "google_play":
        if config.get("package_name"):
            return f"https://play.google.com/store/apps/details?id={config['package_name']}"
        if config.get("query"):
            return f"https://play.google.com/store/search?q={quote(config['query'])}&c=apps"
    if source.type == "app_store":
        if config.get("app_id"):
            return f"https://apps.apple.com/{country}/app/id{config['app_id']}"
        if config.get("query"):
            # Trước đây hardcode "/us/" bất kể country thật của config — với app chỉ có mặt ở
            # store VN (vd "vn"), link /us/search trả trang không tìm thấy. Đồng thời query có
            # khoảng trắng (vd "SHB SAHA") chưa được encode, có thể bị server từ chối.
            return f"https://apps.apple.com/{country}/search?term={quote(config['query'])}"
    return None


def _post_to_summary(post: Post, pain_point_lifecycle_status: str | None = None) -> PostSummary:
    prediction = post.prediction
    return PostSummary(
        id=post.id,
        content=post.content or "",
        language=post.language,
        sentiment=prediction.sentiment if prediction else None,
        topic_label=prediction.topic_label if prediction else None,
        severity_score=prediction.severity_score if prediction else None,
        is_spam=post.is_spam,
        is_seeding=prediction.is_seeding if prediction else False,
        seeding_reasoning=prediction.seeding_reasoning if prediction else None,
        posted_at=post.posted_at,
        collected_at=post.collected_at,
        source_type=post.source.type if post.source else None,
        pain_point_lifecycle_status=pain_point_lifecycle_status,
        priority_score=post.priority_score,
        like_count=post.like_count,
        comment_count=post.comment_count,
        share_count=post.share_count,
        is_question=prediction.is_question if prediction else None,
        parent_post_id=post.parent_post_id,
        source_url=post.source_url,
    )


def _pain_point_lifecycle_status_for_post(db: Session, post: Post) -> str | None:
    """Post thuộc pain point nào (nếu có) — cùng khoá (topic_id, topic_label==title, sentiment=
    negative) đã dùng ở list_topic_posts/list_pain_point_posts. sentiment=negative bắt buộc vì
    Pain Point Agent CHỈ gom review tiêu cực vào pain point (xem src/analysis/pain_point.py) —
    post tích cực/trung lập cùng topic_label không thực sự thuộc case nào, dù trùng nhóm chủ đề.
    Dùng cho các endpoint đơn-lẻ 1 post, nơi join sẵn vào câu query chính không tiện bằng."""
    prediction = post.prediction
    if prediction is None or prediction.topic_label is None or prediction.sentiment != "negative":
        return None
    return (
        db.query(PainPoint.lifecycle_status)
        .filter(PainPoint.topic_id == post.topic_id, PainPoint.title == prediction.topic_label)
        .scalar()
    )


def _post_to_detail(post: Post, pain_point_lifecycle_status: str | None = None) -> PostDetail:
    prediction = post.prediction
    return PostDetail(
        **_post_to_summary(post, pain_point_lifecycle_status=pain_point_lifecycle_status).model_dump(),
        verification_status=prediction.verification_status if prediction else None,
        content_reliability=prediction.content_reliability if prediction else None,
        reference_status=prediction.reference_status if prediction else None,
        reference_sources=prediction.reference_sources if prediction else [],
        consensus_status=prediction.consensus_status if prediction else None,
        reasoning=prediction.reasoning if prediction else None,
        cross_check_agreed=prediction.cross_check_agreed if prediction else None,
        source=SourceRef(source_type=post.source.type, app_url=_build_app_url(post.source)) if post.source else None,
        reply_content=post.reply_content,
        reply_at=post.reply_at,
    )


def _pain_point_order_by() -> tuple:
    """Thứ tự mặc định cho MỌI danh sách pain point (list_pain_points, top_pain_points trong
    get_dashboard): pain point được doanh nghiệp TỰ đánh dấu (is_priority=True, xem PATCH
    .../lifecycle) luôn đứng đầu — đây là lựa chọn CHỦ ĐỘNG, ưu tiên hơn xếp hạng tự động. Trong
    số các pain point CÙNG mức is_priority, sắp theo severity_avg (mức độ nghiêm trọng — đại diện
    cho "quan trọng với 1 NGÂN HÀNG": rủi ro/tuân thủ/ảnh hưởng khách hàng) thay vì post_count (chỉ
    phản ánh SỐ LƯỢNG phàn nàn, không phản ánh mức độ nghiêm trọng) — post_count chỉ dùng làm tiêu
    chí phân định cuối cùng khi severity_avg bằng nhau (hoặc đều NULL, case chưa có dự đoán nào)."""
    return (
        PainPoint.is_priority.desc(),
        PainPoint.severity_avg.desc().nullslast(),
        PainPoint.post_count.desc(),
    )


def _pain_point_to_summary(pain_point: PainPoint, now: datetime | None = None) -> PainPointSummary:
    now = now or datetime.now(UTC)
    return PainPointSummary(
        id=pain_point.id,
        title=pain_point.title,
        description=pain_point.description,
        post_count=pain_point.post_count,
        trend=pain_point.trend,
        reference_status=pain_point.reference_status,
        severity_avg=pain_point.severity_avg,
        confidence_avg=pain_point.confidence_avg,
        sources=pain_point.sources or [],
        is_priority=pain_point.is_priority,
        lifecycle_status=pain_point.lifecycle_status,
        assigned_user=pain_point.assigned_user,
        department=pain_point.department,
        due_at=pain_point.due_at,
        due_at_overridden=pain_point.due_at_overridden,
        resolved_at=pain_point.resolved_at,
        duplicate_of_id=pain_point.duplicate_of_id,
        lifecycle_note=pain_point.lifecycle_note,
        is_breached=is_breached(pain_point.lifecycle_status, pain_point.due_at, now),
        severity_level=severity_bucket(pain_point.severity_avg),
    )


def _get_accessible_pain_point(pain_point_id: UUID, current_user: User, db: Session) -> PainPoint:
    """Pain point thuộc chủ đề mà user là chủ sở hữu HOẶC thành viên."""
    pain_point = (
        db.query(PainPoint)
        .join(Topic, Topic.id == PainPoint.topic_id)
        .outerjoin(TopicMember, TopicMember.topic_id == Topic.id)
        .filter(
            PainPoint.id == pain_point_id,
            (Topic.user_id == current_user.id) | (TopicMember.user_id == current_user.id),
        )
        .first()
    )
    if pain_point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy pain point")
    return pain_point


def _filter_by_source(query, source_type: str | None):
    """JOIN + lọc theo Source.type — CHỈ khi source_type có giá trị, để không đổi kết quả/kế hoạch
    truy vấn của mọi lệnh gọi hiện có (mặc định source_type=None, xem get_dashboard). Dùng lại cho
    mọi thống kê theo POST (tổng/đã phân tích/tiêu cực/severity/sentiment/negative_by_group/trend)
    — CHỦ Ý KHÔNG áp cho source_breakdown (đó chính là bảng phân rã theo TỪNG nguồn, lọc còn 1
    nguồn thì mất tác dụng — dùng để hiển thị đủ nút chọn nguồn dù đang lọc theo nguồn nào) hay
    top_pain_points/lifecycle_breakdown (pain point gom theo topic_label, không map 1-1 về 1 nguồn
    cụ thể qua PainPointPost mà không cần thêm join phức tạp, ngoài phạm vi yêu cầu lọc biểu đồ)."""
    if source_type is None:
        return query
    return query.join(Source, Source.id == Post.source_id).filter(Source.type == source_type)


@router.get("/topics/{topic_id}/dashboard", response_model=DashboardSummary)
def get_dashboard(
    topic_id: UUID,
    source_type: str | None = Query(default=None, description="Lọc toàn bộ thống kê theo nguồn (vd 'google_play')"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    topic = get_accessible_topic(topic_id, current_user, db)
    now = datetime.now(UTC)
    # "Mới" nghĩa là khách đăng review gần đây — dùng posted_at (ngày đăng thật) khi có, chỉ rơi
    # về collected_at (ngày hệ thống thu thập) khi nguồn không cung cấp posted_at. Dùng cho biểu đồ
    # xu hướng bên dưới — các số liệu tổng hợp (severity/pain point/tiêu cực) đều tính trên TOÀN BỘ
    # dữ liệu đã phân tích, không giới hạn theo ngày, để nhất quán với nhau trên cùng 1 trang.
    effective_date = func.coalesce(Post.posted_at, Post.collected_at)

    total_posts_count = (
        _filter_by_source(db.query(func.count(Post.id)).filter(Post.topic_id == topic.id), source_type).scalar() or 0
    )

    # Mẫu số chung cho severity_breakdown, negative_posts_count và top_pain_points bên dưới — cả 3
    # đều tính trên toàn bộ dữ liệu đã phân tích, không giới hạn thời gian, để các con số hiển thị
    # cùng trang luôn đối chiếu khớp được với nhau (vd severity_breakdown phải cộng đúng bằng số
    # này).
    analyzed_posts_count = (
        _filter_by_source(
            db.query(func.count(Post.id)).join(Prediction, Prediction.post_id == Post.id).filter(Post.topic_id == topic.id),
            source_type,
        ).scalar()
        or 0
    )

    # Quota LLM free-tier có hạn (xem DEFAULT_CONCURRENCY trong src/analysis/runner.py) nên không
    # thể phân tích hết review ngay khi thu thập — hiển thị số còn lại để người dùng biết các con
    # số sentiment/severity bên dưới là CHƯA đầy đủ, không phải hệ thống bỏ sót review tiêu cực.
    pending_analysis_count = (
        db.query(func.count(Post.id))
        .outerjoin(Prediction, Prediction.post_id == Post.id)
        .filter(Post.topic_id == topic.id, Prediction.id.is_(None), Post.is_spam.is_(False), Post.is_duplicate.is_(False))
        .scalar()
        or 0
    )

    negative_posts_count = (
        _filter_by_source(
            db.query(func.count(Post.id))
            .join(Prediction, Prediction.post_id == Post.id)
            .filter(Post.topic_id == topic.id, Prediction.sentiment == "negative"),
            source_type,
        ).scalar()
        or 0
    )

    severity_rows = _filter_by_source(
        db.query(Prediction.severity_score)
        .join(Post, Post.id == Prediction.post_id)
        .filter(Post.topic_id == topic.id, Prediction.severity_score.isnot(None)),
        source_type,
    ).all()
    severity_breakdown = {"low": 0, "medium": 0, "high": 0}
    for (score,) in severity_rows:
        severity_breakdown[severity_bucket(score)] += 1

    source_post_rows = (
        db.query(Source.type, func.count(Post.id))
        .join(Post, Post.source_id == Source.id)
        .filter(Post.topic_id == topic.id)
        .group_by(Source.type)
        .all()
    )
    source_breakdown = dict(source_post_rows)
    # bank_website/news_article đi vào official_documents thay vì posts (xem
    # src/pipeline/collectors/facebook.py và reference_docs.py) — không cộng vào query trên thì 2
    # loại nguồn này LUÔN hiện 0 dù crawl thành công, dù đã thu thập được tài liệu/bài báo thật.
    source_doc_rows = (
        db.query(Source.type, func.count(OfficialDocument.id))
        .join(OfficialDocument, OfficialDocument.source_id == Source.id)
        .filter(OfficialDocument.topic_id == topic.id)
        .group_by(Source.type)
        .all()
    )
    # BIẾN VÒNG LẶP KHÔNG ĐƯỢC TRÙNG TÊN "source_type" — đó là THAM SỐ lọc của cả hàm (query param
    # ?source_type=...), mọi lệnh gọi _filter_by_source() PHÍA SAU (sentiment_rows,
    # negative_by_group_rows, trend_rows) đều đọc lại biến này. Lỗi THẬT đã xảy ra: vòng lặp này
    # từng dùng "source_type" làm tên biến, ghi đè mất giá trị tham số gốc (vd None khi không lọc)
    # bằng giá trị Source.type CUỐI CÙNG duyệt qua (vd "bank_website") — khiến trend/sentiment/
    # negative_by_group bị lọc NHẦM theo 1 nguồn ngẫu nhiên dù người dùng không hề chọn lọc gì,
    # trong khi total_posts_count/analyzed_posts_count (tính TRƯỚC vòng lặp này) vẫn đúng — đúng
    # triệu chứng quan sát được: "tổng số phản hồi" đúng nhưng biểu đồ trống trơn.
    for doc_source_type, count in source_doc_rows:
        source_breakdown[doc_source_type] = source_breakdown.get(doc_source_type, 0) + count

    sentiment_rows = _filter_by_source(
        db.query(Prediction.sentiment, func.count(Post.id))
        .join(Post, Post.id == Prediction.post_id)
        .filter(Post.topic_id == topic.id, Prediction.sentiment.isnot(None))
        .group_by(Prediction.sentiment),
        source_type,
    ).all()
    sentiment_breakdown = dict(sentiment_rows)

    negative_by_group_rows = _filter_by_source(
        db.query(Prediction.topic_label, func.count(Post.id))
        .join(Post, Post.id == Prediction.post_id)
        .filter(Post.topic_id == topic.id, Prediction.sentiment == "negative", Prediction.topic_label.isnot(None))
        .group_by(Prediction.topic_label),
        source_type,
    ).all()
    negative_by_group = dict(negative_by_group_rows)

    # 30 ngày gần nhất, CHỈ tính dữ liệu ĐÃ PHÂN TÍCH (JOIN thường với Prediction, không phải
    # outerjoin) — trước đây outerjoin khiến "Tổng số phản hồi" cộng cả post CHƯA phân tích (chỉ
    # negative_count mới thật sự lọc theo Prediction), làm đường tổng lẫn cả dữ liệu thô mới thu
    # thập chưa qua AI, không phản ánh đúng "toàn bộ dữ liệu đã phân tích". Giới hạn lại 30 ngày
    # (thay vì toàn bộ lịch sử) để biểu đồ tập trung vào diễn biến GẦN ĐÂY, đúng như tên "(30 ngày)".
    trend_start = now - timedelta(days=TREND_DAYS)
    # func.timezone(...) quy đổi timestamptz sang giờ tường (wall-clock) Việt Nam TRƯỚC khi lấy
    # ngày — không dùng func.date(effective_date) trực tiếp (tính theo timezone phiên Postgres,
    # mặc định UTC) để biểu đồ xu hướng không gộp nhầm review 00h-07h sáng giờ VN vào ngày hôm
    # trước. Cùng gốc bug với bộ lọc date_from/date_to phía trên — xem comment ở đó.
    trend_day = func.date(func.timezone(str(VN_TZ), effective_date))
    trend_rows = _filter_by_source(
        db.query(
            trend_day.label("day"),
            func.count(Post.id).label("count"),
            func.sum(case((Prediction.sentiment == "negative", 1), else_=0)).label("negative_count"),
        )
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(Post.topic_id == topic.id, effective_date >= trend_start)
        .group_by(trend_day)
        .order_by(trend_day),
        source_type,
    ).all()
    trend = [TrendPoint(date=row.day, count=row.count, negative_count=row.negative_count or 0) for row in trend_rows]

    all_pain_points = (
        db.query(PainPoint).filter(PainPoint.topic_id == topic.id).order_by(*_pain_point_order_by()).all()
    )

    # Đếm SLA trong Python (không phải SQL) để dùng đúng một định nghĩa quá hạn trong src/sla.py —
    # số pain point mỗi topic chỉ vài chục nên không đáng lo về hiệu năng.
    lifecycle_breakdown: dict[str, int] = {}
    overdue_count = 0
    due_soon_count = 0
    due_soon_cutoff = now + timedelta(hours=DUE_SOON_HOURS)
    for pp in all_pain_points:
        lifecycle_breakdown[pp.lifecycle_status] = lifecycle_breakdown.get(pp.lifecycle_status, 0) + 1
        if is_breached(pp.lifecycle_status, pp.due_at, now):
            overdue_count += 1
        elif (
            pp.due_at is not None
            and pp.lifecycle_status not in CLOSED_LIFECYCLE_STATUSES
            and pp.due_at <= due_soon_cutoff
        ):
            due_soon_count += 1

    return DashboardSummary(
        negative_posts_count=negative_posts_count,
        total_posts_count=total_posts_count,
        analyzed_posts_count=analyzed_posts_count,
        pending_analysis_count=pending_analysis_count,
        severity_breakdown=severity_breakdown,
        source_breakdown=source_breakdown,
        sentiment_breakdown=sentiment_breakdown,
        negative_by_group=negative_by_group,
        trend=trend,
        top_pain_points=[_pain_point_to_summary(pp, now) for pp in all_pain_points[:5]],
        overdue_count=overdue_count,
        due_soon_count=due_soon_count,
        lifecycle_breakdown=lifecycle_breakdown,
    )


@router.get("/topics/{topic_id}/trend/hourly", response_model=list[HourlyTrendPoint])
def get_topic_trend_hourly(
    topic_id: UUID,
    date: date = Query(description="Ngày cần xem chi tiết theo giờ (giờ Việt Nam), định dạng YYYY-MM-DD"),
    source_type: str | None = Query(default=None, description="Lọc theo nguồn (vd 'google_play') — khớp bộ lọc nguồn của biểu đồ theo ngày"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HourlyTrendPoint]:
    """Zoom chi tiết theo GIỜ cho đúng 1 ngày VN của biểu đồ xu hướng cả topic (TrendChart click vào
    1 điểm ngày) — cùng cách tính effective_date/quy đổi giờ VN với trend theo ngày ở get_dashboard,
    chỉ đổi func.date(...) thành func.date_trunc('hour', ...) và giới hạn đúng 1 ngày thay vì cả
    TREND_DAYS ngày. Nhận thêm source_type để khớp ĐÚNG bộ lọc nguồn đang chọn trên biểu đồ theo
    ngày (xem _filter_by_source ở get_dashboard) — không có tham số này thì zoom vào 1 ngày trong
    lúc đang lọc theo 1 nguồn cụ thể sẽ hiện lại dữ liệu CẢ topic, trông như bộ lọc "mất tác dụng"."""
    topic = get_accessible_topic(topic_id, current_user, db)
    effective_date = func.coalesce(Post.posted_at, Post.collected_at)
    vn_local = func.timezone(str(VN_TZ), effective_date)
    day_start = datetime.combine(date, time.min)
    day_end = day_start + timedelta(days=1)
    trend_hour = func.date_trunc("hour", vn_local)
    trend_rows = _filter_by_source(
        db.query(
            trend_hour.label("hour"),
            func.count(Post.id).label("count"),
            func.sum(case((Prediction.sentiment == "negative", 1), else_=0)).label("negative_count"),
        )
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(Post.topic_id == topic.id, vn_local >= day_start, vn_local < day_end),
        source_type,
    ).group_by(trend_hour).order_by(trend_hour).all()
    return [HourlyTrendPoint(hour=row.hour, count=row.count, negative_count=row.negative_count or 0) for row in trend_rows]


@router.get("/topics/{topic_id}/posts", response_model=list[PostSummary])
def list_topic_posts(
    topic_id: UUID,
    window_days: int | None = Query(default=None, ge=1, description="Chỉ lấy post thu thập trong N ngày gần nhất"),
    sentiment: str | None = Query(default=None, description="Lọc theo sentiment (vd 'negative')"),
    analyzed_only: bool = Query(default=False, description="Chỉ lấy post đã có kết quả phân tích"),
    q: str | None = Query(default=None, min_length=1, max_length=200, description="Tìm theo từ khoá trong nội dung"),
    source_type: str | None = Query(default=None, description="Lọc theo nguồn (vd 'google_play')"),
    severity: str | None = Query(default=None, pattern="^(low|medium|high)$", description="Lọc theo bậc nghiêm trọng"),
    date_from: date | None = Query(default=None, description="Từ ngày (theo posted_at, rơi về collected_at nếu NULL)"),
    date_to: date | None = Query(default=None, description="Đến ngày (bao gồm cả ngày này)"),
    lifecycle_status: str | None = Query(
        default=None, description="Lọc theo trạng thái xử lý của pain point chứa post này"
    ),
    is_question: bool | None = Query(default=None, description="Lọc theo cờ 'là câu hỏi/thắc mắc' (xem is_question)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PostSummary]:
    """Drill-down cho các ô thống kê trên dashboard, đồng thời là API lọc chính của trang danh sách
    phản hồi — mọi bộ lọc chạy ở DB (không lọc phía client) và kết hợp được với nhau (AND)."""
    topic = get_accessible_topic(topic_id, current_user, db)

    effective_date = func.coalesce(Post.posted_at, Post.collected_at)
    query = (
        db.query(Post, PainPoint.lifecycle_status)
        .outerjoin(Prediction, Prediction.post_id == Post.id)
        .outerjoin(Source, Post.source_id == Source.id)
        # Post thuộc pain point nào: cùng topic + topic_label khớp title + sentiment=negative —
        # đúng khoá đã dùng ở list_pain_point_posts (xem docstring _pain_point_lifecycle_status_for_post).
        # Post thuộc nhóm chưa đủ ngưỡng cảnh báo HOẶC không phải sentiment=negative thì không khớp
        # JOIN này, PainPoint.lifecycle_status trả None — hợp lý vì chưa/không thuộc case nào cả.
        .outerjoin(
            PainPoint,
            (PainPoint.topic_id == Post.topic_id)
            & (PainPoint.title == Prediction.topic_label)
            & (Prediction.sentiment == "negative"),
        )
        # CHỈ bài viết gốc — comment Facebook (Post.parent_post_id có giá trị) không hiện lẫn ở đây
        # để danh sách phẳng không bị vụn thành hàng nghìn comment thiếu ngữ cảnh bài viết cha; xem
        # chúng qua GET /posts/{post_id}/comments hoặc luồng Facebook riêng. Không đổi hành vi với
        # nguồn khác Facebook (parent_post_id luôn NULL).
        .filter(Post.topic_id == topic.id, Post.parent_post_id.is_(None))
    )
    if window_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        query = query.filter(effective_date >= cutoff)
    if sentiment is not None:
        query = query.filter(Prediction.sentiment == sentiment)
    if analyzed_only:
        query = query.filter(Prediction.id.isnot(None))
    if q is not None:
        # Escape ký tự đại diện của ILIKE ('%', '_') trong từ khoá người dùng gõ — tránh 1 từ khoá
        # tình cờ chứa ký tự này bị hiểu nhầm thành mẫu tìm kiếm.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Post.content.ilike(f"%{escaped}%", escape="\\"))
    if source_type is not None:
        query = query.filter(Source.type == source_type)
    if severity is not None:
        lo, hi = SEVERITY_RANGES[severity]
        query = query.filter(Prediction.severity_score >= lo, Prediction.severity_score < hi)
    if date_from is not None:
        # So khớp theo NGÀY DƯƠNG LỊCH GIỜ VIỆT NAM (VN_TZ), KHÔNG phải func.date(effective_date)
        # so trực tiếp với date_from như trước — func.date() tính "ngày" theo timezone phiên
        # Postgres (mặc định UTC, xem docker-compose.yml không set TZ), lệch 7 tiếng với lịch VN
        # thật. Hậu quả THẬT đã xảy ra: review đăng 00h-07h sáng giờ VN có UTC vẫn là tối hôm
        # trước, nên bị tính nhầm sang ngày hôm trước — lọc "ngày X" bỏ sót/lẫn review sát nửa đêm.
        # Quy đổi date_from/date_to thành đúng mốc thời khắc (instant) 00:00 giờ VN rồi so trực tiếp
        # trên cột timestamptz — so instant-với-instant luôn đúng bất kể session timezone của
        # Postgres là gì (cùng cách đã dùng cho "today_start" ở routes_auth.py/pipeline/runner.py).
        query = query.filter(effective_date >= datetime.combine(date_from, time.min, tzinfo=VN_TZ))
    if date_to is not None:
        # date_to là "đến hết ngày này" (inclusive) — biên trên là 00:00 giờ VN của NGÀY KẾ TIẾP.
        query = query.filter(effective_date < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=VN_TZ))
    if lifecycle_status is not None:
        query = query.filter(PainPoint.lifecycle_status == lifecycle_status)
    if is_question is not None:
        query = query.filter(Prediction.is_question == is_question)

    rows = query.order_by(effective_date.desc()).offset(offset).limit(limit).all()
    return [_post_to_summary(post, pain_point_lifecycle_status=status) for post, status in rows]


def _period_stats(db: Session, topic: Topic, date_from: date, date_to: date) -> PeriodStats:
    """Số liệu 1 giai đoạn cho GET /topics/{id}/compare-periods — CÙNG định nghĩa/nguồn dữ liệu với
    negative_by_group/sentiment_breakdown của get_dashboard() phía trên (không loại comment
    Facebook — số liệu TỔNG HỢP tính trên mọi Post đã phân tích, khác list_topic_posts vốn CHỈ hiện
    bài viết gốc để danh sách phẳng không vụn), chỉ khác là giới hạn thêm theo khoảng thời gian."""
    effective_date = func.coalesce(Post.posted_at, Post.collected_at)
    # Cùng công thức quy đổi giờ Việt Nam đã dùng ở list_topic_posts/get_pain_point_trend phía trên
    # — biên dưới 00:00 giờ VN của date_from, biên trên 00:00 giờ VN của NGÀY KẾ TIẾP date_to
    # (date_to inclusive).
    range_start = datetime.combine(date_from, time.min, tzinfo=VN_TZ)
    range_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=VN_TZ)

    post_count = (
        db.query(func.count(Post.id))
        .filter(Post.topic_id == topic.id, effective_date >= range_start, effective_date < range_end)
        .scalar()
        or 0
    )

    sentiment_rows = (
        db.query(Prediction.sentiment, func.count(Post.id))
        .join(Post, Post.id == Prediction.post_id)
        .filter(
            Post.topic_id == topic.id,
            Prediction.sentiment.isnot(None),
            effective_date >= range_start,
            effective_date < range_end,
        )
        .group_by(Prediction.sentiment)
        .all()
    )

    negative_by_group_rows = (
        db.query(Prediction.topic_label, func.count(Post.id))
        .join(Post, Post.id == Prediction.post_id)
        .filter(
            Post.topic_id == topic.id,
            Prediction.sentiment == "negative",
            Prediction.topic_label.isnot(None),
            effective_date >= range_start,
            effective_date < range_end,
        )
        .group_by(Prediction.topic_label)
        .all()
    )

    # Pain point MỚI PHÁT SINH trong giai đoạn (created_at rơi trong khoảng) — không phải tổng số
    # đang mở tính đến thời điểm đó.
    pain_point_count = (
        db.query(func.count(PainPoint.id))
        .filter(PainPoint.topic_id == topic.id, PainPoint.created_at >= range_start, PainPoint.created_at < range_end)
        .scalar()
        or 0
    )

    # Số liệu theo ngày trong giai đoạn — CÙNG cách tính trend của get_dashboard() phía trên (chỉ
    # post ĐÃ có Prediction, quy đổi giờ VN trước khi lấy ngày để không gộp nhầm review 00h-07h sáng
    # giờ VN vào ngày hôm trước). Có thêm positive_count (khác TrendPoint của get_dashboard) để
    # frontend cho chọn xem đường Tất cả/Tiêu cực/Tích cực (xem PeriodTrendPoint).
    trend_day = func.date(func.timezone(str(VN_TZ), effective_date))
    trend_rows = (
        db.query(
            trend_day.label("day"),
            func.count(Post.id).label("count"),
            func.sum(case((Prediction.sentiment == "negative", 1), else_=0)).label("negative_count"),
            func.sum(case((Prediction.sentiment == "positive", 1), else_=0)).label("positive_count"),
        )
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(Post.topic_id == topic.id, effective_date >= range_start, effective_date < range_end)
        .group_by(trend_day)
        .order_by(trend_day)
        .all()
    )
    trend = [
        PeriodTrendPoint(
            date=row.day,
            count=row.count,
            negative_count=row.negative_count or 0,
            positive_count=row.positive_count or 0,
        )
        for row in trend_rows
    ]

    return PeriodStats(
        date_from=date_from,
        date_to=date_to,
        post_count=post_count,
        sentiment_breakdown=dict(sentiment_rows),
        negative_by_group=dict(negative_by_group_rows),
        pain_point_count=pain_point_count,
        trend=trend,
    )


@router.get("/topics/{topic_id}/compare-periods", response_model=PeriodComparisonResponse)
def compare_periods(
    topic_id: UUID,
    period_a_from: date = Query(..., description="Giai đoạn A — từ ngày"),
    period_a_to: date = Query(..., description="Giai đoạn A — đến ngày (bao gồm cả ngày này)"),
    period_b_from: date = Query(..., description="Giai đoạn B — từ ngày"),
    period_b_to: date = Query(..., description="Giai đoạn B — đến ngày (bao gồm cả ngày này)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PeriodComparisonResponse:
    """So sánh phản hồi giữa 2 mốc thời gian trong CÙNG 1 chủ đề — thay cho so sánh nhiều chủ đề
    với nhau (GET /topics/compare cũ, đã gỡ bỏ): mỗi ngân hàng giờ là 1 workspace riêng biệt, so
    sánh chủ đề-với-chủ đề giữa các doanh nghiệp khác nhau không còn ý nghĩa nghiệp vụ. Quyền xem
    giống dashboard (chủ sở hữu + thành viên, xem get_accessible_topic)."""
    topic = get_accessible_topic(topic_id, current_user, db)
    return PeriodComparisonResponse(
        period_a=_period_stats(db, topic, period_a_from, period_a_to),
        period_b=_period_stats(db, topic, period_b_from, period_b_to),
    )


@router.get("/topics/{topic_id}/pain-points", response_model=list[PainPointSummary])
def list_pain_points(
    topic_id: UUID,
    lifecycle_status: str | None = Query(default=None, description="Lọc theo trạng thái xử lý"),
    assigned_user_id: UUID | None = Query(default=None, description="Lọc theo người phụ trách"),
    sla_breached: bool | None = Query(
        default=None, description="Chỉ lấy case quá hạn (true) hoặc chưa quá hạn (false)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PainPointSummary]:
    topic = get_accessible_topic(topic_id, current_user, db)
    query = db.query(PainPoint).filter(PainPoint.topic_id == topic.id)
    if lifecycle_status is not None:
        query = query.filter(PainPoint.lifecycle_status == lifecycle_status)
    if assigned_user_id is not None:
        query = query.filter(PainPoint.assigned_user_id == assigned_user_id)

    now = datetime.now(UTC)
    results = [_pain_point_to_summary(pp, now) for pp in query.order_by(*_pain_point_order_by()).all()]
    # Lọc quá hạn ở Python vì is_breached còn phụ thuộc lifecycle_status (case đã đóng không tính
    # quá hạn) — giữ đúng một định nghĩa duy nhất trong src/sla.py thay vì viết lại bằng SQL.
    if sla_breached is not None:
        results = [pp for pp in results if pp.is_breached == sla_breached]
    return results


@router.patch("/pain-points/{pain_point_id}/lifecycle", response_model=PainPointSummary)
def update_pain_point_lifecycle(
    pain_point_id: UUID,
    payload: LifecycleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PainPointSummary:
    """Đổi trạng thái xử lý / giao việc cho pain point. Mọi thay đổi đều ghi 1 dòng nhật ký
    (pain_point_events) để truy vết được ai làm gì, lúc nào."""
    pain_point = _get_accessible_pain_point(pain_point_id, current_user, db)
    topic = pain_point.topic
    changes = payload.model_dump(exclude_unset=True)
    previous_status = pain_point.lifecycle_status
    # Chụp lại trước khi setattr ghi đè — cần để so sánh xem có thực sự ĐỔI người phụ trách hay
    # không (tránh báo lại khi PATCH gửi cùng giá trị cũ).
    previous_assignee_id = pain_point.assigned_user_id

    if "assigned_user_id" in changes and changes["assigned_user_id"] is not None:
        # Không cho giao việc ra ngoài phạm vi chủ đề — người ngoài không xem được case này.
        if not is_topic_participant(topic, changes["assigned_user_id"], db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Người được giao phải là chủ sở hữu hoặc thành viên của chủ đề",
            )

    new_status = changes.get("lifecycle_status", previous_status)
    if new_status == "duplicate":
        duplicate_of_id = changes.get("duplicate_of_id", pain_point.duplicate_of_id)
        if duplicate_of_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đánh dấu trùng lặp thì phải chỉ ra trùng với pain point nào",
            )
        if duplicate_of_id == pain_point.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Pain point không thể trùng với chính nó"
            )
        target = db.query(PainPoint).filter(PainPoint.id == duplicate_of_id).first()
        if target is None or target.topic_id != pain_point.topic_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pain point gốc phải thuộc cùng chủ đề")

    # Tri-state, tách riêng khỏi vòng setattr chung bên dưới vì có nhánh rẽ. KHÔNG đọc
    # changes["due_at"] ở bất kỳ đâu khác — 1 giá trị due_at "đi lạc" trong payload (frontend gửi
    # lại mọi field mỗi lần lưu) không được phép có tác dụng nếu due_at_override không có mặt.
    if "due_at_override" in changes:
        if changes["due_at_override"]:
            new_due_at = changes.get("due_at")
            if new_due_at is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phải cung cấp hạn xử lý khi bật tuỳ chỉnh hạn",
                )
            pain_point.due_at = new_due_at
            pain_point.due_at_overridden = True
        else:
            pain_point.due_at_overridden = False
            pain_point.due_at = compute_due_at(pain_point.created_at or datetime.now(UTC), pain_point.severity_avg)

    for field in ("lifecycle_status", "assigned_user_id", "department", "duplicate_of_id", "is_priority"):
        if field in changes:
            setattr(pain_point, field, changes[field])
    if changes.get("note") is not None:
        pain_point.lifecycle_note = changes["note"]

    if pain_point.lifecycle_status == "resolved" and previous_status != "resolved":
        pain_point.resolved_at = datetime.now(UTC)
    elif pain_point.lifecycle_status != "resolved":
        pain_point.resolved_at = None

    db.add(
        PainPointEvent(
            pain_point_id=pain_point.id,
            user_id=current_user.id,
            from_status=previous_status,
            to_status=pain_point.lifecycle_status,
            note=changes.get("note"),
        )
    )
    db.commit()
    db.refresh(pain_point)

    # Thông báo — bọc try/except giống check_and_notify (xem src/analysis/pain_point.py): lỗi gửi
    # email (SMTP, mạng...) không được làm hỏng response, thao tác đổi trạng thái đã lưu thành
    # công rồi. Chỉ báo khi có THAY ĐỔI thực sự, và không tự báo cho chính actor.
    try:
        if pain_point.assigned_user_id is not None and pain_point.assigned_user_id != previous_assignee_id:
            notify_assignment(db, pain_point, current_user.id)
        if pain_point.lifecycle_status == "resolved" and previous_status != "resolved":
            notify_resolution(db, pain_point, current_user.id)
    except Exception:
        logger.exception("Lỗi khi gửi thông báo vòng đời cho pain_point=%s", pain_point.id)
        db.rollback()

    return _pain_point_to_summary(pain_point)


@router.get("/pain-points/{pain_point_id}/events", response_model=list[PainPointEventResponse])
def list_pain_point_events(
    pain_point_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PainPointEvent]:
    pain_point = _get_accessible_pain_point(pain_point_id, current_user, db)
    return (
        db.query(PainPointEvent)
        .filter(PainPointEvent.pain_point_id == pain_point.id)
        .order_by(PainPointEvent.created_at.desc())
        .all()
    )


@router.get("/pain-points/{pain_point_id}/trend", response_model=list[TrendPoint])
def get_pain_point_trend(
    pain_point_id: UUID,
    days: int = Query(default=TREND_DAYS, ge=1, le=365, description="Giới hạn N ngày gần nhất"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    """Xu hướng theo NGÀY chỉ riêng pain point này — cùng cách tính với biểu đồ xu hướng của cả
    topic trong get_dashboard (coalesce posted_at/collected_at làm trục thời gian), chỉ khác là
    lọc theo topic_label khớp title thay vì cả topic. Badge tăng/giảm/ổn định (trend field trên
    PainPoint, so 7 ngày gần nhất với 7 ngày trước — xem compute_trend trong
    src/analysis/pain_point.py) đã có sẵn từ trước; endpoint này bổ sung góc nhìn theo đường biểu
    đồ, không thay thế badge đó."""
    pain_point = _get_accessible_pain_point(pain_point_id, current_user, db)
    effective_date = func.coalesce(Post.posted_at, Post.collected_at)
    trend_start = datetime.now(UTC) - timedelta(days=days)
    # Cùng quy đổi giờ VN như trend_day ở get_dashboard phía trên — xem comment ở đó.
    trend_day = func.date(func.timezone(str(VN_TZ), effective_date))
    trend_rows = (
        db.query(
            trend_day.label("day"),
            func.count(Post.id).label("count"),
            func.sum(case((Prediction.sentiment == "negative", 1), else_=0)).label("negative_count"),
        )
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(
            Post.topic_id == pain_point.topic_id,
            Prediction.topic_label == pain_point.title,
            effective_date >= trend_start,
        )
        .group_by(trend_day)
        .order_by(trend_day)
        .all()
    )
    return [TrendPoint(date=row.day, count=row.count, negative_count=row.negative_count or 0) for row in trend_rows]


@router.get("/pain-points/{pain_point_id}/trend/hourly", response_model=list[HourlyTrendPoint])
def get_pain_point_trend_hourly(
    pain_point_id: UUID,
    date: date = Query(description="Ngày cần xem chi tiết theo giờ (giờ Việt Nam), định dạng YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HourlyTrendPoint]:
    """Zoom chi tiết theo GIỜ cho đúng 1 ngày VN của biểu đồ xu hướng RIÊNG pain point này — cùng
    cách tính với get_pain_point_trend (lọc thêm topic_label khớp title), chỉ đổi độ chi tiết ngày
    thành giờ, cùng cách với get_topic_trend_hourly ở trên."""
    pain_point = _get_accessible_pain_point(pain_point_id, current_user, db)
    effective_date = func.coalesce(Post.posted_at, Post.collected_at)
    vn_local = func.timezone(str(VN_TZ), effective_date)
    day_start = datetime.combine(date, time.min)
    day_end = day_start + timedelta(days=1)
    trend_hour = func.date_trunc("hour", vn_local)
    trend_rows = (
        db.query(
            trend_hour.label("hour"),
            func.count(Post.id).label("count"),
            func.sum(case((Prediction.sentiment == "negative", 1), else_=0)).label("negative_count"),
        )
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(
            Post.topic_id == pain_point.topic_id,
            Prediction.topic_label == pain_point.title,
            vn_local >= day_start,
            vn_local < day_end,
        )
        .group_by(trend_hour)
        .order_by(trend_hour)
        .all()
    )
    return [HourlyTrendPoint(hour=row.hour, count=row.count, negative_count=row.negative_count or 0) for row in trend_rows]


@router.get("/pain-points/{pain_point_id}/posts", response_model=list[PostSummary])
def list_pain_point_posts(
    pain_point_id: UUID,
    source_type: str | None = Query(default=None, description="Lọc theo nguồn (vd 'facebook') — xem PainPointSummary.sources"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PostSummary]:
    """Drill-down: TOÀN BỘ post khớp (topic_id, topic_label, sentiment=negative) của pain point này
    — không chỉ 3 sample lưu trong pain_point_posts (những cái đó chỉ dùng làm ví dụ tiêu biểu).
    sentiment=negative bắt buộc vì Pain Point Agent CHỈ gom review tiêu cực vào pain point (xem
    src/analysis/pain_point.py) — phản hồi tích cực/trung lập cùng topic_label không thực sự thuộc
    case này, dù trùng nhóm chủ đề; xem được ở danh sách phản hồi đã phân tích chung (list_topic_posts).

    source_type cho phép xem riêng phản hồi của TỪNG nguồn đóng góp (xem PainPointSummary.sources —
    danh sách nguồn duy nhất trong nhóm) ngay tại trang pain point, không cần sang trang riêng của
    từng nguồn (Luồng Facebook/TikTok)."""
    pain_point = _get_accessible_pain_point(pain_point_id, current_user, db)
    query = (
        db.query(Post)
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(
            Post.topic_id == pain_point.topic_id,
            Prediction.topic_label == pain_point.title,
            Prediction.sentiment == "negative",
        )
    )
    if source_type is not None:
        query = query.join(Source, Post.source_id == Source.id).filter(Source.type == source_type)
    posts = query.order_by(Post.collected_at.desc()).offset(offset).limit(limit).all()
    return [_post_to_summary(post, pain_point_lifecycle_status=pain_point.lifecycle_status) for post in posts]


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post_detail(
    post_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PostDetail:
    # Trước đây chỉ kiểm tra Topic.user_id — thành viên chủ đề (được mời, không phải chủ sở hữu)
    # không xem được chi tiết post dù xem được cả dashboard lẫn drill-down danh sách. Sửa cho nhất
    # quán với get_accessible_topic dùng ở mọi endpoint đọc khác trong file này.
    post = (
        db.query(Post)
        .join(Topic, Topic.id == Post.topic_id)
        .outerjoin(TopicMember, TopicMember.topic_id == Topic.id)
        .filter(Post.id == post_id, (Topic.user_id == current_user.id) | (TopicMember.user_id == current_user.id))
        .first()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy post")
    return _post_to_detail(post, pain_point_lifecycle_status=_pain_point_lifecycle_status_for_post(db, post))


@router.get("/posts/{post_id}/comments", response_model=list[PostSummary])
def list_post_comments(
    post_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PostSummary]:
    """Comment (con) của 1 bài viết Facebook cụ thể — xem Post.parent_post_id trong
    src/db/models.py. Luôn rỗng với post của mọi nguồn khác Facebook (không có khái niệm bài viết
    cha/con)."""
    parent = (
        db.query(Post)
        .join(Topic, Topic.id == Post.topic_id)
        .outerjoin(TopicMember, TopicMember.topic_id == Topic.id)
        .filter(Post.id == post_id, (Topic.user_id == current_user.id) | (TopicMember.user_id == current_user.id))
        .first()
    )
    if parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy post")

    comments = (
        db.query(Post)
        .filter(Post.parent_post_id == parent.id)
        .order_by(Post.posted_at.desc().nullslast(), Post.collected_at.desc())
        .all()
    )
    return [_post_to_summary(comment) for comment in comments]
