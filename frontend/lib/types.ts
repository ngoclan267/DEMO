export interface User {
  id: string;
  email: string;
  username: string | null;
  full_name: string | null;
  is_verified: boolean;
  /** Quản trị TỔNG nền tảng — khác chủ sở hữu topic (is_owner ở Topic), chỉ vài tài khoản có. */
  is_platform_admin: boolean;
  /** false với tài khoản "dùng thử" (plan="trial" lúc platform admin tạo — xem POST /topics/admin, trial_ends_at) và chưa nâng cấp qua VNPay. */
  is_paid: boolean;
  /** Còn hạn hay đã qua hạn, KHÔNG khoá đăng nhập dù đã qua (xem trial_expired bên dưới) — null = không giới hạn. */
  trial_ends_at: string | null;
  created_at: string;
  /** True khi hết hạn THỜI GIAN (trial_ends_at đã qua) HOẶC hết trần TRỌN ĐỜI (trial_analysis_call_limit,
   * không lộ số cụ thể ra User) — KHÔNG khoá đăng nhập/dashboard, chỉ để hiện banner mời nâng cấp
   * THƯỜNG TRỰC (xem TrialQuotaBanner.tsx). Backend đã tự tạm dừng phân tích thêm cho tài khoản này.
   * Luôn false với tài khoản không phải dùng thử. */
  trial_expired: boolean;
  /** null nếu KHÔNG phải tài khoản dùng thử. Trần lượt gọi AI miễn phí TRONG 1 NGÀY (UTC) — khác
   * trần trọn đời ở trial_expired (đó tạm dừng vĩnh viễn, đây chỉ tạm dừng tới ngày mới, xem
   * trial_daily_call_limit trong config.py). */
  trial_daily_call_limit: number | null;
  trial_daily_call_count: number | null;
  /** Số PHẢN HỒI thật đã phân tích hôm nay (đếm Prediction thật) — KHÁC trial_daily_call_count (đếm
   * lượt gọi LLM thô, 1 phản hồi tốn 2-3 lượt) — dùng số NÀY khi hiển thị cho người dùng, không
   * dùng trial_daily_call_count để tránh hiểu nhầm số lượt gọi = số phản hồi. */
  trial_daily_responses_analyzed: number | null;
  /** Trần THU THẬP (Collector Agent) MIỄN PHÍ TRONG NGÀY — TÁCH BIỆT với 3 field phân tích AI ở
   * trên, gộp cả review lẫn tài liệu đối chiếu của MỌI topic user này sở hữu (xem
   * trial_daily_crawl_limit trong config.py). null nếu KHÔNG phải tài khoản dùng thử. */
  trial_daily_crawl_limit: number | null;
  trial_daily_crawl_count: number | null;
}

export interface BillingPlan {
  id: string;
  name: string;
  price_vnd: number;
  description: string;
}

/** Tổng token đã dùng + chi phí ƯỚC TÍNH (xem src/analysis/pricing.py) — không phải số tiền thật
 * đã bị trừ khi model đang ở free-tier (xem has_unpriced_usage nếu có model chưa rõ giá). */
export interface AdminUserUsageSummary {
  total_input_tokens: number;
  total_output_tokens: number;
  call_count: number;
  estimated_cost_usd: number;
  has_unpriced_usage: boolean;
}

export interface AdminUserSummary {
  id: string;
  email: string;
  full_name: string | null;
  username: string | null;
  is_platform_admin: boolean;
  is_paid: boolean;
  is_verified: boolean;
  trial_ends_at: string | null;
  created_at: string;
  topic_count: number;
  usage: AdminUserUsageSummary;
  /** null = không phải tài khoản dùng thử (is_paid=true hoặc không có trial_ends_at) — so với
   * usage.call_count để biết còn bao nhiêu lượt trước khi bị khoá đăng nhập (xem trial_analysis_call_limit
   * trong src/config.py). */
  trial_analysis_call_limit: number | null;
}

