import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Float, case, func
from sqlalchemy.orm import Session

from src.analysis.graph import analysis_graph
from src.analysis.knowledge_base.loader import load_topic_documents, select_relevant_docs
from src.analysis.llm import is_quota_error, pop_usage_log, reset_usage_log
from src.analysis.news_classification import classify_news_sentiment
from src.analysis.pain_point import run_pain_point_agent
from src.analysis.usage_tracking import persist_usage_log
from src.config import get_settings
from src.db.models import LLMUsage, OfficialDocument, Post, Prediction, Source, Topic, User
from src.db.session import SessionLocal
from src.logging_config import VN_TZ, configure_logging
from src.pipeline.processing.cross_topic_dedup import resolve_follower_sources
from src.pipeline.processing.seeding import count_similar_recent_posts

logger = logging.getLogger(__name__)

# Trần an toàn số post phân tích mỗi lần chạy — mỗi post tốn nhiều lượt gọi LLM (classify +
# verify + reasoning + description), nên giới hạn để không vượt quota Gemini free-tier trong 1 lần chạy.
DEFAULT_BATCH_LIMIT = 500

# Số bài báo (News Sentiment Agent) phân tích mỗi lần chạy — mỗi bài chỉ tốn 1 lượt gọi LLM (nhẹ
# hơn nhiều so với post), nhưng vẫn giới hạn để không cạnh tranh quota với phân tích phản hồi khách
# hàng (ưu tiên cao hơn — xem thứ tự gọi trong run_analysis_cycle).
DEFAULT_NEWS_BATCH_LIMIT = 100

# Mỗi post cần 2-3 lượt gọi LLM tuần tự (classify -> verify -> consensus reasoning). Từng thử
# concurrency=8 để tăng thông lượng (mỗi lượt gọi LLM là I/O-bound) nhưng đo thực tế trên Gemini
# free-tier bị RESOURCE_EXHAUSTED 429 gần như ngay lập tức: concurrency=8 tạo ra hàng chục request
# đồng thời mỗi vài giây — vượt xa trần RPM. SDK tự retry với backoff nên không lỗi hẳn, nhưng 8
# worker cùng retry chồng chéo khiến 1 batch nhỏ (100 post) chạy hàng giờ không xong thay vì ~vài
# phút. Việc giới hạn RPM giờ do rate limiter RIÊNG cho từng model xử lý đúng chỗ (xem
# src/analysis/llm.py::_rate_limiter_for — 1 token bucket/model, thread-safe, chặn MỌI client dù
# chạy ở thread nào), KHÔNG còn phụ thuộc giả định "tuần tự = tự nhiên đủ chậm" (giả định sai nếu model
# trả lời nhanh hơn nhịp RPM cho phép — đúng nguyên nhân gây 429 quan sát được trước khi có rate
# limiter). Vẫn giữ concurrency=1 vì tăng lên không giúp tăng thông lượng thật (rate limiter đằng
# nào cũng chặn ở đúng nhịp RPM đó) mà chỉ thêm rủi ro vô ích. Mỗi worker tự mở session DB riêng vì
# Session của SQLAlchemy không thread-safe.
DEFAULT_CONCURRENCY = 1

# "Trending": topic có tốc độ post mới trong SPIKE_WINDOW_HOURS gần nhất cao hơn hẳn baseline
# SPIKE_BASELINE_HOURS trước đó thì được ưu tiên phân tích trước trong đợt này — cùng kiểu ratio-
# threshold đã dùng ở compute_trend() (src/analysis/pain_point.py), chỉ khác cửa sổ ngắn hơn nhiều
# (phát hiện spike theo giờ, không phải theo tuần) vì mục đích ở đây là ưu tiên HÀNG ĐỢI PHÂN TÍCH,
# không phải gắn nhãn xu hướng cho pain point.
SPIKE_WINDOW_HOURS = 2
SPIKE_BASELINE_HOURS = 24
SPIKE_RATIO_THRESHOLD = 0.5  # tốc độ post/giờ trong window cao hơn baseline >50% coi là spike


