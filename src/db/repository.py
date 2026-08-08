"""
Repository layer - CRUD that tren SQLite, thay the danh sach in-memory cua
src/services/mock_data.py. Day la nguon du lieu duy nhat cho API: Topics duoc
seed voi app_id/id That da xac minh (Google Play + App Store), con PainPoint/
Notification chi duoc tao ra tu ket qua thuc su cua pipeline (POST run-pipeline),
khong con du lieu mo phong dung san.
"""
import hashlib
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.models import NotificationORM, PainPointORM, PostORM, TopicORM
from src.db.session import get_session, init_db
from src.models.schemas import (
    CaseStatus, Notification, PainPoint, PainPointUpdate, Post, ReportSummary, Topic, TopicReportRow,
)

DEMO_OWNER_ID = "00000000-0000-0000-0000-000000000001"

# App id / numeric id THAT da duoc xac minh qua Google Play search / iTunes lookup API
# (xem lich su hoi thoai - khong dung app_id gia nhu ban dau cua du an).
SEED_TOPICS = [
    {
        "name": "Techcombank",
        "keywords": ["techcombank", "tcb"],
        "sources": ["google_play", "app_store"],
        "source_configs": {
            "google_play": {"app_id": "vn.com.techcombank.bb.app"},
            "app_store": {"app_id": "1548623362", "country": "vn"},
        },
        "alert_threshold": 10,
        "notifications_enabled": True,
    },
    {
        "name": "Vietcombank",
        "keywords": ["vietcombank", "vcb"],
        "sources": ["google_play", "app_store"],
        "source_configs": {
            "google_play": {"app_id": "com.VCB"},
            "app_store": {"app_id": "561433133", "country": "vn"},
        },
        "alert_threshold": 15,
        "notifications_enabled": True,
    },
    {
        "name": "MB Bank",
        "keywords": ["mb bank", "mbbank"],
        "sources": ["google_play", "app_store"],
        "source_configs": {
            "google_play": {"app_id": "com.mbmobile"},
            "app_store": {"app_id": "1205807363", "country": "vn"},
        },
        "alert_threshold": 8,
        "notifications_enabled": False,
    },
    {
        "name": "SHB",
        "keywords": ["shb", "saha", "sai gon ha noi"],
        "sources": ["google_play", "app_store"],
        "source_configs": {
            # SHB SAHA - ung dung ngan hang ban le chinh thuc cua SHB
            "google_play": {"app_id": "vn.shb.saha.mbanking"},
            "app_store": {"app_id": "1661457183", "country": "vn"},
        },
        "alert_threshold": 10,
        "notifications_enabled": True,
    },
    {
        "name": "TPBank",
        "keywords": ["tpbank", "tp bank"],
        "sources": ["google_play", "app_store"],
        "source_configs": {
            # TPBank Mobile - ung dung ngan hang ban le chinh thuc cua TPBank
            "google_play": {"app_id": "com.tpb.mb.gprsandroid"},
            "app_store": {"app_id": "450464147", "country": "vn"},
        },
        "alert_threshold": 10,
        "notifications_enabled": True,
    },
]


def _topic_from_orm(row: TopicORM) -> Topic:
    return Topic(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        keywords=row.keywords,
        sources=row.sources,
        source_configs=row.source_configs,
        alert_threshold=row.alert_threshold,
        notifications_enabled=row.notifications_enabled,
        created_at=row.created_at,
    )


def _pain_point_from_orm(row: PainPointORM) -> PainPoint:
    return PainPoint(
        id=row.id,
        topic_id=row.topic_id,
        title=row.title,
        topic_label=row.topic_label,
        description=row.description,
        post_count=row.post_count,
        trend=row.trend,
        severity=row.severity,
        verification_status=row.verification_status,
        confidence_score=row.confidence_score,
        sources=row.sources,
        sample_posts=row.sample_posts,
        created_at=row.created_at,
        status=row.status or CaseStatus.OPEN.value,
        assignee=row.assignee,
        resolution_notes=row.resolution_notes,
        resolved_at=row.resolved_at,
    )


