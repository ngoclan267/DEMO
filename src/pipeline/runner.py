import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import OfficialDocument, Post, Prediction, Source, Topic, User
from src.db.session import SessionLocal
from src.logging_config import VN_TZ, configure_logging
from src.pipeline.collectors import REFERENCE_SOURCE_TYPES, get_collector
from src.pipeline.processing.content_dedup import find_duplicate_content_ids
from src.pipeline.processing.cross_topic_dedup import resolve_follower_sources, source_identity
from src.pipeline.processing.dedup import UpsertResult, upsert_posts
from src.pipeline.processing.pipeline import ProcessResult, process_raw_posts
from src.pipeline.processing.reference_docs import process_raw_documents, upsert_official_documents

logger = logging.getLogger(__name__)

# Lần đầu thu thập một source (chưa có post nào trong DB): backfill sâu để lấy dữ liệu lịch sử
# dồi dào phục vụ các phase sau. Các chu kỳ sau đó (đã có known_ids): giới hạn thấp hơn nhiều vì
# collector tự dừng sớm ngay khi bắt kịp dữ liệu cũ (xem known_ids trong từng collector) — limit
# ở đây chỉ là trần an toàn, hiếm khi bị chạm tới trừ khi có rất nhiều review mới cùng lúc.
BACKFILL_LIMIT_PER_SOURCE = 2000
INCREMENTAL_LIMIT_PER_SOURCE = 300

# Nguồn tham chiếu (bank_website): số trang trên 1 site ít hơn nhiều so với review, và crawl không
# nên "đào bới" quá sâu 1 site công khai mỗi chu kỳ.
REFERENCE_BACKFILL_LIMIT_PER_SOURCE = 200
REFERENCE_INCREMENTAL_LIMIT_PER_SOURCE = 50


@dataclass
class SourceCycleResult:
    topic_name: str
    source_type: str
    fetched: int
    inserted: int
    skipped_duplicate: int
    spam: int
    # Bài viết Facebook có NỘI DUNG trùng 1 bài khác (không phải trùng external_id như
    # skipped_duplicate ở trên) — xem src/pipeline/processing/content_dedup.py. Vẫn được insert vào
    # DB (giữ số liệu), chỉ bị is_duplicate=True nên không tốn quota LLM phân tích lại.
    duplicate_content: int = 0
    error: str | None = None
    # True nếu nguồn này chưa tới lịch crawl riêng (Source.crawl_interval_minutes) trong chu kỳ này
    # — không phải lỗi, chỉ là chưa tới hạn (xem _is_source_due).
    skipped: bool = False
    # True nếu bị bỏ qua HẲN vì tài khoản dùng thử đã dùng hết trần thu thập MIỄN PHÍ TRONG NGÀY
    # (xem _trial_daily_crawl_remaining, trial_daily_crawl_limit trong config.py) — KHÁC skipped ở
    # trên (đó là chưa tới lịch riêng của nguồn, không liên quan gói dùng thử).
    crawl_capped: bool = False


@dataclass
class CycleResult:
    started_at: float
    elapsed_seconds: float = 0.0
    sources: list[SourceCycleResult] = field(default_factory=list)

    @property
    def total_fetched(self) -> int:
        return sum(s.fetched for s in self.sources)

    @property
    def total_inserted(self) -> int:
        return sum(s.inserted for s in self.sources)

    @property
    def total_crawl_capped(self) -> int:
        return sum(1 for s in self.sources if s.crawl_capped)