@dataclass
class AnalysisCycleResult:
    analyzed: int = 0
    errors: int = 0
    consensus_counts: dict[str, int] = field(default_factory=dict)
    pain_points_created: int = 0
    elapsed_seconds: float = 0.0
    # True nếu chu kỳ này phải DỪNG SỚM vì quota LLM hết — các post còn lại trong post_batch (xem
    # pending_remaining) vẫn được lưu nguyên vẹn ở bảng posts, chỉ đơn giản là chưa có Prediction,
    # tự động nằm trong hàng đợi "pending" để chu kỳ sau xử lý tiếp (không mất dữ liệu).
    quota_exhausted: bool = False
    pending_remaining: int = 0
    # Số post bị BỎ QUA (không đưa vào post_batch) vì thuộc tài khoản dùng thử đã hết hạn/hết trần
    # (thời gian, trọn đời, hoặc NGÀY — xem _trial_users_blocked_from_analysis, trial_analysis_call_
    # limit/trial_daily_call_limit trong config.py) — KHÁC quota_exhausted (đó là quota LLM CHUNG
    # toàn hệ thống). Post này vẫn nằm nguyên trong hàng đợi "pending", tự động được xét lại ở chu kỳ
    # tiếp theo (ngay chu kỳ sau nếu tài khoản đã nâng cấp, hoặc hôm sau nếu chỉ tạm hết trần ngày).
    skipped_trial_limit: int = 0
    # News Sentiment Agent (xem _analyze_news_documents) — tách riêng khỏi analyzed/errors ở trên
    # vì đây là bài báo (official_documents), không phải post, dễ gây hiểu nhầm nếu gộp chung 1 số.
    news_analyzed: int = 0
    news_errors: int = 0


@dataclass
class _PostOutcome:
    success: bool
    consensus_status: str | None = None
    quota_exhausted: bool = False