def _notification_from_orm(row: NotificationORM) -> Notification:
    return Notification(
        id=row.id,
        topic_id=row.topic_id,
        pain_point_id=row.pain_point_id,
        channel=row.channel,
        title=row.title,
        message=row.message,
        sent_at=row.sent_at,
        read=row.read,
    )


def init_and_seed() -> None:
    """Tao bang (neu chua co) va seed cac Topic that con thieu (theo ten).
    Chay lai an toan: Topic da ton tai (vd da chinh sua) se khong bi ghi de,
    chi cac Topic moi duoc them trong SEED_TOPICS (vd SHB, TPBank) se duoc bo sung."""
    init_db()
    with get_session() as session:
        existing_names = set(session.scalars(select(TopicORM.name)).all())
        for seed in SEED_TOPICS:
            if seed["name"] in existing_names:
                continue
            session.add(
                TopicORM(
                    id=str(uuid4()),
                    owner_id=DEMO_OWNER_ID,
                    **seed,
                )
            )
        session.commit()


def list_topics() -> list[Topic]:
    with get_session() as session:
        rows = session.scalars(select(TopicORM)).all()
        return [_topic_from_orm(r) for r in rows]


def get_topic(topic_id: str) -> Topic | None:
    with get_session() as session:
        row = session.get(TopicORM, str(topic_id))
        return _topic_from_orm(row) if row else None


def create_topic(topic: Topic) -> Topic:
    with get_session() as session:
        session.add(
            TopicORM(
                id=str(topic.id),
                owner_id=str(topic.owner_id),
                name=topic.name,
                keywords=topic.keywords,
                sources=topic.sources,
                source_configs=topic.source_configs,
                alert_threshold=topic.alert_threshold,
                notifications_enabled=topic.notifications_enabled,
                created_at=topic.created_at,
            )
        )
        session.commit()
    return topic


def _post_content_hash(post: Post) -> str:
    raw = f"{post.topic_id}|{post.source}|{post.content.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_posts(posts: list[Post]) -> int:
    """Luu cac phan hoi crawl that; bo qua ban ghi trung (cung topic/source/noi dung)."""
    saved = 0
    with get_session() as session:
        for post in posts:
            session.add(
                PostORM(
                    id=str(post.id),
                    topic_id=str(post.topic_id),
                    source=post.source,
                    author=post.author,
                    content=post.content,
                    content_hash=_post_content_hash(post),
                    published_at=post.published_at,
                    collected_at=post.collected_at,
                    is_duplicate=post.is_duplicate,
                    is_spam=post.is_spam,
                )
            )
            try:
                session.commit()
                saved += 1
            except IntegrityError:
                session.rollback()
    return saved


def filter_new_posts(posts: list[Post]) -> list[Post]:
    """Loai cac phan hoi da tung duoc luu (cung topic/source/noi dung) o chu ky
    crawl truoc do - crawler khong co con tro "since" nen moi chu ky deu tra ve
    lai phan lon review cu, neu khong loc thi Pain Point se bi dem trung moi
    lan pipeline chay (xem add_pain_points ben duoi cong don post_count)."""
    if not posts:
        return posts
    init_db()
    hashes = {post.id: _post_content_hash(post) for post in posts}
    with get_session() as session:
        existing = set(
            session.scalars(
                select(PostORM.content_hash).where(PostORM.content_hash.in_(hashes.values()))
            ).all()
        )
    return [post for post in posts if hashes[post.id] not in existing]


def count_posts(topic_id: str) -> int:
    with get_session() as session:
        rows = session.scalars(select(PostORM).where(PostORM.topic_id == str(topic_id))).all()
        return len(rows)


def _post_from_orm(row: PostORM) -> Post:
    return Post(
        id=row.id,
        topic_id=row.topic_id,
        source=row.source,
        author=row.author,
        content=row.content,
        published_at=row.published_at,
        collected_at=row.collected_at,
        is_duplicate=row.is_duplicate,
        is_spam=row.is_spam,
        sentiment=row.sentiment,
        topic_label=row.topic_label,
        severity_score=row.severity_score,
    )


