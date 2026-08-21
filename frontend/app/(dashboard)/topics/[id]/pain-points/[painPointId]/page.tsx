"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { HourlyTrendPoint, PainPointSummary, PostSummary, TrendPoint } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { SentimentBadge, SeverityBadge, SeedingBadge, ReferenceBadge, TrendBadge, SENTIMENT_ACCENT_COLOR } from "@/components/ui/Badges";
import { PostDetailModal } from "@/components/posts/PostDetailModal";
import { PostDate } from "@/components/posts/PostDate";
import { PostCommentsDialog } from "@/components/social/SocialStreamPage";
import { SOCIAL_PLATFORM_CONFIG_BY_SOURCE_TYPE } from "@/lib/socialPlatforms";
import { LifecyclePanel } from "@/components/painpoints/LifecyclePanel";
import { PriorityToggle } from "@/components/painpoints/PriorityToggle";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { Topbar } from "@/components/layout/Topbar";

const PAGE_SIZE = 20;

const SOURCE_LABEL: Record<string, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn",
  facebook: "Facebook",
  tiktok: "TikTok",
};

export default function PainPointDrillDownPage() {
  const { id, painPointId } = useParams<{ id: string; painPointId: string }>();
  const [painPoint, setPainPoint] = useState<PainPointSummary | null>(null);
  // Các pain point khác cùng chủ đề — cần cho dropdown "trùng với pain point nào".
  const [siblings, setSiblings] = useState<PainPointSummary[]>([]);
  const [trend, setTrend] = useState<TrendPoint[] | null>(null);
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selectedPost, setSelectedPost] = useState<PostSummary | null>(null);
  // "" = tất cả nguồn. Danh sách nguồn để chọn lấy từ painPoint.sources (xem PainPointSummary) —
  // chỉ những nguồn THỰC SỰ đóng góp vào nhóm này, không phải toàn bộ nguồn có thể có.
  const [sourceFilter, setSourceFilter] = useState("");
  const fetchingRef = useRef(false);

  useEffect(() => {
    api.get<PainPointSummary[]>(`/topics/${id}/pain-points`).then((all) => {
      setSiblings(all);
      setPainPoint(all.find((p) => p.id === painPointId) || null);
    });
  }, [id, painPointId]);

  useEffect(() => {
    api.get<TrendPoint[]>(`/pain-points/${painPointId}/trend`).then(setTrend);
  }, [painPointId]);

  async function loadMore(fromOffset = offset) {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(fromOffset) });
      if (sourceFilter) params.set("source_type", sourceFilter);
      const page = await api.get<PostSummary[]>(`/pain-points/${painPointId}/posts?${params.toString()}`);
      setPosts((prev) => {
        const base = fromOffset === 0 ? [] : prev;
        const merged = [...base, ...page];
        const seen = new Set<string>();
        return merged.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
      });
      setOffset(fromOffset + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } finally {
      fetchingRef.current = false;
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-filter-change, standard pattern
    setHasMore(true);
    loadMore(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [painPointId, sourceFilter]);

  return (
    <div>
      <Topbar
        title={painPoint?.title || "Pain point"}
        subtitle="Nhóm phản hồi cùng chủ đề đạt ngưỡng cảnh báo"
        cta={
          painPoint && (
            <div className="flex items-center gap-2 rounded-md border border-[var(--color-line)] bg-white px-3 py-1.5">
              <PriorityToggle painPoint={painPoint} onUpdated={setPainPoint} />
              <span className="text-[13px] text-[var(--color-ink-2)]">Cấp thiết nhất</span>
            </div>
          )
        }
      />

      <div className="pt-6">
        <Link
          href={`/topics/${id}`}
          className="text-sm text-[var(--color-muted)] hover:text-[var(--color-ink)]"
        >
          ← Quay lại dashboard
        </Link>

        {painPoint && (
          <div className="mt-3 mb-6">
            <div className="flex flex-wrap items-center gap-2">
              <TrendBadge trend={painPoint.trend} />
              <ReferenceBadge status={painPoint.reference_status} />
            </div>
            {painPoint.description && <p className="mt-2 text-sm text-[var(--color-muted)]">{painPoint.description}</p>}
            <p className="mt-1 text-xs text-[var(--color-muted)]">{painPoint.post_count} phản hồi thuộc nhóm này</p>
          </div>
        )}

        {painPoint && (
          <LifecyclePanel painPoint={painPoint} topicId={id} siblings={siblings} onUpdated={setPainPoint} />
        )}

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Xu hướng riêng của &quot;{painPoint?.title}&quot;</CardTitle>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">
              30 ngày gần nhất — so sánh tuần này với tuần trước xem ở badge{" "}
              <TrendBadge trend={painPoint?.trend ?? null} /> phía trên.
            </p>
          </CardHeader>
          <CardBody>
            <TrendChart
              data={trend ?? []}
              onDrillDown={(date) => api.get<HourlyTrendPoint[]>(`/pain-points/${painPointId}/trend/hourly?date=${date}`)}
            />
          </CardBody>
        </Card>

        {painPoint && painPoint.sources.length > 1 && (
          <div className="mb-4 flex flex-wrap gap-1.5">
            {[{ value: "", label: "Tất cả" }, ...painPoint.sources.map((s) => ({ value: s, label: SOURCE_LABEL[s] || s }))].map(
              (o) => (
                <button
                  key={o.value || "all"}
                  type="button"
                  onClick={() => setSourceFilter(o.value)}
                  aria-pressed={sourceFilter === o.value}
                  className={clsx(
                    "rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors",
                    sourceFilter === o.value
                      ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                      : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]",
                  )}
                >
                  {o.label}
                </button>
              ),
            )}
          </div>
        )}

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Toàn bộ phản hồi</CardTitle>
          </CardHeader>
          <CardBody className="space-y-2.5">
            <AnimatePresence initial={false}>
              {posts.map((post, index) => (
                <motion.button
                  key={post.id}
                  onClick={() => setSelectedPost(post)}
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
                    <SeedingBadge isSeeding={post.is_seeding} reasoning={post.seeding_reasoning} />
                    {post.source_type && (
                      <span className="text-xs text-[var(--color-muted)]">{SOURCE_LABEL[post.source_type] || post.source_type}</span>
                    )}
                    <PostDate postedAt={post.posted_at} collectedAt={post.collected_at} />
                  </div>
                </motion.button>
              ))}
            </AnimatePresence>

            {posts.length === 0 && !loading && <p className="text-sm text-[var(--color-muted)]">Chưa có phản hồi nào.</p>}

            {hasMore && (
              <div className="pt-2">
                <Button variant="secondary" onClick={() => loadMore()} loading={loading}>
                  Tải thêm
                </Button>
              </div>
            )}
          </CardBody>
        </Card>

        {selectedPost &&
          (() => {
            const socialConfig = selectedPost.source_type ? SOCIAL_PLATFORM_CONFIG_BY_SOURCE_TYPE[selectedPost.source_type] : undefined;
            // Facebook/TikTok có cấu trúc bài viết/comment riêng — dùng đúng dialog đó (xem
            // comment kèm theo) thay vì modal "phẳng" chỉ hiện 1 phản hồi đơn lẻ.
            if (socialConfig) {
              return (
                <PostCommentsDialog
                  post={selectedPost}
                  topicId={id}
                  config={socialConfig}
                  painPointByTitle={painPoint ? new Map([[painPoint.title, painPoint]]) : new Map()}
                  onClose={() => setSelectedPost(null)}
                />
              );
            }
            return <PostDetailModal postId={selectedPost.id} onClose={() => setSelectedPost(null)} />;
          })()}
      </div>
    </div>
  );
}