def run_analysis_cycle(
    session: Session | None = None,
    limit: int = DEFAULT_BATCH_LIMIT,
    concurrency: int = DEFAULT_CONCURRENCY,
    topic_id: UUID | None = None,
) -> AnalysisCycleResult:
    """Chạy Classification -> Verification -> Consensus cho các post chưa có prediction (song
    song theo `concurrency` post cùng lúc), rồi Pain Point Agent gom nhóm kết quả theo topic.
    `topic_id`: giới hạn vào 1 topic cụ thể (vd chạy tay để dồn nợ backlog 1 topic) — mặc định
    None nghĩa là mọi topic đang active, đúng như hành vi khi chạy tự động theo lịch."""
    owns_session = session is None
    session = session or SessionLocal()
    start = time.monotonic()
    result = AnalysisCycleResult()

    try:
        spiking_topic_ids = _topics_with_recent_spike(session)

        effective_date = func.coalesce(Post.posted_at, Post.collected_at)
        order_columns = []
        if spiking_topic_ids:
            # Topic đang "spike" (tốc độ post mới tăng vọt so với baseline) được ưu tiên phân tích
            # TRƯỚC — đây là tín hiệu "trending" theo yêu cầu, tính trên khối lượng thu thập thô,
            # không phụ thuộc kết quả Classification (vốn chưa có ở bước này).
            order_columns.append(case((Post.topic_id.in_(spiking_topic_ids), 1), else_=0).desc())
        # Ưu tiên NGÀY gần đây nhất trước — TIÊU CHÍ CHÍNH, không phải tiebreak phụ như trước. Quota
        # LLM free-tier có hạn (xem DEFAULT_CONCURRENCY ở trên) nên không thể phân tích hết ngay lập
        # tức; review vừa đăng hôm nay PHẢI được phân tích trước hàng nghìn review backlog cũ hơn,
        # không để priority_score (heuristic độ nghiêm trọng) của 1 post cũ kéo nó lên trước post
        # mới — post mới luôn được xét trước. func.date(): gộp theo NGÀY (không phải chính xác tới
        # giây) để priority_score vẫn có đất dụng võ PHÂN ĐỊNH thứ tự giữa các post CÙNG ngày, thay
        # vì bị effective_date (đủ chi tiết tới giây, hiếm khi trùng) đè hoàn toàn, biến priority_score
        # thành tiêu chí chết. Hết việc mới (đã phân tích hết post trong ngày gần nhất) thì query tự
        # nhiên "rơi" xuống ngày kế tiếp cũ hơn ở chu kỳ sau — không cần logic "chuyển giai đoạn"
        # riêng, đây là hệ quả tự nhiên của việc luôn SELECT lại toàn bộ post CHƯA có Prediction sắp
        # theo đúng thứ tự này mỗi chu kỳ.
        # func.timezone(...): gộp theo NGÀY GIỜ VIỆT NAM, không phải theo timezone phiên Postgres
        # (mặc định UTC) — nếu không, post đăng 00h-07h sáng giờ VN bị tính nhầm sang ngày hôm
        # trước, mất đúng ưu tiên "hôm nay luôn được xét trước" nêu ở comment trên.
        order_columns.append(func.date(func.timezone(str(VN_TZ), effective_date)).desc())
        order_columns.append(Post.priority_score.desc())
        order_columns.append(effective_date.desc())  # tiebreak cuối: cùng ngày, cùng priority_score

        # Post thuộc source 'follower' (trùng định danh app thật package_name/app_id với 1 source
        # 'canonical' ở topic khác — xem src/pipeline/processing/cross_topic_dedup.py) KHÔNG bao giờ
        # tự gọi LLM ở đây: Prediction của chúng được sao chép lại từ canonical ngay khi crawl (xem
        # _sync_post_source_from_canonical trong src/pipeline/runner.py), tránh phân tích trùng cùng
        # 1 review dưới nhiều topic và tốn gấp đôi/gấp ba quota một cách vô ích.
        follower_source_ids = set(resolve_follower_sources(session).keys())

        # Xếp hạng RIÊNG theo TỪNG SOURCE (row_number PARTITION BY Post.source_id) rồi ghép
        # round-robin CÓ TRỌNG SỐ khi lấy batch cuối cùng — thay vì partition theo user như trước.
        # Lý do: quota LLM (RPM, xem src/analysis/llm.py::_rate_limiter_for) là TÀI NGUYÊN DÙNG
        # CHUNG toàn hệ thống — partition theo user vẫn để 1 SOURCE có backlog khổng lồ (vd Google
        # Play >6,900 post) CHIẾM HẾT lượt của chính user/topic đó, các source khác CÙNG topic (vd
        # Facebook chỉ 411 post) gần như không tới lượt dù không có gì bất thường (quan sát được
        # thật: Facebook kẹt sau Google Play/App Store nhiều ngày liền). Partition theo source_id
        # (không phải user_id) vẫn giữ nguyên tính công bằng GIỮA CÁC USER như thiết kế cũ (2 user
        # khác nhau luôn có source_id khác nhau nên vẫn tách bạch), CỘNG THÊM công bằng GIỮA CÁC
        # NGUỒN trong cùng 1 user.
        #
        # virtual_rank = rank_within_source / analysis_priority (Source.analysis_priority, doanh
        # nghiệp tự đặt qua PATCH /topics/{id}/sources/{id}, mặc định 1 = ngang nhau). Nguồn có
        # priority càng cao càng đạt cùng 1 mốc virtual_rank sau ÍT vòng hơn nên được xếp lên đầu
        # THƯỜNG XUYÊN HƠN theo đúng tỷ lệ (vd priority=3 so với priority=1: cứ 1 post của nguồn
        # priority=1 được chọn thì nguồn priority=3 đã được chọn 3 post) — nhưng KHÔNG BAO GIỜ về 0
        # lượt, khác hẳn thứ tự cứng "xong nguồn A mới tới nguồn B" (cách đó tái tạo lại đúng lỗi 1
        # nguồn chiếm hết batch mà cơ chế round-robin này sửa). coalesce(...,1): post mồ côi (source
        # đã bị xoá, source_id NULL do ondelete=SET NULL) vẫn được xếp hạng bình thường, không bị
        # loại khỏi hàng đợi.
        rank_within_source = func.row_number().over(partition_by=Post.source_id, order_by=order_columns)
        priority = func.coalesce(Source.analysis_priority, 1)
        virtual_rank = (func.cast(rank_within_source, Float) / priority).label("virtual_rank")
        ranked_query = (
            session.query(Post.id, Post.topic_id, Post.content, Topic.user_id, Post.source_id, virtual_rank)
            .join(Topic, Topic.id == Post.topic_id)
            .outerjoin(Source, Source.id == Post.source_id)
            .outerjoin(Prediction, Prediction.post_id == Post.id)
            .filter(
                Prediction.id.is_(None),
                Post.is_spam.is_(False),
                # Bài viết Facebook trùng nội dung 1 bài khác (xem
                # src/pipeline/processing/content_dedup.py) — không đáng tốn quota LLM phân tích lại
                # y hệt nội dung đã phân tích rồi.
                Post.is_duplicate.is_(False),
                Post.content.isnot(None),
            )
        )
        if follower_source_ids:
            ranked_query = ranked_query.filter(Post.source_id.notin_(follower_source_ids))
        if topic_id is not None:
            ranked_query = ranked_query.filter(Post.topic_id == topic_id)
        ranked = ranked_query.subquery()
        unanalyzed_posts = (
            session.query(ranked.c.id, ranked.c.topic_id, ranked.c.content, ranked.c.user_id)
            # virtual_rank thấp nhất trước — với priority bằng nhau (mặc định), đây chính là
            # round-robin đều như cũ. source_id chỉ để tiebreak, giữ thứ tự ổn định giữa các lần
            # chạy cùng dữ liệu.
            .order_by(ranked.c.virtual_rank.asc(), ranked.c.source_id.asc())
            .limit(limit)
            .all()
        )
        blocked_user_ids = _trial_users_blocked_from_analysis(session, {post.user_id for post in unanalyzed_posts})
        # Trích id/topic_id/content/user_id ra trước khi đưa sang thread khác — Row (không phải
        # object ORM Post) nên không gắn với session, nhưng vẫn giữ pattern tuple cũ để không đổi
        # chữ ký _analyze_post_standalone (user_id chỉ dùng LẠI để lọc trong vòng lặp bên dưới,
        # không truyền vào _analyze_post_standalone). Post thuộc user đã hết hạn/hết trần dùng thử
        # (blocked_user_ids) bị loại ngay ở đây — vẫn nằm trong bảng posts/hàng đợi "pending", chỉ
        # đơn giản chưa được ĐƯA vào batch xử lý chu kỳ này.
        post_batch = [
            (post.id, post.topic_id, post.content, post.user_id)
            for post in unanalyzed_posts
            if post.user_id not in blocked_user_ids
        ]
        result.skipped_trial_limit = len(unanalyzed_posts) - len(post_batch)

        if post_batch:
            processed_count = 0
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                for chunk_start in range(0, len(post_batch), concurrency):
                    chunk = post_batch[chunk_start : chunk_start + concurrency]
                    # Lọc lại NGAY TRƯỚC MỖI CHUNK, không chỉ 1 lần đầu chu kỳ ở trên —
                    # blocked_user_ids tính ở đầu hàm là snapshot LÚC BẮT ĐẦU chọn batch, nhưng 1
                    # chu kỳ có thể xử lý tới DEFAULT_BATCH_LIMIT=500 post, kéo dài hàng giờ (đặc
                    # biệt khi dính 429 rate-limit) — user có thể CHẠM trần ngày ngay GIỮA chu kỳ,
                    # nhưng các post của họ đã được chọn sẵn vào post_batch từ đầu vẫn chạy tiếp nếu
                    # không lọc lại ở đây (quan sát được thật: tài khoản vượt trần 50 lên tới 72 lượt
                    # trong cùng 1 chu kỳ). concurrency=1 nên chunk luôn có đúng 1 post — chi phí lọc
                    # lại (vài query COUNT nhỏ) không đáng kể so với ~15-20s mỗi lượt gọi LLM.
                    chunk_user_ids = {user_id for _, _, _, user_id in chunk}
                    newly_blocked = _trial_users_blocked_from_analysis(session, chunk_user_ids)
                    if newly_blocked:
                        result.skipped_trial_limit += sum(1 for _, _, _, user_id in chunk if user_id in newly_blocked)
                        chunk = [(pid, tid, content, uid) for pid, tid, content, uid in chunk if uid not in newly_blocked]
                    if not chunk:
                        continue
                    futures = [
                        executor.submit(_analyze_post_standalone, post_id, post_topic_id, content)
                        for post_id, post_topic_id, content, _user_id in chunk
                    ]
                    chunk_hit_quota = False
                    for future in as_completed(futures):
                        outcome = future.result()
                        processed_count += 1
                        if outcome.success:
                            result.analyzed += 1
                            status = outcome.consensus_status or "unknown"
                            result.consensus_counts[status] = result.consensus_counts.get(status, 0) + 1
                        else:
                            result.errors += 1
                            if outcome.quota_exhausted:
                                chunk_hit_quota = True
                    if chunk_hit_quota:
                        # Hết quota — dừng NGAY thay vì kiên trì thử hết batch (mỗi post còn lại
                        # cũng sẽ fail với cùng lý do, chỉ tốn thêm thời gian timeout/backoff). Các
                        # post chưa kịp xử lý vẫn đã được lưu ở bảng posts từ trước (Collector/
                        # Processing Agent không phụ thuộc bước này) — chỉ đơn giản là chưa có
                        # Prediction, tự động nằm trong hàng đợi "pending" cho chu kỳ sau.
                        result.quota_exhausted = True
                        break
            result.pending_remaining = len(post_batch) - processed_count

        # Bỏ qua hẳn nếu bước phân tích post ở trên đã hết quota — gọi tiếp chắc chắn cũng fail
        # ngay vì cùng 1 quota LLM, chỉ tốn thêm thời gian timeout/backoff vô ích. Phản hồi khách
        # hàng LUÔN ưu tiên hơn bài báo, nên bước này CHỦ Ý chạy SAU, không xen giữa batch post.
        if not result.quota_exhausted:
            news_query = session.query(OfficialDocument).filter(
                OfficialDocument.category == "news", OfficialDocument.sentiment.is_(None)
            )
            if topic_id is not None:
                news_query = news_query.filter(OfficialDocument.topic_id == topic_id)
            news_batch = news_query.limit(DEFAULT_NEWS_BATCH_LIMIT).all()
            for doc in news_batch:
                reset_usage_log()
                try:
                    news_result = classify_news_sentiment(doc.title, doc.content or "")
                    doc.sentiment = news_result.sentiment
                    doc.sentiment_classified_at = datetime.now(UTC)
                    persist_usage_log(session, pop_usage_log(), user_id=doc.topic.user_id, topic_id=doc.topic_id)
                    session.commit()
                    result.news_analyzed += 1
                except Exception as exc:
                    # classify_news_sentiment raise TRƯỚC khi gán doc.sentiment (xem thân hàm) nên
                    # session không có gì cần rollback ở đây — chỉ cần lưu lại usage đã tốn thật (dù
                    # kết quả cuối lỗi, vd parsing_error sau khi model đã trả lời) rồi commit riêng.
                    persist_usage_log(session, pop_usage_log(), user_id=doc.topic.user_id, topic_id=doc.topic_id)
                    session.commit()
                    result.news_errors += 1
                    if is_quota_error(exc):
                        # Cùng lý do dừng sớm như batch post ở trên — bài báo còn lại chưa xử lý
                        # vẫn giữ nguyên sentiment=NULL, tự động nằm trong hàng đợi chu kỳ sau.
                        break
                    logger.warning("Lỗi khi phân tích sắc thái bài báo id=%s", doc.id, exc_info=True)

        topics_query = session.query(Topic).filter(Topic.status == "active")
        if topic_id is not None:
            topics_query = topics_query.filter(Topic.id == topic_id)
        for topic in topics_query.all():
            pain_points = run_pain_point_agent(session, topic)
            result.pain_points_created += len(pain_points)
    finally:
        if owns_session:
            session.close()

    result.elapsed_seconds = time.monotonic() - start
    logger.info(
        "Chu kỳ phân tích hoàn tất trong %.1fs — analyzed=%d errors=%d news_analyzed=%d news_errors=%d "
        "pain_points=%d consensus=%s%s%s",
        result.elapsed_seconds,
        result.analyzed,
        result.errors,
        result.news_analyzed,
        result.news_errors,
        result.pain_points_created,
        result.consensus_counts,
        # Cố ý KHÔNG viết "HẾT QUOTA" — is_quota_error() gộp chung mọi lỗi 429 (RPM/TPM chạm trần
        # NGAY PHÚT ĐÓ lẫn RPD hết thật cho cả ngày), nên phần lớn trường hợp đây chỉ là giới hạn
        # tần suất tạm thời (tự hết sau 1 phút) chứ không phải quota ngày đã cạn — xem RPD trên
        # Google AI Studio dashboard để biết chắc có phải hết quota ngày thật hay không.
        f" — DỪNG SỚM DO GẶP GIỚI HẠN TẦN SUẤT LLM (lỗi 429 — có thể chỉ là RPM/TPM phút hiện tại, "
        f"không hẳn hết quota ngày), còn {result.pending_remaining} post chuyển sang hàng đợi chờ"
        if result.quota_exhausted
        else "",
        f" — {result.skipped_trial_limit} post bỏ qua vì tài khoản dùng thử đã hết hạn/hết trần" if result.skipped_trial_limit else "",
    )
    return result


