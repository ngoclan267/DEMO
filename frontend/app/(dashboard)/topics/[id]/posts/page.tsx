"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { PostSummary, Topic } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  SentimentBadge,
  SeverityBadge,
  LifecycleBadge,
  LIFECYCLE_OPTIONS,
  SEVERITY_OPTIONS,
  SENTIMENT_OPTIONS,
  SENTIMENT_ACCENT_COLOR,
} from "@/components/ui/Badges";
import { PostDetailModal } from "@/components/posts/PostDetailModal";
import { PostDate } from "@/components/posts/PostDate";
import type { LifecycleStatus } from "@/lib/types";
import { Topbar } from "@/components/layout/Topbar";

const PAGE_SIZE = 20;

const SOURCE_LABEL: Record<string, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn",
  facebook: "Facebook",
  tiktok: "TikTok",
};
const SOURCE_OPTIONS = Object.entries(SOURCE_LABEL).map(([value, label]) => ({ value, label }));

const selectClass =
  "h-11 rounded-xl border border-[var(--color-line)] bg-white px-3 text-[13.5px] text-[var(--color-ink)] outline-none transition focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-500)]/20";

interface Filters {
  q: string;
  sourceType: string;
  severity: string;
  dateFrom: string;
  dateTo: string;
  lifecycleStatus: string;
  sentiment: string;
  analyzedOnly: boolean;
}

const EMPTY_FILTERS: Filters = {
  q: "",
  sourceType: "",
  severity: "",
  dateFrom: "",
  dateTo: "",
  lifecycleStatus: "",
  sentiment: "",
  analyzedOnly: false,
};

// Mọi bộ lọc chạy Ở BACKEND (query DB) — hàm này chỉ gộp state hiện tại thành query string, không
// tự lọc mảng post nào ở client.
function buildQuery(filters: Filters, limit: number, offset: number): string {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters.q) params.set("q", filters.q);
  if (filters.sourceType) params.set("source_type", filters.sourceType);
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  if (filters.lifecycleStatus) params.set("lifecycle_status", filters.lifecycleStatus);
  if (filters.sentiment) params.set("sentiment", filters.sentiment);
  if (filters.analyzedOnly) params.set("analyzed_only", "true");
  return params.toString();
}