export interface AdminTopicSummary {
  id: string;
  name: string;
  status: TopicStatus;
  created_at: string;
  source_count: number;
  post_count: number;
  pain_point_count: number;
  usage: AdminUserUsageSummary;
}

export interface AdminUserDetail extends AdminUserSummary {
  topics: AdminTopicSummary[];
}

/** 1 yêu cầu "Liên hệ tư vấn" gửi từ trang giới thiệu công khai (xem POST /contact, trang
 * /admin/contacts) — thay cho tự đăng ký đã gỡ. */
export interface AdminContactSummary {
  id: string;
  company_name: string;
  contact_name: string;
  email: string;
  phone: string | null;
  message: string | null;
  is_handled: boolean;
  created_at: string;
}

export type SourceType = "google_play" | "app_store" | "linkedin" | "bank_website" | "facebook" | "news_article" | "tiktok";

export interface Source {
  id: string;
  type: SourceType;
  config: Record<string, unknown>;
  is_active: boolean;
  /** Lịch crawl riêng cho nguồn này (phút) — null nghĩa là dùng nhịp scheduler chung. */
  crawl_interval_minutes: number | null;
  last_crawled_at: string | null;
  /** Trọng số ưu tiên PHÂN TÍCH (không phải crawl) — mặc định 1 = ngang hàng mọi nguồn khác
   * (round-robin đều). Số lớn hơn được chọn vào batch phân tích thường xuyên hơn theo tỷ lệ, không
   * bao giờ về 0 lượt (xem src/analysis/runner.py::virtual_rank). */
  analysis_priority: number;
}

/** Loại tài liệu tham chiếu — "news" là tin bên thứ ba (qua NewsApifyCollector), các loại còn lại
 * là văn bản CHÍNH THỨC crawl được từ website ngân hàng. */
export type DocumentCategory =
  | "notice"
  | "policy"
  | "fee"
  | "incident"
  | "maintenance"
  | "product"
  | "news"
  | "other";

export interface OfficialDocument {
  id: string;
  category: DocumentCategory;
  title: string;
  url: string;
  content: string | null;
  published_at: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  /** Sắc thái đưa tin (News Sentiment Agent) — chỉ có với category="news", null với category khác. */
  sentiment: Sentiment | null;
  sentiment_classified_at: string | null;
}

export type NotifyChannel = "email" | "web" | "both";
export type TopicStatus = "active" | "archived";

export interface Topic {
  id: string;
  name: string;
  keywords: string[];
  alert_threshold: number;
  notify_enabled: boolean;
  notify_channel: NotifyChannel;
  status: TopicStatus;
  created_at: string;
  sources: Source[];
  /** Người đang đăng nhập có phải chủ sở hữu không — quyết định hiện nút quản trị. */
  is_owner: boolean;
  /** Tự động gán PHÒNG BAN (không chọn người cụ thể) cho pain point mới dựa trên độ phù hợp nội
   * dung — xem src/analysis/department_routing.py. Mặc định false (opt-in), khác notify_enabled. */
  auto_assign_enabled: boolean;
}

export interface TrendPoint {
  date: string;
  count: number;
  negative_count: number;
}

/** 1 điểm trend theo GIỜ trong 1 ngày cụ thể — zoom chi tiết từ TrendPoint (theo ngày), trả về từ
 * GET /pain-points/{id}/trend/hourly và GET /topics/{id}/trend/hourly. */
export interface HourlyTrendPoint {
  hour: string;
  count: number;
  negative_count: number;
}

/** 1 điểm trend trong GET /topics/{id}/compare-periods — thêm positive_count so với TrendPoint
 * (PeriodTrendChart cho chọn xem đường Tất cả/Tiêu cực/Tích cực). */
export interface PeriodTrendPoint {
  date: string;
  count: number;
  negative_count: number;
  positive_count: number;
}