def run_cycle(session: Session | None = None) -> CycleResult:
    """Chạy một chu kỳ Collector Agent + Processing Agent cho mọi Topic/Source đang active."""
    owns_session = session is None
    session = session or SessionLocal()

    start = time.monotonic()
    result = CycleResult(started_at=start)

    try:
        now = datetime.now(UTC)
        topics = session.query(Topic).filter(Topic.status == "active").all()
        topic_sources = [(topic, source) for topic in topics for source in topic.sources if source.is_active]

        # Topic MỚI TẠO chỉ có config {"query": "tên ngân hàng"} (chưa có package_name/app_id thật)
        # — tự resolve định danh TRƯỚC khi tính nhóm trùng, để nếu app này đã được 1 topic khác crawl
        # rồi thì ngay CHU KỲ ĐẦU TIÊN đã nhận diện được là follower và đồng bộ toàn bộ dữ liệu có
        # sẵn, thay vì phải tự backfill từ đầu rồi đợi chu kỳ sau mới phát hiện ra trùng (xem
        # _maybe_resolve_identity). Chỉ resolve cho source đã tới lịch crawl trong chu kỳ này.
        for _topic, source in topic_sources:
            if source.type in ("google_play", "app_store") and _is_source_due(source, now):
                _maybe_resolve_identity(session, source)

        # source_id -> canonical source_id, cho các source trùng định danh app thật (package_name/
        # app_id) ở topic KHÁC — xem src/pipeline/processing/cross_topic_dedup.py. Tính 1 lần cho cả
        # chu kỳ (không phải mỗi source) vì cần nhìn toàn cục mọi source mới xác định được ai là
        # canonical (source tạo sớm nhất trong nhóm trùng).
        follower_map = resolve_follower_sources(session)
        for topic, source in topic_sources:
            result.sources.append(_run_source(session, topic, source, follower_map.get(source.id)))
    finally:
        if owns_session:
            session.close()

    result.elapsed_seconds = time.monotonic() - start
    logger.info(
        "Chu kỳ hoàn tất trong %.1fs — tổng fetched=%d, inserted=%d, số nguồn=%d%s",
        result.elapsed_seconds,
        result.total_fetched,
        result.total_inserted,
        len(result.sources),
        f" — {result.total_crawl_capped} nguồn bị dừng vì tài khoản dùng thử hết trần thu thập hôm nay"
        if result.total_crawl_capped
        else "",
    )
    return result


def _get_known_external_ids(session: Session, source_id) -> set[str]:
    rows = session.query(Post.external_id).filter(Post.source_id == source_id).all()
    return {row[0] for row in rows if row[0]}


def _get_known_document_urls(session: Session, source_id) -> set[str]:
    rows = session.query(OfficialDocument.url).filter(OfficialDocument.source_id == source_id).all()
    return {row[0] for row in rows if row[0]}


def _maybe_resolve_identity(session: Session, source: Source) -> None:
    """Nếu source chưa có định danh app thật (package_name/app_id) — vd mới tạo, config chỉ có
    {"query": "tên ngân hàng"} — tự resolve qua chính collector (chỉ search, KHÔNG fetch review) và
    lưu lại vào Source.config. Không làm gì nếu đã có định danh hoặc collector không hỗ trợ
    resolve_identity (loại nguồn khác ngoài google_play/app_store)."""
    if source_identity(source.type, source.config) is not None:
        return
    collector = get_collector(source.type, source.config)
    resolver = getattr(collector, "resolve_identity", None)
    if resolver is None:
        return
    try:
        resolved = resolver()
    except Exception:
        logger.exception("Lỗi khi tự resolve định danh app cho source=%s (type=%s)", source.id, source.type)
        return
    if resolved:
        source.config = {**source.config, **resolved}
        session.commit()


def _is_source_due(source: Source, now: datetime) -> bool:
    """True nếu nguồn này đã tới lịch crawl riêng. crawl_interval_minutes=None (mọi nguồn hiện có,
    trước khi có tính năng này) nghĩa là dùng nhịp scheduler mặc định — LUÔN đến hạn, giữ nguyên
    hành vi cũ. Có giá trị thì chỉ crawl lại khi đã đủ lâu kể từ last_crawled_at — cần cho các nguồn
    ít thay đổi (vd website ngân hàng) để không gọi lại mỗi tick scheduler."""
    if source.crawl_interval_minutes is None:
        return True
    if source.last_crawled_at is None:
        return True
    return now - source.last_crawled_at >= timedelta(minutes=source.crawl_interval_minutes)