def _topics_with_recent_spike(session: Session) -> set[UUID]:
    """Tập topic_id có tốc độ post mới (theo collected_at) trong SPIKE_WINDOW_HOURS gần nhất cao
    hơn hẳn baseline SPIKE_BASELINE_HOURS trước đó — dùng để ưu tiên hàng đợi phân tích, KHÔNG lưu
    cột mới (tính lại mỗi lần gọi, đủ rẻ vì chỉ 2 group-by COUNT)."""
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=SPIKE_WINDOW_HOURS)
    baseline_start = now - timedelta(hours=SPIKE_BASELINE_HOURS)

    window_counts = dict(
        session.query(Post.topic_id, func.count(Post.id))
        .filter(Post.collected_at >= window_start)
        .group_by(Post.topic_id)
        .all()
    )
    if not window_counts:
        return set()

    baseline_counts = dict(
        session.query(Post.topic_id, func.count(Post.id))
        .filter(Post.collected_at >= baseline_start, Post.collected_at < window_start)
        .group_by(Post.topic_id)
        .all()
    )

    baseline_hours_span = max(SPIKE_BASELINE_HOURS - SPIKE_WINDOW_HOURS, 1)
    spiking: set[UUID] = set()
    for topic_id, window_count in window_counts.items():
        baseline_hourly_rate = baseline_counts.get(topic_id, 0) / baseline_hours_span
        window_hourly_rate = window_count / SPIKE_WINDOW_HOURS
        if baseline_hourly_rate == 0:
            if window_count > 0:
                spiking.add(topic_id)
            continue
        if (window_hourly_rate - baseline_hourly_rate) / baseline_hourly_rate > SPIKE_RATIO_THRESHOLD:
            spiking.add(topic_id)
    return spiking