/** 1 mốc thời gian trong GET /topics/{id}/compare-periods — xem PeriodComparisonResponse. */
export interface PeriodStats {
  date_from: string;
  date_to: string;
  post_count: number;
  sentiment_breakdown: Record<string, number>;
  negative_by_group: Record<string, number>;
  /** Pain point MỚI PHÁT SINH trong giai đoạn, không phải tổng số đang mở. */
  pain_point_count: number;
  /** Số liệu theo ngày trong giai đoạn — vẽ PeriodTrendChart (2 giai đoạn cạnh nhau). */
  trend: PeriodTrendPoint[];
}

export interface PeriodComparisonResponse {
  period_a: PeriodStats;
  period_b: PeriodStats;
}

export type Trend = "increasing" | "stable" | "decreasing";

/** Vòng đời xử lý do con người vận hành (khác reference_status — đánh giá của máy). */
export type LifecycleStatus = "new" | "in_progress" | "resolved" | "duplicate" | "ignored";
/** Trạng thái đã đóng — khớp CLOSED_LIFECYCLE_STATUSES trong src/sla.py. */
export const CLOSED_LIFECYCLE_STATUSES: LifecycleStatus[] = ["resolved", "duplicate", "ignored"];
export type SeverityLevel = "low" | "medium" | "high";

export interface AssigneeRef {
  id: string;
  email: string;
  full_name: string | null;
  /** Phòng ban của người này TRONG chủ đề đang xem — null cho chủ sở hữu hoặc thành viên chưa được
   * gán. Nguồn cho tự động phân việc, xem src/analysis/department_routing.py. */
  department: string | null;
}

export interface PainPointEvent {
  id: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  created_at: string;
  user: AssigneeRef | null;
}

export interface PainPointSummary {
  id: string;
  title: string;
  description: string | null;
  post_count: number;
  trend: Trend | null;
  reference_status: ReferenceStatus;
  severity_avg: number | null;
  confidence_avg: number | null;
  sources: string[];
  /** Doanh nghiệp tự đánh dấu là cấp thiết nhất — luôn đứng đầu danh sách bất kể severity_avg (xem
   * PATCH /pain-points/{id}/lifecycle). False mặc định = sắp theo severity_avg như trước. */
  is_priority: boolean;
  lifecycle_status: LifecycleStatus;
  assigned_user: AssigneeRef | null;
  department: string | null;
  due_at: string | null;
  /** True nếu quản lý đã tự đặt hạn (không phải tính tự động từ mức độ nghiêm trọng). */
  due_at_overridden: boolean;
  resolved_at: string | null;
  duplicate_of_id: string | null;
  lifecycle_note: string | null;
  /** Server tính sẵn để mọi màn hình dùng chung một định nghĩa quá hạn (xem src/sla.py). */
  is_breached: boolean;
  severity_level: SeverityLevel;
}

export interface DashboardSummary {
  negative_posts_count: number;
  total_posts_count: number;
  analyzed_posts_count: number;
  pending_analysis_count: number;
  severity_breakdown: Record<string, number>;
  source_breakdown: Record<string, number>;
  sentiment_breakdown: Record<string, number>;
  /** Số phản hồi tiêu cực theo từng nhóm chủ đề (1 trong 9 topic_label cố định). */
  negative_by_group: Record<string, number>;
  trend: TrendPoint[];
  top_pain_points: PainPointSummary[];
  overdue_count: number;
  due_soon_count: number;
  lifecycle_breakdown: Record<string, number>;
}

export type Sentiment = "positive" | "neutral" | "negative";