def _trial_daily_crawl_remaining(session: Session, user_id) -> int | None:
    """None nếu KHÔNG phải tài khoản dùng thử có giới hạn (is_paid=True hoặc trial_ends_at=None —
    đúng điều kiện đã dùng cho trần phân tích AI, xem _trial_users_blocked_from_analysis trong
    src/analysis/runner.py) — nghĩa là KHÔNG giới hạn thu thập. Có giá trị thì trả về số bản ghi còn
    được thu thập THÊM hôm nay (>= 0, không âm dù đã vượt trần) — gộp cả Post lẫn OfficialDocument
    của MỌI topic mà user này sở hữu (1 tài khoản = 1 ngân sách, không tách theo từng nguồn/topic).

    CHỈ áp trần NGÀY (không kiểm tra hết hạn thời gian/trần trọn đời như phân tích) — thu thập dữ
    liệu MỚI vẫn tiếp tục kể cả sau khi hết hạn dùng thử hẳn (yêu cầu nghiệp vụ: chỉ "ngừng phân
    tích", không ngừng thu thập), chỉ phân tích mới bị tạm dừng vĩnh viễn tới khi nâng cấp."""
    user = session.query(User).filter(User.id == user_id).first()
    if user is None or user.is_paid or user.trial_ends_at is None:
        return None
    # Giờ VN (không phải UTC) — mốc 0:00 UTC rơi vào 7h sáng giờ VN, "làm mới" trần giữa buổi sáng
    # thay vì nửa đêm theo giờ người dùng thực tế đang ở Việt Nam đang dùng. Đồng bộ với
    # _trial_users_blocked_from_analysis (src/analysis/runner.py) và _build_user_response
    # (src/api/routes_auth.py) — cả 3 nơi PHẢI cùng 1 mốc reset, lệch nhau sẽ đếm sai lượt còn lại.
    today_start = datetime.now(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    posts_today = (
        session.query(func.count(Post.id))
        .join(Topic, Topic.id == Post.topic_id)
        .filter(Topic.user_id == user_id, Post.collected_at >= today_start)
        .scalar()
        or 0
    )
    docs_today = (
        session.query(func.count(OfficialDocument.id))
        .join(Topic, Topic.id == OfficialDocument.topic_id)
        .filter(Topic.user_id == user_id, OfficialDocument.first_seen_at >= today_start)
        .scalar()
        or 0
    )
    return max(0, get_settings().trial_daily_crawl_limit - posts_today - docs_today)


def _run_source(
    session: Session, topic: Topic, source: Source, canonical_source_id=None
) -> SourceCycleResult:
    now = datetime.now(UTC)
    if not _is_source_due(source, now):
        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=0,
            inserted=0,
            skipped_duplicate=0,
            spam=0,
            skipped=True,
        )

    # canonical_source_id != None (follower — sao chép dữ liệu ĐÃ CÓ SẴN từ 1 source khác trong hệ
    # thống, xem _sync_post_source_from_canonical) KHÔNG gọi API bên ngoài nên KHÔNG tính vào ngân
    # sách thu thập — chỉ áp trần cho lượt gọi collector thật (post/reference source bên dưới).
    crawl_remaining = None
    if canonical_source_id is None:
        crawl_remaining = _trial_daily_crawl_remaining(session, topic.user_id)
        if crawl_remaining == 0:
            return SourceCycleResult(
                topic_name=topic.name,
                source_type=source.type,
                fetched=0,
                inserted=0,
                skipped_duplicate=0,
                spam=0,
                crawl_capped=True,
            )

    if source.type in REFERENCE_SOURCE_TYPES:
        result = _run_reference_source(session, topic, source, max_limit=crawl_remaining)
    elif canonical_source_id is not None:
        result = _sync_post_source_from_canonical(session, topic, source, canonical_source_id)
    else:
        result = _run_post_source(session, topic, source, max_limit=crawl_remaining)

    if result.error is None:
        source.last_crawled_at = now
        session.commit()
    return result


