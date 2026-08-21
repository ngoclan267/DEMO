import clsx from "clsx";
import type {
  ConsensusStatus,
  ContentReliability,
  DocumentCategory,
  IdentityStatus,
  LifecycleStatus,
  ReferenceRelation,
  ReferenceStatus,
  Sentiment,
  Trend,
} from "@/lib/types";

/* Pill + dot — cùng ngôn ngữ hình ảnh với SeverityPill của thiết kế tham khảo, dùng 1 bảng "tone"
   nhỏ (map 1:1 từ bảng màu Tailwind gốc trước đây: green->leaf, red->rose, amber->amber, blue->sky,
   slate->muted) để giữ nguyên đúng ý nghĩa/mức độ nghiêm trọng của từng badge, chỉ đổi giá trị màu. */
type Tone = "leaf" | "rose" | "amber" | "sky" | "muted";

const TONE_CLASS: Record<Tone, string> = {
  leaf: "bg-[var(--color-leaf)]/10 text-[var(--color-leaf)]",
  rose: "bg-[var(--color-rose)]/10 text-[var(--color-rose)]",
  amber: "bg-[var(--color-amber-glow)]/10 text-[var(--color-amber-glow)]",
  sky: "bg-[var(--color-sky)]/10 text-[var(--color-sky)]",
  muted: "bg-[var(--color-cream-2)] text-[var(--color-muted)]",
};

const TONE_DOT: Record<Tone, string> = {
  leaf: "bg-[var(--color-leaf)]",
  rose: "bg-[var(--color-rose)]",
  amber: "bg-[var(--color-amber-glow)]",
  sky: "bg-[var(--color-sky)]",
  muted: "bg-[var(--color-muted)]",
};

function Badge({ tone = "muted", className, children }: { tone?: Tone; className?: string; children: React.ReactNode }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        TONE_CLASS[tone],
        className,
      )}
    >
      <span aria-hidden className={clsx("h-1.5 w-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
      {children}
    </span>
  );
}

const SENTIMENT_LABEL: Record<Sentiment, string> = {
  positive: "Tích cực",
  neutral: "Trung lập",
  negative: "Tiêu cực",
};

const SENTIMENT_TONE: Record<Sentiment, Tone> = {
  positive: "leaf",
  neutral: "muted",
  negative: "rose",
};

/** Màu thanh viền/accent trái cho card danh sách phản hồi (Facebook/TikTok, Google Play/App Store,
 * dòng pain point...) — xuất dùng chung để mọi danh sách phản hồi trong hệ thống quét mắt bằng
 * cùng 1 quy ước màu, thay vì mỗi trang tự định nghĩa lại. Dùng CSS var trực tiếp (không phải class
 * Tailwind) vì cần gán vào style inline (border-left-color) cho card. */
export const SENTIMENT_ACCENT_COLOR: Record<Sentiment, string> = {
  positive: "var(--color-leaf)",
  neutral: "var(--color-line)",
  negative: "var(--color-rose)",
};

export function SentimentBadge({ sentiment }: { sentiment: Sentiment | null }) {
  if (!sentiment) return <Badge>Chưa phân tích</Badge>;
  return <Badge tone={SENTIMENT_TONE[sentiment]}>{SENTIMENT_LABEL[sentiment]}</Badge>;
}

/* --- Câu hỏi/thắc mắc của khách — ĐỘC LẬP với sentiment (xem Prediction.is_question) --- */
export function QuestionBadge({ isQuestion }: { isQuestion: boolean | null }) {
  if (!isQuestion) return null;
  return <Badge tone="sky">Góc thắc mắc</Badge>;
}

/** Cảnh báo nghi ngờ review/bình luận GIẢ MẠO, DÀN DỰNG (Seeding Agent) — CHỈ cảnh báo, không có
 * nghĩa là đã chắc chắn/đã bị loại khỏi phân tích (khác is_spam). `reasoning` hiện qua title (hover)
 * khi có, giữ giao diện gọn không cần thêm tooltip riêng. */
export function SeedingBadge({ isSeeding, reasoning }: { isSeeding: boolean; reasoning?: string | null }) {
  if (!isSeeding) return null;
  return (
    <span title={reasoning || undefined}>
      <Badge tone="amber">⚠ Nghi ngờ seeding</Badge>
    </span>
  );
}

export const SENTIMENT_OPTIONS: { value: Sentiment; label: string }[] = (
  ["negative", "neutral", "positive"] as const
).map((value) => ({ value, label: SENTIMENT_LABEL[value] }));

export function severityBucket(score: number): "low" | "medium" | "high" {
  if (score < 0.34) return "low";
  if (score < 0.67) return "medium";
  return "high";
}