def _trial_users_blocked_from_analysis(session: Session, user_ids: set[UUID]) -> set[UUID]:
    """Tài khoản dùng thử (is_paid=False, có trial_ends_at) bị tạm dừng phân tích THÊM — do 1 trong
    3 lý do ĐỘC LẬP, hợp (OR) lại:
      - Hết hạn THỜI GIAN (trial_ends_at đã qua).
      - Hết trần TRỌN ĐỜI (trial_analysis_call_limit trong config.py).
      - Hết trần MIỄN PHÍ TRONG NGÀY (trial_daily_call_limit) — khác 2 lý do trên ở chỗ chỉ tạm dừng
        tới khi qua ngày mới, không phải vĩnh viễn tới khi nâng cấp.
    CẢ 3 đều KHÔNG khoá đăng nhập/dashboard (trước đây 2 lý do đầu làm login() trả 402 — đã gỡ, xem
    UserResponse.trial_expired và _build_user_response trong routes_auth.py để hiện banner mời nâng
    cấp thay vì chặn hẳn). Tính lại MỖI CHU KỲ (không lưu cột "đã reset chưa") — tự động đúng khi qua
    ngày mới vì mốc today_start trôi theo thời gian gọi thật, không cần job reset riêng."""
    if not user_ids:
        return set()
    trial_users = (
        session.query(User.id, User.trial_ends_at)
        .filter(User.id.in_(user_ids), User.is_paid.is_(False), User.trial_ends_at.isnot(None))
        .all()
    )
    if not trial_users:
        return set()
    trial_user_ids = {uid for uid, _ in trial_users}
    now = datetime.now(UTC)
    expired_by_time = {uid for uid, trial_ends_at in trial_users if trial_ends_at < now}

    lifetime_counts = dict(
        session.query(LLMUsage.user_id, func.count(LLMUsage.id))
        .filter(LLMUsage.user_id.in_(trial_user_ids))
        .group_by(LLMUsage.user_id)
        .all()
    )
    lifetime_limit = get_settings().trial_analysis_call_limit
    expired_by_usage = {uid for uid in trial_user_ids if lifetime_counts.get(uid, 0) >= lifetime_limit}

    # Giờ VN (không phải UTC) — đồng bộ mốc reset với _trial_daily_crawl_remaining
    # (src/pipeline/runner.py) và _build_user_response (src/api/routes_auth.py), xem comment ở đó.
    today_start = datetime.now(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_counts = dict(
        session.query(LLMUsage.user_id, func.count(LLMUsage.id))
        .filter(LLMUsage.user_id.in_(trial_user_ids), LLMUsage.created_at >= today_start)
        .group_by(LLMUsage.user_id)
        .all()
    )
    daily_limit = get_settings().trial_daily_call_limit
    over_daily_limit = {uid for uid in trial_user_ids if daily_counts.get(uid, 0) >= daily_limit}

    return expired_by_time | expired_by_usage | over_daily_limit


def _analyze_post_standalone(post_id: UUID, topic_id: UUID, content: str) -> _PostOutcome:
    """Chạy Classification->Verification->Consensus cho 1 post, trong thread riêng của nó — tự mở
    và đóng session DB riêng (Session của SQLAlchemy không thread-safe để dùng chung)."""
    session = SessionLocal()
    try:
        try:
            topic_docs = select_relevant_docs(content, load_topic_documents(session, topic_id))
        except Exception:
            # Tra cứu tài liệu crawl được là phần BỔ SUNG cho Verification Agent — lỗi ở đây (vd sự
            # cố DB tạm thời) không được chặn việc phân tích post; verify_post(topic_docs=None) vẫn
            # chạy được với kho tĩnh toàn cục.
            logger.warning("Lỗi khi tải tài liệu đối chiếu cho topic_id=%s — bỏ qua, dùng kho tĩnh", topic_id)
            topic_docs = []

        try:
            similar_post_count = count_similar_recent_posts(session, topic_id, content, exclude_post_id=post_id)
        except Exception:
            # Cùng triết lý topic_docs ở trên — lỗi truy vấn cụm bài KHÔNG được chặn phân tích,
            # Seeding Agent vẫn chạy được với similar_post_count=0 (chỉ mất tín hiệu cụm dồn dập).
            logger.warning("Lỗi khi đếm bài viết tương tự cho topic_id=%s — bỏ qua, similar_post_count=0", topic_id)
            similar_post_count = 0

        # user_id của chủ topic — cần để ghi llm_usage đúng tài khoản (xem persist_usage_log).
        owner_user_id = session.query(Topic.user_id).filter(Topic.id == topic_id).scalar()

        reset_usage_log()
        state = analysis_graph.invoke(
            {
                "post_id": post_id,
                "content": content,
                "topic_docs": topic_docs,
                "similar_post_count": similar_post_count,
            }
        )
        # Ghi nhận usage NGAY, kể cả khi state báo lỗi bên dưới — 1 post có thể classify thành công
        # rồi verify mới fail (state["error"]), token của bước classify VẪN đã tốn thật, phải ghi
        # nhận đúng, không được bỏ qua chỉ vì post cuối cùng không phân tích xong.
        persist_usage_log(session, pop_usage_log(), user_id=owner_user_id, topic_id=topic_id)
        session.commit()

        if state.get("error"):
            logger.warning("Lỗi phân tích post_id=%s: %s", post_id, state["error"])
            return _PostOutcome(success=False, quota_exhausted=bool(state.get("quota_exhausted")))

        classification = state["classification"]
        verification = state["verification"]
        now = datetime.now(UTC)

        session.add(
            Prediction(
                post_id=post_id,
                sentiment=classification.sentiment,
                topic_label=classification.topic_label,
                severity_score=classification.severity_score,
                confidence_score=classification.confidence_score,
                content_reliability=classification.content_reliability,
                is_question=classification.is_question,
                model_version=get_settings().analysis_model_name,
                classified_at=now,
                reference_status=verification.reference_status,
                reference_sources=[src.model_dump() for src in verification.reference_sources],
                reference_confidence=verification.reference_confidence,
                reference_checked_at=now,
                # Danh tính khách hàng: chưa có tích hợp CRM nên luôn để mặc định 'unverified'.
                # Khi nào nối được CRM thì set verification_status/identity_checked_at ở đây.
                consensus_status=state["consensus_status"],
                final_confidence=state["final_confidence"],
                reasoning=state["reasoning"],
                consensus_at=now,
                # None nếu case đủ rõ ràng ngay từ Consensus (không cần cross-check, xem
                # graph.py::_should_cross_check) — .get() vì AnalysisState total=False, key này
                # không tồn tại trong dict trả về khi không đi qua cross_check_node.
                cross_check_agreed=state.get("cross_check_agreed"),
                # seeding vắng mặt (None) khi Seeding Agent lỗi/nuốt lỗi (xem
                # graph.py::detect_seeding_node) — is_seeding mặc định False, chỉ CẢNH BÁO chứ
                # không loại post khỏi pain point.
                is_seeding=state["seeding"].is_seeding if state.get("seeding") else False,
                seeding_reasoning=state["seeding"].reasoning if state.get("seeding") else None,
            )
        )
        session.commit()
        return _PostOutcome(success=True, consensus_status=state["consensus_status"])
    except Exception:
        session.rollback()
        logger.exception("Lỗi khi phân tích post_id=%s", post_id)
        return _PostOutcome(success=False)
    finally:
        session.close()


def main() -> None:
    configure_logging()
    result = run_analysis_cycle()
    print(
        f"\nAnalysis cycle done in {result.elapsed_seconds:.1f}s — "
        f"analyzed={result.analyzed} errors={result.errors} pain_points={result.pain_points_created}"
    )
    print(f"Consensus breakdown: {result.consensus_counts}")
    if result.quota_exhausted:
        print(f"Quota exhausted — {result.pending_remaining} post(s) still pending for next cycle")


if __name__ == "__main__":
    main()