function TopicPostsContent() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Đọc lối tắt cũ (?filter=negative|analyzed từ các ô thống kê dashboard) làm giá trị khởi tạo —
  // chỉ dùng 1 lần lúc vào trang, sau đó thanh lọc mới là nguồn sự thật duy nhất.
  const [filters, setFilters] = useState<Filters>(() => {
    const legacy = searchParams.get("filter");
    return { ...EMPTY_FILTERS, sentiment: legacy === "negative" ? "negative" : "", analyzedOnly: legacy === "analyzed" };
  });
  const [searchInput, setSearchInput] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Topic[]>("/topics")
      .then(setTopics)
      .catch(() => {});
  }, []);

  // Gõ từ khoá không gọi API ngay mỗi phím — đợi 400ms sau lần gõ cuối. setState nằm trong
  // callback của setTimeout (hệ thống bên ngoài), không phải thân effect, nên không phạm quy tắc
  // "đừng setState đồng bộ trong effect".
  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((f) => (f.q === searchInput ? f : { ...f, q: searchInput }));
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  async function loadMore(currentOffset: number) {
    setLoading(true);
    try {
      const page = await api.get<PostSummary[]>(`/topics/${id}/posts?${buildQuery(filters, PAGE_SIZE, currentOffset)}`);
      setPosts((prev) => (currentOffset === 0 ? page : [...prev, ...page]));
      setOffset(currentOffset + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-filter-change, standard pattern
    setPosts([]);
    loadMore(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    id,
    filters.q,
    filters.sourceType,
    filters.severity,
    filters.dateFrom,
    filters.dateTo,
    filters.lifecycleStatus,
    filters.sentiment,
    filters.analyzedOnly,
  ]);

  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  function onTopicChange(newTopicId: string) {
    // Đổi chủ đề nhưng giữ nguyên mọi bộ lọc khác đang bật — người dùng đang lọc "tiêu cực,
    // Google Play" thì xem sang ngân hàng khác cũng nên giữ đúng bộ lọc đó.
    router.push(`/topics/${newTopicId}/posts?${buildQuery(filters, PAGE_SIZE, 0)}`);
  }

  const currentTopic = topics.find((t) => t.id === id);
  const hasActiveFilters =
    filters.q || filters.sourceType || filters.severity || filters.dateFrom || filters.dateTo || filters.lifecycleStatus;

  return (
    <div>
      <Topbar
        title="Danh sách phản hồi"
        cta={
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-[var(--color-muted)]">Chủ đề</span>
            <select className={selectClass} value={id} onChange={(e) => onTopicChange(e.target.value)}>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        }
      />

      <div className="pt-6">
        <Link href={`/topics/${id}`} className="text-sm text-[var(--color-muted)] hover:text-[var(--color-ink)]">
          ← Quay lại dashboard
        </Link>

        <Card className="mt-4 mb-4 p-5">
          <CardBody className="space-y-3 p-0">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Tìm theo từ khoá trong nội dung phản hồi..."
            />
            <div>
              <span className="mb-1.5 block text-xs font-medium text-[var(--color-ink-2)]">Cảm xúc</span>
              <div className="flex flex-wrap gap-1.5">
                {[{ value: "", label: "Tất cả" }, ...SENTIMENT_OPTIONS].map((o) => (
                  <button
                    key={o.value || "all"}
                    type="button"
                    onClick={() => set("sentiment", o.value)}
                    aria-pressed={filters.sentiment === o.value}
                    className={clsx(
                      "rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors",
                      filters.sentiment === o.value
                        ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                        : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]",
                    )}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <div>
                <span className="mb-1 block text-xs font-medium text-[var(--color-ink-2)]">Nguồn dữ liệu</span>
                <select
                  className={`${selectClass} w-full`}
                  value={filters.sourceType}
                  onChange={(e) => set("sourceType", e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {SOURCE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <span className="mb-1 block text-xs font-medium text-[var(--color-ink-2)]">Mức độ nghiêm trọng</span>
                <select
                  className={`${selectClass} w-full`}
                  value={filters.severity}
                  onChange={(e) => set("severity", e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {SEVERITY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <span className="mb-1 block text-xs font-medium text-[var(--color-ink-2)]">Trạng thái case</span>
                <select
                  className={`${selectClass} w-full`}
                  value={filters.lifecycleStatus}
                  onChange={(e) => set("lifecycleStatus", e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {LIFECYCLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <span className="mb-1 block text-xs font-medium text-[var(--color-ink-2)]">Từ ngày</span>
                <input
                  type="date"
                  className={`${selectClass} w-full`}
                  value={filters.dateFrom}
                  onChange={(e) => set("dateFrom", e.target.value)}
                />
              </div>
              <div>
                <span className="mb-1 block text-xs font-medium text-[var(--color-ink-2)]">Đến ngày</span>
                <input
                  type="date"
                  className={`${selectClass} w-full`}
                  value={filters.dateTo}
                  onChange={(e) => set("dateTo", e.target.value)}
                />
              </div>
            </div>
            {hasActiveFilters && (
              <button
                onClick={() => setFilters((f) => ({ ...EMPTY_FILTERS, sentiment: f.sentiment, analyzedOnly: f.analyzedOnly }))}
                className="text-xs text-[var(--color-brand-600)] hover:underline"
              >
                Xoá bộ lọc
              </button>
            )}
          </CardBody>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>{currentTopic ? `Phản hồi — ${currentTopic.name}` : "Danh sách phản hồi"}</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <AnimatePresence initial={false}>
              {posts.map((post, index) => (
                <motion.button
                  key={post.id}
                  onClick={() => setSelectedPostId(post.id)}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.04 }}
                  whileHover={{ y: -3 }}
                  style={{ borderLeftColor: post.sentiment ? SENTIMENT_ACCENT_COLOR[post.sentiment] : "var(--color-line)" }}
                  className="block w-full rounded-2xl border border-[var(--color-line)] border-l-[3px] bg-white p-4 text-left shadow-[0_1px_2px_rgba(11,18,32,0.04)] transition-[border-color,box-shadow] duration-300 hover:border-[var(--color-bone)] hover:shadow-[0_14px_32px_rgba(11,18,32,0.10)]"
                >
                  <p className="mb-2.5 text-sm text-[var(--color-ink)]">&ldquo;{post.content}&rdquo;</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <SentimentBadge sentiment={post.sentiment} />
                    <SeverityBadge score={post.severity_score} />
                    {post.topic_label && (
                      <span className="rounded-full bg-[var(--color-cream-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--color-ink-2)]">
                        {post.topic_label}
                      </span>
                    )}
                    {post.pain_point_lifecycle_status && (
                      <LifecycleBadge status={post.pain_point_lifecycle_status as LifecycleStatus} />
                    )}
                    {post.source_type && (
                      <span className="text-xs text-[var(--color-muted)]">{SOURCE_LABEL[post.source_type] || post.source_type}</span>
                    )}
                    <PostDate postedAt={post.posted_at} collectedAt={post.collected_at} />
                  </div>
                </motion.button>
              ))}
            </AnimatePresence>

            {posts.length === 0 && !loading && (
              <p className="text-sm text-[var(--color-muted)]">Không có phản hồi nào khớp bộ lọc.</p>
            )}

            {hasMore && (
              <div className="pt-2">
                <Button variant="secondary" onClick={() => loadMore(offset)} loading={loading}>
                  Tải thêm
                </Button>
              </div>
            )}
          </CardBody>
        </Card>

        {selectedPostId && <PostDetailModal postId={selectedPostId} onClose={() => setSelectedPostId(null)} />}
      </div>
    </div>
  );
}

export default function TopicPostsPage() {
  return (
    <Suspense fallback={null}>
      <TopicPostsContent />
    </Suspense>
  );
}