def _run_reference_source(session: Session, topic: Topic, source: Source, max_limit: int | None = None) -> SourceCycleResult:
    """Nhánh dành cho nguồn ĐỐI CHIẾU (bank_website) — dữ liệu thu được là tài liệu chính thức của
    ngân hàng, không phải phản hồi khách hàng, nên đi vào official_documents thay vì posts.

    `max_limit`: ngân sách thu thập MIỄN PHÍ còn lại trong ngày của tài khoản dùng thử (xem
    _trial_daily_crawl_remaining) — None nghĩa là không giới hạn (tài khoản trả phí)."""
    try:
        known_urls = _get_known_document_urls(session, source.id)
        limit = REFERENCE_INCREMENTAL_LIMIT_PER_SOURCE if known_urls else REFERENCE_BACKFILL_LIMIT_PER_SOURCE
        if max_limit is not None:
            limit = min(limit, max_limit)

        collector = get_collector(source.type, source.config)
        raw_docs = collector.collect(limit=limit, known_ids=known_urls)
        rows = process_raw_documents(raw_docs, topic_id=topic.id, source_id=source.id)
        upsert_result = upsert_official_documents(session, rows)

        logger.info(
            "[%s/%s] fetched=%d inserted/updated=%d không đổi=%d",
            topic.name,
            source.type,
            len(raw_docs),
            upsert_result.inserted,
            upsert_result.skipped_unchanged,
        )

        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=len(raw_docs),
            inserted=upsert_result.inserted,
            skipped_duplicate=upsert_result.skipped_unchanged,
            spam=0,
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Lỗi khi thu thập tài liệu đối chiếu topic=%s source=%s", topic.name, source.type)
        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=0,
            inserted=0,
            skipped_duplicate=0,
            spam=0,
            error=str(exc),
        )


def _upsert_posts_with_parent_links(session: Session, source_id, processed: ProcessResult) -> UpsertResult:
    """Upsert bình thường (1 lượt) nếu batch không có comment nào cần gắn bài viết cha — đúng hành
    vi cũ, áp dụng cho mọi nguồn khác Facebook. Có comment (processed.parent_external_id_by_external_id
    không rỗng, xem src/pipeline/collectors/facebook.py) thì upsert 2 đợt: bài viết TRƯỚC (để có UUID
    nội bộ), rồi resolve UUID đó cho từng comment qua 1 truy vấn DB riêng — KHÔNG dùng RETURNING của
    lượt upsert bài viết, vì DO UPDATE ... WHERE (xem upsert_posts) chỉ trả về dòng THỰC SỰ có ghi đè,
    nên đa số bài viết đã biết từ chu kỳ trước sẽ không xuất hiện trong RETURNING dù vẫn cần lấy được
    id của chúng để gắn comment mới."""
    if not processed.parent_external_id_by_external_id:
        return upsert_posts(session, processed.rows)

    child_external_ids = set(processed.parent_external_id_by_external_id.keys())
    parent_rows = [r for r in processed.rows if r["external_id"] not in child_external_ids]
    child_rows = [r for r in processed.rows if r["external_id"] in child_external_ids]

    parent_result = upsert_posts(session, parent_rows)

    needed_parent_external_ids = set(processed.parent_external_id_by_external_id.values())
    id_map = dict(
        session.query(Post.external_id, Post.id)
        .filter(Post.source_id == source_id, Post.external_id.in_(needed_parent_external_ids))
        .all()
    )
    for row in child_rows:
        parent_external_id = processed.parent_external_id_by_external_id.get(row["external_id"])
        row["parent_post_id"] = id_map.get(parent_external_id)

    child_result = upsert_posts(session, child_rows)
    return UpsertResult(
        inserted=parent_result.inserted + child_result.inserted,
        skipped_duplicate=parent_result.skipped_duplicate + child_result.skipped_duplicate,
    )