const SEVERITY_TONE: Record<string, Tone> = {
  low: "sky",
  medium: "amber",
  high: "rose",
};

export const SEVERITY_LABEL: Record<string, string> = {
  low: "Nhẹ",
  medium: "Trung bình",
  high: "Nghiêm trọng",
};

export const SEVERITY_OPTIONS: { value: "low" | "medium" | "high"; label: string }[] = (
  ["low", "medium", "high"] as const
).map((value) => ({ value, label: SEVERITY_LABEL[value] }));

export function SeverityBadge({ score }: { score: number | null }) {
  if (score === null) return <Badge>—</Badge>;
  const bucket = severityBucket(score);
  return <Badge tone={SEVERITY_TONE[bucket]}>{SEVERITY_LABEL[bucket]}</Badge>;
}

/** Màu thanh viền/accent trái cho danh sách pain point — cùng quy ước với SENTIMENT_ACCENT_COLOR
 * (xem đó), chỉ khác trục màu (mức độ nghiêm trọng thay vì cảm xúc) vì pain point là 1 CỤM phản
 * hồi, "cảm xúc" của cả cụm không có ý nghĩa rõ ràng bằng mức độ nghiêm trọng trung bình. */
export const SEVERITY_ACCENT_COLOR: Record<"low" | "medium" | "high", string> = {
  low: "var(--color-sky)",
  medium: "var(--color-amber-glow)",
  high: "var(--color-rose)",
};

/* --- Đối chiếu VĂN BẢN chính thức (KHÔNG phải xác minh danh tính khách hàng) ---
   "no_match" cố ý dùng chữ trung tính: đa số review nói về lỗi kỹ thuật thông thường, không có
   văn bản chính thức nào nhắc tới — đó là bình thường, không phải một thất bại kiểm chứng. */
const REFERENCE_LABEL: Record<ReferenceStatus, string> = {
  matched: "Có văn bản liên quan",
  no_match: "Không có văn bản liên quan",
  conflicting: "Các nguồn mâu thuẫn",
};

const REFERENCE_TONE: Record<ReferenceStatus, Tone> = {
  matched: "sky",
  no_match: "muted",
  conflicting: "amber",
};

export function ReferenceBadge({ status }: { status: ReferenceStatus | null }) {
  if (!status) return <Badge>—</Badge>;
  return <Badge tone={REFERENCE_TONE[status]}>{REFERENCE_LABEL[status]}</Badge>;
}

/* --- Quan hệ của 1 tài liệu đối chiếu cụ thể với review (xem ReferenceSource trong lib/types) --- */
const REFERENCE_RELATION_LABEL: Record<ReferenceRelation, string> = {
  explains_as_policy: "Giải thích theo chính sách",
  confirms_issue: "Xác nhận sự cố có thật",
};

const REFERENCE_RELATION_TONE: Record<ReferenceRelation, Tone> = {
  explains_as_policy: "muted",
  confirms_issue: "rose",
};

export function ReferenceRelationBadge({ relation }: { relation: ReferenceRelation }) {
  return <Badge tone={REFERENCE_RELATION_TONE[relation]}>{REFERENCE_RELATION_LABEL[relation]}</Badge>;
}

/* --- Xác minh DANH TÍNH khách hàng (CRM) --- */
const IDENTITY_LABEL: Record<IdentityStatus, string> = {
  verified: "Đã xác minh danh tính",
  unverified: "Chưa xác minh danh tính",
};

const IDENTITY_TONE: Record<IdentityStatus, Tone> = {
  verified: "leaf",
  unverified: "muted",
};

export function IdentityBadge({ status }: { status: IdentityStatus | null }) {
  if (!status) return <Badge>—</Badge>;
  return <Badge tone={IDENTITY_TONE[status]}>{IDENTITY_LABEL[status]}</Badge>;
}

/* --- AI đánh giá độ tin cậy NỘI DUNG theo tính cụ thể của mô tả --- */
const RELIABILITY_LABEL: Record<ContentReliability, string> = {
  high: "Mô tả cụ thể",
  medium: "Mô tả khá chung",
  low: "Mô tả mơ hồ",
};

const RELIABILITY_TONE: Record<ContentReliability, Tone> = {
  high: "leaf",
  medium: "amber",
  low: "muted",
};

export function ContentReliabilityBadge({ reliability }: { reliability: ContentReliability | null }) {
  if (!reliability) return <Badge>Chưa đánh giá</Badge>;
  return <Badge tone={RELIABILITY_TONE[reliability]}>{RELIABILITY_LABEL[reliability]}</Badge>;
}