export interface PostSummary {
  id: string;
  content: string;
  language: string;
  sentiment: Sentiment | null;
  topic_label: string | null;
  severity_score: number | null;
  is_spam: boolean;
  /** Cảnh báo nghi ngờ review/bình luận GIẢ MẠO, DÀN DỰNG (Seeding Agent) — CHỈ cảnh báo, post này
   * vẫn được tính vào pain point bình thường (khác is_spam). */
  is_seeding: boolean;
  seeding_reasoning: string | null;
  posted_at: string | null;
  collected_at: string | null;
  source_type: string | null;
  /** Trạng thái xử lý của pain point chứa post này — null nếu chưa thuộc pain point nào. */
  pain_point_lifecycle_status: LifecycleStatus | null;
  /** Điểm ưu tiên PHÂN TÍCH — heuristic thuần, KHÔNG phải sentiment (xem src/pipeline/processing/priority.py). */
  priority_score: number;
  /** Số liệu tương tác — hiện chỉ có với bài viết Facebook/TikTok, null với mọi nguồn khác. */
  like_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  /** true/false = AI đã phân loại là câu hỏi/nhận xét; null = chưa phân tích. Độc lập với sentiment. */
  is_question: boolean | null;
  /** ID bài viết cha (Facebook/TikTok) nếu đây là 1 COMMENT; null với bài viết gốc và mọi nguồn khác. */
  parent_post_id: string | null;
  /** Link trực tiếp tới bài viết/comment gốc trên nền tảng nguồn — hiện chỉ Facebook/TikTok có. */
  source_url: string | null;
}

export interface SourceRef {
  source_type: string;
  app_url: string | null;
}

/** Xác minh DANH TÍNH khách hàng qua CRM/hệ thống nội bộ — hiện luôn "unverified" vì chưa tích hợp CRM. */
export type IdentityStatus = "verified" | "unverified";
/** AI đánh giá độ tin cậy NỘI DUNG dựa trên tính cụ thể của mô tả. */
export type ContentReliability = "high" | "medium" | "low";
/** Đối chiếu VĂN BẢN chính thức (QĐ 2345, TT 17/18, thông báo ngân hàng). */
export type ReferenceStatus = "matched" | "no_match" | "conflicting";
export type ConsensusStatus = "confirmed" | "dismissed" | "needs_review";

/** explains_as_policy: tài liệu giải thích đây là đúng quy định/chính sách, không phải lỗi.
 * confirms_issue: tài liệu xác nhận đây là sự cố/vấn đề có thật đã được ghi nhận chính thức. */
export type ReferenceRelation = "explains_as_policy" | "confirms_issue";

/** Một tài liệu tham chiếu cụ thể mà Verification Agent tìm được khớp với review (kho tĩnh QĐ
 * 2345/TT 17-18, hoặc tài liệu crawl được từ website ngân hàng — xem OfficialDocument). */
export interface ReferenceSource {
  doc_id: string;
  title: string;
  url: string;
  relation: ReferenceRelation;
}

export interface PostDetail extends PostSummary {
  // 3 khái niệm tách bạch — cố ý không gộp chung vào một chữ "xác minh".
  verification_status: IdentityStatus | null;
  content_reliability: ContentReliability | null;
  reference_status: ReferenceStatus | null;
  /** Rỗng khi reference_status không phải "matched". */
  reference_sources: ReferenceSource[];
  consensus_status: ConsensusStatus | null;
  reasoning: string | null;
  /** null = chưa cross-check (case đủ rõ ràng ngay từ Consensus, không cần — xem
   * src/analysis/graph.py::_should_cross_check). true/false = đã cross-check bằng model độc lập
   * thứ 2 (xem src/analysis/cross_check.py), có đồng thuận với phân loại gốc hay không. */
  cross_check_agreed: boolean | null;
  source: SourceRef | null;
  /** Phản hồi của nhà phát triển/ngân hàng — null nếu chưa có phản hồi hoặc nguồn không hỗ trợ (hiện chỉ Google Play). */
  reply_content: string | null;
  reply_at: string | null;
}

export type NotificationType =
  | "threshold_alert"
  | "assigned"
  | "resolved"
  | "daily_digest"
  | "department_assigned"
  | "contact_request";

export interface AppNotification {
  id: string;
  /** null cho contact_request — thông báo cấp nền tảng, không gắn topic nào. */
  topic_id: string | null;
  /** null cho daily_digest/contact_request — thông báo cấp topic/nền tảng, không gắn 1 pain point cụ thể. */
  pain_point_id: string | null;
  channel: string;
  notification_type: NotificationType;
  severity: number | null;
  message: string | null;
  sent_at: string;
  read_status: "unread" | "read";
}