def _run_post_source(session: Session, topic: Topic, source: Source, max_limit: int | None = None) -> SourceCycleResult:
    """`max_limit`: ngân sách thu thập MIỄN PHÍ còn lại trong ngày của tài khoản dùng thử (xem
    _trial_daily_crawl_remaining) — None nghĩa là không giới hạn (tài khoản trả phí)."""
    try:
        known_ids = _get_known_external_ids(session, source.id)
        limit = INCREMENTAL_LIMIT_PER_SOURCE if known_ids else BACKFILL_LIMIT_PER_SOURCE
        if max_limit is not None:
            limit = min(limit, max_limit)

        collector = get_collector(source.type, source.config)
        raw_posts = collector.collect(limit=limit, known_ids=known_ids)
        if collector.resolved_config_update:
            # Lưu lại id app vừa tự resolve được từ "query" (tên ngân hàng) — để chu kỳ sau dùng
            # thẳng id thay vì search lại, và để dashboard dựng được link thẳng tới trang app (xem
            # _build_app_url trong src/api/routes_dashboard.py) thay vì trang tìm kiếm chung chung.
            # Gán mới cả dict (không mutate in-place) để SQLAlchemy nhận diện đúng cột JSONB đã đổi.
            # Commit riêng ngay tại đây — không dựa vào commit trong upsert_posts() bên dưới, vì
            # hàm đó return sớm KHÔNG commit khi raw_posts rỗng (trường hợp rất phổ biến ở các chu
            # kỳ incremental không có review mới), khi đó thay đổi config sẽ bị mất khi session đóng.
            source.config = {**source.config, **collector.resolved_config_update}
            session.commit()
        processed = process_raw_posts(raw_posts, topic_id=topic.id, source_id=source.id)

        # is_duplicate=False mặc định cho MỌI row trước — pg_insert(...).values(rows) ở dưới compile
        # 1 câu INSERT dùng chung cho cả danh sách, nên mọi dict phải có ĐÚNG cùng 1 tập key, không
        # thể chỉ set "is_duplicate" cho riêng vài row rồi bỏ trống ở các row còn lại.
        for row in processed.rows:
            row["is_duplicate"] = False

        # Facebook hay gặp bài đăng lại/spam LẶP NGUYÊN VĂN nội dung nhưng khác NGÀY đăng (khác
        # external_id nên dedupe_in_batch/UNIQUE(source_id, external_id) ở trên không bắt được) —
        # chỉ bật cho facebook vì đây là nơi quan sát thấy hiện tượng này, chưa có bằng chứng cần
        # cho google_play/app_store (review gắn với tài khoản/thiết bị thật, ít khi bị đăng lại).
        duplicate_content_count = 0
        if source.type == "facebook":
            duplicate_ids = find_duplicate_content_ids(
                session, source.id, processed.rows, processed.parent_external_id_by_external_id
            )
            duplicate_content_count = len(duplicate_ids)
            for row in processed.rows:
                if row["external_id"] in duplicate_ids:
                    row["is_duplicate"] = True

        # Commit theo từng source (không gộp cả chu kỳ vào 1 transaction) để một nguồn lỗi
        # không làm rollback dữ liệu các nguồn khác đã thu thập thành công trong cùng chu kỳ.
        upsert_result = _upsert_posts_with_parent_links(session, source.id, processed)

        logger.info(
            "[%s/%s] fetched=%d inserted=%d trùng=%d spam=%d trùng nội dung=%d",
            topic.name,
            source.type,
            len(raw_posts),
            upsert_result.inserted,
            upsert_result.skipped_duplicate,
            processed.spam_count,
            duplicate_content_count,
        )

        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=len(raw_posts),
            inserted=upsert_result.inserted,
            skipped_duplicate=upsert_result.skipped_duplicate,
            spam=processed.spam_count,
            duplicate_content=duplicate_content_count,
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Lỗi khi thu thập topic=%s source=%s", topic.name, source.type)
        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=0,
            inserted=0,
            skipped_duplicate=0,
            spam=0,
            error=str(exc),
        )


