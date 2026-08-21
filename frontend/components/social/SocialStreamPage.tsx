"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowSquareOut,
  ChatCircle,
  FacebookLogo,
  ShareNetwork,
  ThumbsUp,
  TiktokLogo,
} from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { PainPointSummary, PostSummary, Topic } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { SentimentBadge, QuestionBadge, SeedingBadge, LifecycleBadge, SENTIMENT_ACCENT_COLOR } from "@/components/ui/Badges";
import { ExpandableText } from "@/components/ui/ExpandableText";
import { PostDate } from "@/components/posts/PostDate";
import { Dialog } from "@/components/ui/Dialog";
import { Topbar } from "@/components/layout/Topbar";

const PAGE_SIZE = 20;

type Tab = "all" | "positive" | "negative" | "question";

// Biểu tượng nền tảng nhỏ đặt cạnh nội dung — chỉ 2 nền tảng có trang luồng riêng (Facebook/TikTok,
// xem lib/socialPlatforms.tsx) nên map trực tiếp theo sourceType, không cần truyền qua config.
const PLATFORM_ICON: Record<string, typeof FacebookLogo> = {
  facebook: FacebookLogo,
  tiktok: TiktokLogo,
};

const TABS: { value: Tab; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "positive", label: "Tích cực" },
  { value: "negative", label: "Tiêu cực" },
  { value: "question", label: "Góc thắc mắc" },
];

/** Cấu hình riêng theo nền tảng — logic list/dialog/tab/pain-point/phân trang dùng CHUNG (xem
 * frontend/app/(dashboard)/topics/[id]/facebook/page.tsx trước khi tách, giờ chỉ còn 1 bản duy nhất
 * ở đây). Thêm nền tảng mới (vd LinkedIn) chỉ cần 1 trang mỏng truyền config này, không lặp lại
 * ~250 dòng list/dialog/phân trang cho mỗi nền tảng. */
export interface SocialPlatformConfig {
  sourceType: string;
  pageTitle: string;
  cardTitle: string;
  dialogTitle: string;
  viewOnPlatformLabel: string;
  description: ReactNode;
}

function buildQuery(sourceType: string, tab: Tab, limit: number, offset: number): string {
  const params = new URLSearchParams({
    source_type: sourceType,
    limit: String(limit),
    offset: String(offset),
  });
  if (tab === "positive") params.set("sentiment", "positive");
  if (tab === "negative") params.set("sentiment", "negative");
  if (tab === "question") params.set("is_question", "true");
  return params.toString();
}

function EngagementStats({ post }: { post: PostSummary }) {
  if (post.like_count === null && post.comment_count === null && post.share_count === null) return null;
  return (
    <div className="flex items-center gap-3.5 text-xs text-[var(--color-muted)]">
      {post.like_count !== null && (
        <span className="flex items-center gap-1">
          <ThumbsUp size={13} /> {post.like_count}
        </span>
      )}
      {post.comment_count !== null && (
        <span className="flex items-center gap-1">
          <ChatCircle size={13} /> {post.comment_count}
        </span>
      )}
      {post.share_count !== null && (
        <span className="flex items-center gap-1">
          <ShareNetwork size={13} /> {post.share_count}
        </span>
      )}
    </div>
  );
}

function ViewOnPlatformLink({ url, label }: { url: string | null; label: string }) {
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="inline-flex items-center gap-1 text-xs font-medium text-[var(--color-brand-600)] hover:underline"
    >
      {label} <ArrowSquareOut size={12} />
    </a>
  );
}

/** Nhóm chủ đề (topic_label) mà Classification Agent gán cho post/comment này — cùng nhãn dùng để
 * gom pain point (xem PainPoint.title == Prediction.topic_label ở backend). Nhóm đã đủ ngưỡng cảnh
 * báo (đã thành pain point thật) thì bấm vào đi thẳng tới đó để xử lý; chưa đủ ngưỡng thì chỉ hiện
 * nhãn tham khảo, chưa có nơi nào để "xử lý" (chưa có case). */
