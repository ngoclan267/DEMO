const SEVERITY_META: Record<string, { label: string; className: string }> = {
  low: { label: "Nhẹ", className: "bg-severity-low" },
  medium: { label: "Trung bình", className: "bg-severity-medium" },
  high: { label: "Nghiêm trọng", className: "bg-severity-high" },
};

// Export để dùng chung cho nút chọn nguồn trên biểu đồ xu hướng (xem
// frontend/app/(dashboard)/topics/[id]/page.tsx) — tránh có thêm 1 bảng nhãn nguồn thứ 3 (đã có
// SOURCE_LABEL riêng ở topics/[id]/posts/page.tsx cho dropdown lọc).
export const SOURCE_META: Record<string, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn",
  facebook: "Facebook",
  tiktok: "TikTok",
  bank_website: "Website ngân hàng",
  news_article: "Bài báo",
};

// Cùng bảng màu SENTIMENT_TONE đang dùng ở Badges.tsx (leaf/muted/rose) — nhất quán giữa badge
// từng phản hồi và thanh tổng hợp này.
const SENTIMENT_META: Record<string, { label: string; className: string }> = {
  positive: { label: "Tích cực", className: "bg-[var(--color-leaf)]" },
  neutral: { label: "Trung tính", className: "bg-[var(--color-muted)]" },
  negative: { label: "Tiêu cực", className: "bg-[var(--color-rose)]" },
};

// Cùng họ màu với LIFECYCLE_CLASS (badge) trong Badges.tsx — sắc độ đậm hơn vì đây là fill thanh
// bar chứ không phải nền pill nhạt, giữ liên tưởng màu nhất quán giữa 2 nơi hiển thị.
const LIFECYCLE_META: Record<string, { label: string; className: string }> = {
  new: { label: "Mới", className: "bg-[var(--color-sky)]" },
  in_progress: { label: "Đang xử lý", className: "bg-[var(--color-amber-glow)]" },
  resolved: { label: "Đã xử lý", className: "bg-[var(--color-leaf)]" },
  duplicate: { label: "Trùng lặp", className: "bg-[var(--color-muted)]" },
  ignored: { label: "Bỏ qua", className: "bg-[var(--color-line)]" },
};

function BarRow({ label, count, total, colorClassName }: { label: string; count: number; total: number; colorClassName: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-xs">
        <span className="font-medium text-[var(--color-ink-2)]">{label}</span>
        <span className="text-[var(--color-muted)]">
          <span className="tabular-nums font-semibold text-[var(--color-ink-2)]">{count}</span>
          <span className="ml-1.5 tabular-nums text-[var(--color-muted)]">{pct}%</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-cream-2)]">
        <div className={`h-full rounded-full transition-[width] ${colorClassName}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function SeverityBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-3">
      {(["low", "medium", "high"] as const).map((key) => (
        <BarRow
          key={key}
          label={SEVERITY_META[key].label}
          count={breakdown[key] || 0}
          total={total}
          colorClassName={SEVERITY_META[key].className}
        />
      ))}
    </div>
  );
}

export function SourceBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  const entries = Object.entries(breakdown);
  if (entries.length === 0) return <p className="text-sm text-[var(--color-muted)]">Chưa có dữ liệu.</p>;
  return (
    <div className="space-y-3">
      {entries.map(([key, count]) => (
        <BarRow key={key} label={SOURCE_META[key] || key} count={count} total={total} colorClassName="bg-brand-500" />
      ))}
    </div>
  );
}

export function SentimentBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  if (total === 0) return <p className="text-sm text-[var(--color-muted)]">Chưa có dữ liệu.</p>;
  return (
    <div className="space-y-3">
      {(["positive", "neutral", "negative"] as const).map((key) => (
        <BarRow
          key={key}
          label={SENTIMENT_META[key].label}
          count={breakdown[key] || 0}
          total={total}
          colorClassName={SENTIMENT_META[key].className}
        />
      ))}
    </div>
  );
}

export function LifecycleBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  if (total === 0) return <p className="text-sm text-[var(--color-muted)]">Chưa có pain point nào.</p>;
  return (
    <div className="space-y-3">
      {(["new", "in_progress", "resolved", "duplicate", "ignored"] as const).map((key) => (
        <BarRow
          key={key}
          label={LIFECYCLE_META[key].label}
          count={breakdown[key] || 0}
          total={total}
          colorClassName={LIFECYCLE_META[key].className}
        />
      ))}
    </div>
  );
}