/* --- Kết luận của AI ---
   Tiền tố "AI đánh giá" là cố ý: trước đây nhãn "Xác nhận là vấn đề thật" đọc như đã được kiểm
   chứng, đặt cạnh "Chưa xác minh" thành ra mâu thuẫn. Đây chỉ là suy luận của mô hình. */
const CONSENSUS_LABEL: Record<ConsensusStatus, string> = {
  confirmed: "AI đánh giá: vấn đề thật",
  dismissed: "Không phải lỗi (đã giải thích)",
  needs_review: "Cần người xem xét",
};

const CONSENSUS_TONE: Record<ConsensusStatus, Tone> = {
  confirmed: "rose",
  dismissed: "muted",
  needs_review: "amber",
};

export function ConsensusBadge({ status }: { status: ConsensusStatus | null }) {
  if (!status) return <Badge>—</Badge>;
  return <Badge tone={CONSENSUS_TONE[status]}>{CONSENSUS_LABEL[status]}</Badge>;
}

/* Cross-Check Agent — chỉ chạy khi Kết luận ban đầu là "Cần người xem xét" (xem
   src/analysis/graph.py::_should_cross_check), dùng model độc lập thứ 2 để phân loại lại. null =
   chưa cross-check (case đủ rõ ràng ngay từ đầu, không cần), không hiện badge — không phải "chưa
   xử lý". */
export function CrossCheckBadge({ agreed }: { agreed: boolean | null }) {
  if (agreed === null) return null;
  return agreed ? (
    <Badge tone="leaf">Đã kiểm tra chéo: đồng thuận</Badge>
  ) : (
    <Badge tone="rose">Đã kiểm tra chéo: bất đồng</Badge>
  );
}

const TREND_LABEL: Record<Trend, string> = {
  increasing: "↑ Đang tăng",
  stable: "→ Ổn định",
  decreasing: "↓ Đang giảm",
};

const TREND_TONE: Record<Trend, Tone> = {
  increasing: "rose",
  stable: "muted",
  decreasing: "leaf",
};

export function TrendBadge({ trend }: { trend: Trend | null }) {
  if (!trend) return null;
  return <Badge tone={TREND_TONE[trend]}>{TREND_LABEL[trend]}</Badge>;
}

/* --- Vòng đời xử lý (con người vận hành) --- */
const LIFECYCLE_LABEL: Record<LifecycleStatus, string> = {
  new: "Mới",
  in_progress: "Đang xử lý",
  resolved: "Đã xử lý",
  duplicate: "Trùng lặp",
  ignored: "Bỏ qua",
};

const LIFECYCLE_TONE: Record<LifecycleStatus, Tone> = {
  new: "sky",
  in_progress: "amber",
  resolved: "leaf",
  duplicate: "muted",
  ignored: "muted",
};

export function LifecycleBadge({ status }: { status: LifecycleStatus }) {
  return <Badge tone={LIFECYCLE_TONE[status]}>{LIFECYCLE_LABEL[status]}</Badge>;
}

export const LIFECYCLE_OPTIONS: { value: LifecycleStatus; label: string }[] = (
  ["new", "in_progress", "resolved", "duplicate", "ignored"] as const
).map((value) => ({ value, label: LIFECYCLE_LABEL[value] }));

/* --- Loại tài liệu đối chiếu CHÍNH THỨC từ website ngân hàng (xem BankWebsiteCollector) ---
   "news" cố ý KHÔNG nằm trong DOCUMENT_CATEGORY_OPTIONS: đó là tin bên thứ ba (NewsApifyCollector),
   hiển thị riêng ở mục "Bài báo liên quan", không phải nguồn đối chiếu chính thức của doanh nghiệp. */
const DOCUMENT_CATEGORY_LABEL: Record<DocumentCategory, string> = {
  notice: "Thông báo",
  policy: "Chính sách",
  fee: "Biểu phí",
  incident: "Sự cố",
  maintenance: "Bảo trì",
  product: "Sản phẩm",
  news: "Tin tức",
  other: "Khác",
};

const DOCUMENT_CATEGORY_TONE: Record<DocumentCategory, Tone> = {
  notice: "sky",
  policy: "muted",
  fee: "amber",
  incident: "rose",
  maintenance: "amber",
  product: "leaf",
  news: "muted",
  other: "muted",
};

export function DocumentCategoryBadge({ category }: { category: DocumentCategory }) {
  return <Badge tone={DOCUMENT_CATEGORY_TONE[category]}>{DOCUMENT_CATEGORY_LABEL[category]}</Badge>;
}

export const DOCUMENT_CATEGORY_OPTIONS: { value: DocumentCategory; label: string }[] = (
  ["notice", "policy", "fee", "incident", "maintenance", "product", "other"] as const
).map((value) => ({ value, label: DOCUMENT_CATEGORY_LABEL[value] }));