function PainPointTag({
  topicId,
  topicLabel,
  painPointByTitle,
}: {
  topicId: string;
  topicLabel: string | null;
  painPointByTitle: Map<string, PainPointSummary>;
}) {
  if (!topicLabel) return null;
  const painPoint = painPointByTitle.get(topicLabel);

  if (!painPoint) {
    return (
      <span
        className="rounded-full bg-[var(--color-cream-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--color-ink-2)]"
        title="Nhóm chủ đề chưa đủ ngưỡng cảnh báo nên chưa tạo thành pain point"
      >
        {topicLabel}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <Link
        href={`/topics/${topicId}/pain-points/${painPoint.id}`}
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-center gap-1 rounded-full bg-[var(--color-cream-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--color-ink-2)] transition-colors hover:bg-[var(--color-bone)]"
      >
        {topicLabel} <ArrowSquareOut size={11} />
      </Link>
      <LifecycleBadge status={painPoint.lifecycle_status} />
    </span>
  );
}

/** Xuất công khai để trang chi tiết pain point (xem topics/[id]/pain-points/[painPointId]) dùng
 * lại đúng dialog này khi phản hồi thuộc nguồn có cấu trúc bài viết/comment (Facebook/TikTok), thay
 * vì chỉ dùng PostDetailModal "phẳng" như phản hồi Google Play/App Store. */
export function PostCommentsDialog({
  post,
  topicId,
  painPointByTitle,
  config,
  onClose,
}: {
  post: PostSummary;
  topicId: string;
  painPointByTitle: Map<string, PainPointSummary>;
  config: SocialPlatformConfig;
  onClose: () => void;
}) {
  const [comments, setComments] = useState<PostSummary[] | null>(null);

  useEffect(() => {
    api
      .get<PostSummary[]>(`/posts/${post.id}/comments`)
      .then(setComments)
      .catch(() => setComments([]));
  }, [post.id]);

  return (
    <Dialog open onClose={onClose} title={config.dialogTitle} size="lg">
      <div className="space-y-4">
        <div className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-cream-2)]/40 p-4">
          <ExpandableText text={post.content} />
          <div className="mt-3 flex flex-wrap items-center gap-2.5">
            <SentimentBadge sentiment={post.sentiment} />
            <QuestionBadge isQuestion={post.is_question} />
            <SeedingBadge isSeeding={post.is_seeding} reasoning={post.seeding_reasoning} />
            <PainPointTag topicId={topicId} topicLabel={post.topic_label} painPointByTitle={painPointByTitle} />
            <EngagementStats post={post} />
            <PostDate postedAt={post.posted_at} collectedAt={post.collected_at} />
            <ViewOnPlatformLink url={post.source_url} label={config.viewOnPlatformLabel} />
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium tracking-[0.06em] text-[var(--color-muted)] uppercase">
            Bình luận {comments ? `(${comments.length})` : ""}
          </p>
          {comments === null && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}
          {comments !== null && comments.length === 0 && (
            <p className="text-sm text-[var(--color-muted)]">Chưa thu thập được bình luận nào cho bài viết này.</p>
          )}
          <div className="max-h-[50vh] space-y-2 overflow-y-auto">
            {comments?.map((c) => (
              <div key={c.id} className="rounded-2xl border border-[var(--color-line)] bg-white p-3.5">
                <ExpandableText text={c.content} />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <SentimentBadge sentiment={c.sentiment} />
                  <QuestionBadge isQuestion={c.is_question} />
                  <SeedingBadge isSeeding={c.is_seeding} reasoning={c.seeding_reasoning} />
                  <PainPointTag topicId={topicId} topicLabel={c.topic_label} painPointByTitle={painPointByTitle} />
                  <PostDate postedAt={c.posted_at} collectedAt={c.collected_at} />
                  <ViewOnPlatformLink url={c.source_url} label={config.viewOnPlatformLabel} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Dialog>
  );
}

export function SocialStreamPage({ topicId, config }: { topicId: string; config: SocialPlatformConfig }) {
  const [topic, setTopic] = useState<Topic | null>(null);
  const [tab, setTab] = useState<Tab>("all");
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<PostSummary | null>(null);
  const [painPointByTitle, setPainPointByTitle] = useState<Map<string, PainPointSummary>>(new Map());

  useEffect(() => {
    api.get<Topic>(`/topics/${topicId}`).then(setTopic);
    // Nhãn nhóm chủ đề (topic_label) của post/comment khớp title của pain point cùng chủ đề (xem
    // PainPoint.title == Prediction.topic_label ở backend) — tải 1 lần để tra cứu, không phải gọi
    // API riêng cho từng post.
    api
      .get<PainPointSummary[]>(`/topics/${topicId}/pain-points`)
      .then((pps) => setPainPointByTitle(new Map(pps.map((pp) => [pp.title, pp]))))
      .catch(() => {});
  }, [topicId]);

  async function loadMore(currentOffset: number) {
    setLoading(true);
    try {
      const page = await api.get<PostSummary[]>(
        `/topics/${topicId}/posts?${buildQuery(config.sourceType, tab, PAGE_SIZE, currentOffset)}`,
      );
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
  }, [topicId, tab]);

  return (
    <div>
      <Topbar title={config.pageTitle} subtitle={topic ? topic.name : undefined} />

      <div className="pt-6">
        <Link
          href={`/topics/${topicId}`}
          className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]"
        >
          ← Quay lại dashboard
        </Link>

        <p className="mt-3 mb-4 text-sm leading-relaxed text-[var(--color-muted)]">{config.description}</p>

        <div className="mb-4 flex flex-wrap gap-1.5">
          {TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTab(t.value)}
              aria-pressed={tab === t.value}
              className={clsx(
                "relative rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors",
                tab === t.value
                  ? "border-[var(--color-brand-500)] text-white"
                  : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]",
              )}
            >
              {tab === t.value && (
                <motion.span
                  layoutId="social-tab-pill"
                  className="absolute inset-0 rounded-full bg-[var(--color-brand-500)]"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <span className="relative">{t.label}</span>
            </button>
          ))}
        </div>

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>{config.cardTitle}</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <AnimatePresence initial={false}>
              {posts.map((post, index) => {
                const PlatformIcon = PLATFORM_ICON[config.sourceType];
                const accent = post.sentiment ? SENTIMENT_ACCENT_COLOR[post.sentiment] : "var(--color-line)";
                return (
                  <motion.button
                    key={post.id}
                    onClick={() => setSelected(post)}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.04 }}
                    whileHover={{ y: -3 }}
                    style={{ borderLeftColor: accent }}
                    className="group relative flex w-full gap-3 overflow-hidden rounded-2xl border border-[var(--color-line)] border-l-[3px] bg-white p-4 text-left shadow-[0_1px_2px_rgba(11,18,32,0.04)] transition-[border-color,box-shadow] duration-300 hover:border-[var(--color-bone)] hover:shadow-[0_14px_32px_rgba(11,18,32,0.10)]"
                  >
                    {PlatformIcon && (
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-cream-2)] text-[var(--color-ink-2)] transition-colors duration-300 group-hover:bg-[var(--color-brand-500)]/10 group-hover:text-[var(--color-brand-700)]">
                        <PlatformIcon size={15} weight="fill" />
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="mb-2.5 line-clamp-3 text-[13.5px] leading-relaxed text-[var(--color-ink)]">{post.content}</p>
                      <div className="flex flex-wrap items-center gap-2.5">
                        <SentimentBadge sentiment={post.sentiment} />
                        <QuestionBadge isQuestion={post.is_question} />
                        <SeedingBadge isSeeding={post.is_seeding} reasoning={post.seeding_reasoning} />
                        <PainPointTag topicId={topicId} topicLabel={post.topic_label} painPointByTitle={painPointByTitle} />
                        <EngagementStats post={post} />
                        <PostDate postedAt={post.posted_at} collectedAt={post.collected_at} />
                        <span className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[var(--color-brand-600)] transition-transform duration-300 group-hover:translate-x-0.5">
                          Xem bình luận →
                        </span>
                      </div>
                    </div>
                  </motion.button>
                );
              })}
            </AnimatePresence>

            {posts.length === 0 && !loading && (
              <p className="text-sm text-[var(--color-muted)]">Chưa có bài viết nào khớp bộ lọc.</p>
            )}

            {hasMore && (
              <div className="pt-2">
                <button
                  onClick={() => loadMore(offset)}
                  disabled={loading}
                  className="text-sm font-medium text-[var(--color-brand-600)] hover:underline disabled:opacity-50"
                >
                  {loading ? "Đang tải..." : "Tải thêm"}
                </button>
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {selected && (
        <PostCommentsDialog
          post={selected}
          topicId={topicId}
          painPointByTitle={painPointByTitle}
          config={config}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