def save_post_classifications(predictions: list) -> None:
    """Ghi ket qua Classification Agent (sentiment/topic_label/severity_score)
    thang vao tung Post - chi thuc hien 1 lan/phan hoi (predictions chi duoc
    tinh cho clean_posts, tuc la phan hoi MOI, xem processing_node), dung lam
    nguon that cho bieu do xu huong thay vi phai goi lai LLM."""
    if not predictions:
        return
    with get_session() as session:
        by_id = {str(p.post_id): p for p in predictions}
        rows = session.scalars(select(PostORM).where(PostORM.id.in_(by_id.keys()))).all()
        for row in rows:
            pred = by_id[row.id]
            row.sentiment = pred.sentiment.value if hasattr(pred.sentiment, "value") else pred.sentiment
            row.topic_label = pred.topic_label
            row.severity_score = pred.severity_score
        session.commit()


def get_topic_trend(topic_id: str, days: int = 30):
    """Xu huong phan hoi tieu cuc theo NGAY THAT (published_at) trong `days`
    ngay gan nhat - nguon that duy nhat cho bieu do so sanh cac chu ky/thang,
    thay cho sparkline gia truoc day chi dung tren client (xem PRD phan Respond).
    Cac phan hoi chua duoc phan loai (sentiment IS NULL - vd du lieu cu truoc khi
    co cot nay) duoc coi la khong xac dinh va khong tinh vao negative_count.

    Zero-fill DU MOI NGAY trong khoang (ke ca ngay khong co phan hoi nao) - neu
    khong, cac ngay =0 se bi bo qua hoan toan khoi ket qua, khien truc thoi gian
    o bieu do "Ngay" bi nhay coc (khoang cach giua 2 diem tren bieu do khong con
    dung ty le voi so ngay that giua chung), va khi gop len Tuan/Thang cung se
    thieu nhung tuan/thang khong co phan hoi nao thay vi hien thi dung la 0."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days)
    with get_session() as session:
        rows = session.scalars(
            select(PostORM).where(
                PostORM.topic_id == str(topic_id), PostORM.published_at >= since
            )
        ).all()

    buckets: dict[str, dict] = {}
    for row in rows:
        day = row.published_at.strftime("%Y-%m-%d")
        bucket = buckets.setdefault(day, {"total_posts": 0, "negative_count": 0, "by_label": {}})
        bucket["total_posts"] += 1
        if row.sentiment == "negative":
            bucket["negative_count"] += 1
            label = row.topic_label or "khac"
            bucket["by_label"][label] = bucket["by_label"].get(label, 0) + 1

    today = datetime.utcnow().date()
    start_day = since.date()
    cursor = start_day
    while cursor <= today:
        key = cursor.strftime("%Y-%m-%d")
        buckets.setdefault(key, {"total_posts": 0, "negative_count": 0, "by_label": {}})
        cursor += timedelta(days=1)

    points = [
        {"date": day, **data}
        for day, data in sorted(buckets.items())
    ]
    return points


def list_posts(topic_id: str, source: str | None = None, limit: int = 200) -> list[Post]:
    """Danh sach phan hoi (review) that da crawl duoc cho 1 Topic - de nguoi dung
    xem lai noi dung goc, kiem tra vi sao pipeline phan loai/gom nhom nhu vay."""
    with get_session() as session:
        stmt = select(PostORM).where(PostORM.topic_id == str(topic_id))
        if source:
            stmt = stmt.where(PostORM.source == source)
        stmt = stmt.order_by(PostORM.published_at.desc()).limit(limit)
        rows = session.scalars(stmt).all()
        return [_post_from_orm(r) for r in rows]


_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_MAX_SAMPLE_POSTS = 25
_MAX_SOURCES = 10


def _merge_unique(existing: list[str], new: list[str], cap: int) -> list[str]:
    merged = list(existing)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged[:cap]


def add_pain_points(pain_points: list[PainPoint]) -> None:
    """Ghi nhan Pain Point tu 1 chu ky pipeline. Neu chu de da co Pain Point cung
    nhom van de (cung topic_id + title) tu chu ky truoc, GOM lai (cong don so
    phan hoi, hop nhat phan hoi tieu bieu/nguon doi chieu, lay muc do nghiem
    trong cao nhat) thay vi tao ban ghi moi rieng le moi chu ky - neu khong,
    cung mot van de se bi vun vat thanh nhieu Pain Point nho qua thoi gian,
    khien muc do tieu cuc thuc te bi che khuat tren dashboard."""
    with get_session() as session:
        for pp in pain_points:
            severity_value = pp.severity.value if hasattr(pp.severity, "value") else pp.severity
            verification_value = (
                pp.verification_status.value if hasattr(pp.verification_status, "value")
                else pp.verification_status
            )
            existing = session.scalar(
                select(PainPointORM)
                .where(PainPointORM.topic_id == str(pp.topic_id), PainPointORM.title == pp.title)
                .order_by(PainPointORM.created_at.desc())
            )
            if existing is not None:
                new_total = existing.post_count + pp.post_count
                existing.confidence_score = round(
                    (existing.confidence_score * existing.post_count + pp.confidence_score * pp.post_count)
                    / max(new_total, 1),
                    2,
                )
                if _SEVERITY_RANK.get(severity_value, 0) > _SEVERITY_RANK.get(existing.severity, 0):
                    existing.severity = severity_value
                existing.trend = "up" if pp.post_count > 0 else existing.trend
                existing.description = pp.description
                existing.verification_status = verification_value
                existing.sources = _merge_unique(existing.sources, pp.sources, _MAX_SOURCES)
                existing.sample_posts = _merge_unique(existing.sample_posts, pp.sample_posts, _MAX_SAMPLE_POSTS)
                existing.post_count = new_total
                if not existing.topic_label:
                    existing.topic_label = pp.topic_label
                # Van de da duoc danh dau "da xu ly" nhung chu ky nay lai phat
                # hien them phan hoi tieu cuc cung nhom -> van de tai dien,
                # tu dong mo lai thay vi im lang cong don vao 1 case da dong.
                if existing.status == CaseStatus.RESOLVED.value and pp.post_count > 0:
                    existing.status = CaseStatus.OPEN.value
                    existing.resolved_at = None
                continue

            session.add(
                PainPointORM(
                    id=str(pp.id),
                    topic_id=str(pp.topic_id),
                    title=pp.title,
                    topic_label=pp.topic_label,
                    description=pp.description,
                    post_count=pp.post_count,
                    trend=pp.trend,
                    severity=severity_value,
                    verification_status=verification_value,
                    confidence_score=pp.confidence_score,
                    sources=pp.sources,
                    sample_posts=pp.sample_posts,
                    created_at=pp.created_at,
                )
            )
        session.commit()


def list_pain_points(topic_id: str) -> list[PainPoint]:
    with get_session() as session:
        rows = session.scalars(
            select(PainPointORM).where(PainPointORM.topic_id == str(topic_id)).order_by(PainPointORM.created_at.desc())
        ).all()
        return [_pain_point_from_orm(r) for r in rows]


def get_pain_point(pain_point_id: str) -> PainPoint | None:
    with get_session() as session:
        row = session.get(PainPointORM, str(pain_point_id))
        return _pain_point_from_orm(row) if row else None


def list_all_pain_points() -> list[PainPoint]:
    """Toan bo Pain Point tren tat ca chu de - dung cho Report tong quan
    cross-brand (xem GET /api/v1/report/summary)."""
    with get_session() as session:
        rows = session.scalars(select(PainPointORM)).all()
        return [_pain_point_from_orm(r) for r in rows]


def update_pain_point(pain_point_id: str, update: PainPointUpdate) -> PainPoint | None:
    """Cap nhat trang thai xu ly (Respond) cho mot Pain Point."""
    with get_session() as session:
        row = session.get(PainPointORM, str(pain_point_id))
        if row is None:
            return None

        if update.status is not None:
            status_value = update.status.value if hasattr(update.status, "value") else update.status
            if status_value == CaseStatus.RESOLVED.value and row.status != CaseStatus.RESOLVED.value:
                row.resolved_at = datetime.utcnow()
            elif status_value != CaseStatus.RESOLVED.value:
                row.resolved_at = None
            row.status = status_value
        if update.assignee is not None:
            row.assignee = update.assignee
        if update.resolution_notes is not None:
            row.resolution_notes = update.resolution_notes

        session.commit()
        session.refresh(row)
        return _pain_point_from_orm(row)


def add_notifications(notifications: list[Notification]) -> None:
    with get_session() as session:
        for n in notifications:
            session.add(
                NotificationORM(
                    id=str(n.id),
                    topic_id=str(n.topic_id),
                    pain_point_id=str(n.pain_point_id),
                    channel=n.channel,
                    title=n.title,
                    message=n.message,
                    sent_at=n.sent_at,
                    read=n.read,
                )
            )
        session.commit()


def list_notifications() -> list[Notification]:
    with get_session() as session:
        rows = session.scalars(select(NotificationORM).order_by(NotificationORM.sent_at.desc())).all()
        return [_notification_from_orm(r) for r in rows]


def get_report_summary(sla_hours: int) -> ReportSummary:
    """Tong hop KPI cross-topic cho man hinh Report/Command Center: so case
    theo trang thai, thoi gian xu ly trung binh, ty le dung SLA, va bang
    so sanh theo tung chu de (ngan hang) - xem GET /api/v1/report/summary."""
    now = datetime.utcnow()
    topics = list_topics()
    pain_points = list_all_pain_points()

    by_topic_rows: list[TopicReportRow] = []
    open_count = in_progress_count = resolved_count = total_negative = 0

    for topic in topics:
        topic_pps = [pp for pp in pain_points if pp.topic_id == topic.id]
        t_open = sum(1 for pp in topic_pps if pp.status == CaseStatus.OPEN)
        t_in_progress = sum(1 for pp in topic_pps if pp.status == CaseStatus.IN_PROGRESS)
        t_resolved = sum(1 for pp in topic_pps if pp.status == CaseStatus.RESOLVED)
        t_total_negative = sum(pp.post_count for pp in topic_pps)
        t_high_open = sum(
            1 for pp in topic_pps
            if pp.status != CaseStatus.RESOLVED and pp.severity.value in ("high", "critical")
        )
        t_avg_conf = round(sum(pp.confidence_score for pp in topic_pps) / len(topic_pps), 2) if topic_pps else 0.0

        by_topic_rows.append(TopicReportRow(
            topic_id=topic.id,
            topic_name=topic.name,
            total_negative=t_total_negative,
            open_count=t_open,
            in_progress_count=t_in_progress,
            resolved_count=t_resolved,
            high_severity_open=t_high_open,
            avg_confidence=t_avg_conf,
        ))

        open_count += t_open
        in_progress_count += t_in_progress
        resolved_count += t_resolved
        total_negative += t_total_negative

    resolution_hours: list[float] = []
    resolved_within_sla = 0
    overdue_open = 0
    for pp in pain_points:
        if pp.status == CaseStatus.RESOLVED and pp.resolved_at:
            hours = (pp.resolved_at - pp.created_at).total_seconds() / 3600
            resolution_hours.append(hours)
            if hours <= sla_hours:
                resolved_within_sla += 1
        elif pp.status in (CaseStatus.OPEN, CaseStatus.IN_PROGRESS):
            age_hours = (now - pp.created_at).total_seconds() / 3600
            if age_hours > sla_hours:
                overdue_open += 1

    avg_resolution_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
    resolved_within_sla_pct = (
        round(resolved_within_sla / len(resolution_hours) * 100, 1) if resolution_hours else None
    )

    return ReportSummary(
        total_negative=total_negative,
        open_count=open_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        overdue_open_count=overdue_open,
        avg_resolution_hours=avg_resolution_hours,
        resolved_within_sla_pct=resolved_within_sla_pct,
        by_topic=by_topic_rows,
    )