def _sync_post_source_from_canonical(
    session: Session, topic: Topic, source: Source, canonical_source_id
) -> SourceCycleResult:
    """Source này trùng định danh app thật (package_name/app_id) với 1 source 'canonical' ở topic
    khác (xem src/pipeline/processing/cross_topic_dedup.py) — thay vì gọi lại API bên ngoài, sao
    chép thẳng content post đã có sẵn từ canonical, và Prediction nếu canonical đã phân tích xong.
    Không bao giờ tự gọi LLM ở nhánh này (xem run_analysis_cycle loại follower khỏi hàng đợi) —
    review cùng nội dung chỉ tốn quota LLM đúng 1 lần, dùng chung cho mọi topic theo dõi cùng app.
    """
    try:
        known_ids = _get_known_external_ids(session, source.id)
        canonical_posts = session.query(Post).filter(Post.source_id == canonical_source_id).all()

        new_rows = [
            {
                "topic_id": topic.id,
                "source_id": source.id,
                "external_id": p.external_id,
                "raw_content": p.raw_content,
                "content": p.content,
                "language": p.language,
                "posted_at": p.posted_at,
                "reply_content": p.reply_content,
                "reply_at": p.reply_at,
                "is_spam": p.is_spam,
                "status": p.status,
                "priority_score": p.priority_score,
            }
            for p in canonical_posts
            if p.external_id and p.external_id not in known_ids
        ]
        upsert_result = upsert_posts(session, new_rows) if new_rows else UpsertResult(inserted=0, skipped_duplicate=0)
        predictions_copied = _copy_missing_predictions(session, source, canonical_source_id)

        logger.info(
            "[%s/%s] đồng bộ từ source canonical=%s: post mới=%d, prediction sao chép=%d",
            topic.name,
            source.type,
            canonical_source_id,
            upsert_result.inserted,
            predictions_copied,
        )

        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=len(new_rows),
            inserted=upsert_result.inserted,
            skipped_duplicate=upsert_result.skipped_duplicate,
            spam=0,
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Lỗi khi đồng bộ topic=%s source=%s từ canonical", topic.name, source.type)
        return SourceCycleResult(
            topic_name=topic.name,
            source_type=source.type,
            fetched=0,
            inserted=0,
            skipped_duplicate=0,
            spam=0,
            error=str(exc),
        )


def _copy_missing_predictions(session: Session, source: Source, canonical_source_id) -> int:
    """Với mọi post của `source` CHƯA có Prediction, sao chép Prediction từ post cùng external_id
    bên canonical nếu đã có — không đụng tới post đã tự có Prediction riêng (vd còn sót lại từ
    trước khi có cơ chế đồng bộ này)."""
    canonical_rows = (
        session.query(Post.external_id, Prediction)
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(Post.source_id == canonical_source_id)
        .all()
    )
    canonical_by_external_id = {external_id: prediction for external_id, prediction in canonical_rows}
    if not canonical_by_external_id:
        return 0

    local_posts_missing_prediction = (
        session.query(Post)
        .outerjoin(Prediction, Prediction.post_id == Post.id)
        .filter(
            Post.source_id == source.id,
            Prediction.id.is_(None),
            Post.external_id.in_(canonical_by_external_id.keys()),
        )
        .all()
    )

    copied = 0
    for post in local_posts_missing_prediction:
        canonical_prediction = canonical_by_external_id.get(post.external_id)
        if canonical_prediction is None:
            continue
        session.add(_clone_prediction(post.id, canonical_prediction))
        copied += 1
    if copied:
        session.commit()
    return copied


def _clone_prediction(post_id, source_prediction: Prediction) -> Prediction:
    return Prediction(
        post_id=post_id,
        sentiment=source_prediction.sentiment,
        topic_label=source_prediction.topic_label,
        severity_score=source_prediction.severity_score,
        confidence_score=source_prediction.confidence_score,
        content_reliability=source_prediction.content_reliability,
        is_question=source_prediction.is_question,
        model_version=source_prediction.model_version,
        classified_at=source_prediction.classified_at,
        reference_status=source_prediction.reference_status,
        reference_sources=source_prediction.reference_sources,
        reference_confidence=source_prediction.reference_confidence,
        reference_checked_at=source_prediction.reference_checked_at,
        consensus_status=source_prediction.consensus_status,
        final_confidence=source_prediction.final_confidence,
        reasoning=source_prediction.reasoning,
        consensus_at=source_prediction.consensus_at,
    )


def main() -> None:
    configure_logging()
    result = run_cycle()
    print(
        f"\nCycle done in {result.elapsed_seconds:.1f}s — "
        f"fetched={result.total_fetched} inserted={result.total_inserted} sources={len(result.sources)}"
    )
    for s in result.sources:
        status = f"ERROR: {s.error}" if s.error else ("skipped (chưa tới lịch)" if s.skipped else "ok")
        print(f"  - {s.topic_name} / {s.source_type}: fetched={s.fetched} inserted={s.inserted} ({status})")


if __name__ == "__main__":
    main()
