"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { FacebookLogo, Files, Hourglass, Newspaper, TiktokLogo, Users } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { DashboardSummary, HourlyTrendPoint, OfficialDocument, PainPointSummary, Topic } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatTile } from "@/components/dashboard/StatTile";
import { TrendChart } from "@/components/dashboard/TrendChart";
import {
  LifecycleBreakdown,
  SentimentBreakdown,
  SeverityBreakdown,
  SourceBreakdown,
  SOURCE_META,
} from "@/components/dashboard/BreakdownBars";
import { PartToWholePie } from "@/components/dashboard/PartToWholePie";
import {
  LifecycleBadge,
  ReferenceBadge,
  SentimentBadge,
  TrendBadge,
  severityBucket,
  SEVERITY_ACCENT_COLOR,
  SENTIMENT_ACCENT_COLOR,
} from "@/components/ui/Badges";
import { SlaBadge } from "@/components/painpoints/SlaBadge";
import { PriorityToggle } from "@/components/painpoints/PriorityToggle";
import { sortPainPoints } from "@/lib/painPointSort";
import { Topbar } from "@/components/layout/Topbar";

// Scheduler chạy nền liên tục phân tích thêm phản hồi/tạo pain point mới cho topic này — làm mới
// mỗi 30s để số liệu tự "nhảy số" mà không cần tải lại trang (xem lib/usePolling.ts).
const TOPIC_DASHBOARD_POLL_INTERVAL_MS = 30_000;

export default function TopicDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [painPoints, setPainPoints] = useState<PainPointSummary[] | null>(null);
  const [newsArticles, setNewsArticles] = useState<OfficialDocument[]>([]);
  // "all" = không lọc (mặc định) — nút "Tất cả" trong dải chọn nguồn bên dưới biểu đồ xu hướng.
  const [sourceFilter, setSourceFilter] = useState<string>("all");

  // Tách thành callback (thay vì gọi thẳng trong effect) để dùng lại được cho usePolling bên dưới —
  // scheduler chạy nền có thể tạo pain point mới/đổi post_count-severity_avg bất cứ lúc nào.
  const loadPainPoints = useCallback(() => {
    api.get<PainPointSummary[]>(`/topics/${id}/pain-points`).then((pps) => setPainPoints(sortPainPoints(pps)));
  }, [id]);

  useEffect(() => {
    // Reset bộ lọc nguồn về "Tất cả" mỗi khi CHUYỂN SANG topic khác — component này không unmount
    // khi điều hướng giữa 2 topic cùng route pattern /topics/[id] (Next.js tái dùng lại instance),
    // nên sourceFilter (useState) KHÔNG tự về "all" nếu không reset tay ở đây. Thiếu dòng này là lý
    // do topic B trống trơn sau khi đã lọc theo 1 nguồn cụ thể ở topic A rồi mới chuyển qua B — nguồn
    // đó có thể không tồn tại/không có dữ liệu ở topic B, khiến summary rỗng dù topic B thừa dữ liệu.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset bộ lọc theo id đổi, standard pattern
    setSourceFilter("all");
    api.get<Topic>(`/topics/${id}`).then(setTopic);
    loadPainPoints();
    // Tin bên thứ ba (qua NewsApifyCollector) — chỉ để xem, không tham gia đối chiếu/suy luận AI
    // (xem load_topic_documents loại trừ category="news"). Im lặng bỏ qua nếu lỗi/chưa có nguồn tin
    // tức nào — không phải phần cốt lõi của trang.
    api
      .get<OfficialDocument[]>(`/topics/${id}/official-documents?category=news&limit=5`)
      .then(setNewsArticles)
      .catch(() => {});
  }, [id, loadPainPoints]);

  // Tương tự — tách thành callback trả về Promise (KHÔNG tự setSummary bên trong) để effect bên
  // dưới vẫn giữ nguyên cơ chế cancelled-guard, còn usePolling gọi thẳng .then(setSummary) không
  // cần guard đó (poll cách nhau 30s, không có nguy cơ response cũ đè response mới như đổi filter
  // liên tục).
  const fetchSummary = useCallback(() => {
    const query = sourceFilter === "all" ? "" : `?source_type=${encodeURIComponent(sourceFilter)}`;
    return api.get<DashboardSummary>(`/topics/${id}/dashboard${query}`);
  }, [id, sourceFilter]);

  // Tách riêng khỏi effect trên — gọi lại MỖI KHI đổi nguồn chọn (xem dải nút bên dưới biểu đồ xu
  // hướng), không cần tải lại topic/pain point/bài báo (không đổi theo nguồn). Đổi topic (id) cũng
  // kích hoạt lại effect này CÙNG LÚC với effect trên vừa reset sourceFilter về "all" — 2 lệnh gọi
  // dashboard có thể chồng nhau (1 lần với filter CŨ dính lại từ topic trước, 1 lần với "all" mới
  // reset). cancelled guard: bỏ qua kết quả nếu effect đã bị huỷ (id/sourceFilter đổi tiếp trước
  // khi request này kịp trả lời) — tránh trường hợp response CŨ về SAU đè lên response ĐÚNG mới hơn.
  useEffect(() => {
    let cancelled = false;
    fetchSummary().then((data) => {
      if (!cancelled) setSummary(data);
    });
    return () => {
      cancelled = true;
    };
  }, [fetchSummary]);

  // Scheduler chạy nền liên tục phân tích thêm phản hồi — tự làm mới số liệu mỗi 30s (analyzed_
  // posts_count, pending_analysis_count...) và danh sách pain point mà không cần tải lại trang.
  usePolling(() => fetchSummary().then(setSummary), TOPIC_DASHBOARD_POLL_INTERVAL_MS);
  usePolling(loadPainPoints, TOPIC_DASHBOARD_POLL_INTERVAL_MS);

  if (!topic || !summary) return <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>;

  const pct = (part: number, whole: number) => (whole > 0 ? Math.round((part / whole) * 100) : 0);
  const analyzedPct = pct(summary.analyzed_posts_count, summary.total_posts_count);
  const negativePct = pct(summary.negative_posts_count, summary.analyzed_posts_count);

  function onPainPointUpdated(updated: PainPointSummary) {
    setPainPoints((prev) => (prev ? sortPainPoints(prev.map((pp) => (pp.id === updated.id ? updated : pp))) : prev));
  }

  return (
    <div>
      <Topbar
        title={topic.name}
        cta={
          <div className="flex flex-wrap items-center gap-2">
            <Link href={`/topics/${id}/facebook`}>
              <Button variant="secondary">
                <FacebookLogo size={15} /> Luồng Facebook
              </Button>
            </Link>
            <Link href={`/topics/${id}/tiktok`}>
              <Button variant="secondary">
                <TiktokLogo size={15} /> Luồng TikTok
              </Button>
            </Link>
            <Link href={`/topics/${id}/reference-docs`}>
              <Button variant="secondary">
                <Files size={15} /> Nguồn đối chiếu
              </Button>
            </Link>
            <Link href={`/topics/${id}/news`}>
              <Button variant="secondary">
                <Newspaper size={15} /> Bài báo
              </Button>
            </Link>
            <Link href={`/topics/${id}/members`}>
              <Button variant="secondary">
                <Users size={15} /> Thành viên
              </Button>
            </Link>
            {topic.is_owner && (
              <Link href={`/topics/${id}/edit`}>
                <Button variant="secondary">Chỉnh sửa</Button>
              </Link>
            )}
          </div>
        }
      />

      <div className="pt-6">
        <Link href="/topics" className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]">
          ← Chủ đề
        </Link>

        <div className="mt-4 mb-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatTile
            label="Tổng số phản hồi"
            value={summary.total_posts_count}
            hint="đã thu thập từ tất cả nguồn"
            href={`/topics/${id}/posts?filter=all`}
          />
          <StatTile
            label="Đã phân tích"
            value={summary.analyzed_posts_count}
            hint={`${analyzedPct}% trên tổng ${summary.total_posts_count}`}
            tone="brand"
            href={`/topics/${id}/posts?filter=analyzed`}
          />
          <StatTile
            label="Phản hồi tiêu cực"
            value={summary.negative_posts_count}
            hint={`${negativePct}% trên ${summary.analyzed_posts_count} đã phân tích`}
            tone="danger"
            href={`/topics/${id}/posts?filter=negative`}
          />
        </div>

        {summary.pending_analysis_count > 0 && (
          <div className="mb-6 flex gap-2.5 rounded-2xl border border-[var(--color-amber-glow)]/25 bg-[var(--color-amber-glow)]/8 px-4 py-3">
            <Hourglass size={15} className="mt-0.5 shrink-0 text-[var(--color-amber-glow)]" />
            <p className="text-[12.5px] leading-5 text-[var(--color-ink-2)]">
              Còn <span className="font-semibold">{summary.pending_analysis_count}</span> phản hồi đang chờ phân tích —
              hệ thống xử lý dần theo giới hạn tốc độ của AI, ưu tiên phản hồi mới nhất trước. Mọi số liệu trên trang này
              chỉ tính trên <span className="font-semibold">{summary.analyzed_posts_count}</span> phản hồi đã phân tích
              xong và sẽ tăng dần theo thời gian.
            </p>
          </div>
        )}

        {(summary.overdue_count > 0 || summary.due_soon_count > 0) && (
          <div className="card-soft mb-6 flex flex-wrap items-center gap-4 px-4 py-3">
            {summary.overdue_count > 0 && (
              <span className="flex items-center gap-2 text-[13px] text-[var(--color-rose)]">
                <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-[var(--color-rose)]/10 px-1.5 text-xs font-bold tabular-nums">
                  {summary.overdue_count}
                </span>
                case quá hạn xử lý
              </span>
            )}
            {summary.due_soon_count > 0 && (
              <span className="flex items-center gap-2 text-[13px] text-[var(--color-amber-glow)]">
                <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-[var(--color-amber-glow)]/10 px-1.5 text-xs font-bold tabular-nums">
                  {summary.due_soon_count}
                </span>
                case sắp đến hạn (trong 24h)
              </span>
            )}
          </div>
        )}

        <Card className="mb-6">
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>Xu hướng phản hồi (30 ngày)</CardTitle>
            {Object.keys(summary.source_breakdown).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setSourceFilter("all")}
                  aria-pressed={sourceFilter === "all"}
                  className={`rounded-full border px-3 py-1 text-[11.5px] font-medium transition-colors ${
                    sourceFilter === "all"
                      ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                      : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
                  }`}
                >
                  Tất cả
                </button>
                {Object.entries(summary.source_breakdown)
                  .sort(([, a], [, b]) => b - a)
                  .map(([type]) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setSourceFilter(type)}
                      aria-pressed={sourceFilter === type}
                      className={`rounded-full border px-3 py-1 text-[11.5px] font-medium transition-colors ${
                        sourceFilter === type
                          ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                          : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
                      }`}
                    >
                      {SOURCE_META[type] || type}
                    </button>
                  ))}
              </div>
            )}
          </CardHeader>
          <CardBody>
            <TrendChart
              data={summary.trend}
              onDrillDown={(date) => {
                const params = new URLSearchParams({ date });
                if (sourceFilter !== "all") params.set("source_type", sourceFilter);
                return api.get<HourlyTrendPoint[]>(`/topics/${id}/trend/hourly?${params.toString()}`);
              }}
            />
          </CardBody>
        </Card>

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader>
              <CardTitle>Cảm xúc</CardTitle>
              <p className="mt-0.5 text-xs text-[var(--color-muted)]">Đánh giá tổng quan để phát hiện sớm khủng hoảng truyền thông</p>
            </CardHeader>
            <CardBody>
              <SentimentBreakdown breakdown={summary.sentiment_breakdown} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Mức độ nghiêm trọng</CardTitle>
            </CardHeader>
            <CardBody>
              <SeverityBreakdown breakdown={summary.severity_breakdown} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Nguồn dữ liệu</CardTitle>
            </CardHeader>
            <CardBody>
              <SourceBreakdown breakdown={summary.source_breakdown} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Trạng thái xử lý case</CardTitle>
            </CardHeader>
            <CardBody>
              <LifecycleBreakdown breakdown={summary.lifecycle_breakdown} />
            </CardBody>
          </Card>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>So sánh mức độ tiêu cực giữa các nhóm chủ đề</CardTitle>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">
              Tỉ trọng phản hồi tiêu cực đóng góp bởi từng nhóm chủ đề (trong tối đa 9 nhóm cố định)
            </p>
          </CardHeader>
          <CardBody>
            <PartToWholePie
              data={Object.entries(summary.negative_by_group).map(([label, value]) => ({ label, value }))}
              valueLabel="Phản hồi tiêu cực"
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pain point</CardTitle>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">
              Nhóm chủ đề đạt từ {topic.alert_threshold} phản hồi trở lên mới tạo pain point
            </p>
          </CardHeader>
          <CardBody className="space-y-2">
            {painPoints && painPoints.length === 0 && (
              <p className="text-sm text-[var(--color-muted)]">
                Chưa có pain point nào — cần đủ số phản hồi cùng nhóm chủ đề vượt ngưỡng ({topic.alert_threshold}) mới
                được tạo.
              </p>
            )}
            {painPoints?.map((pp, index) => (
              <motion.div
                key={pp.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.05 }}
                whileHover={{ y: -2 }}
              >
              <Link
                href={`/topics/${id}/pain-points/${pp.id}`}
                style={{ borderLeftColor: pp.severity_avg !== null ? SEVERITY_ACCENT_COLOR[severityBucket(pp.severity_avg)] : "var(--color-line)" }}
                className="block rounded-2xl border border-[var(--color-line)] border-l-[3px] px-4 py-3 shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-[border-color,box-shadow,background-color] duration-300 hover:border-[var(--color-bone)] hover:bg-[var(--color-cream-2)]/40 hover:shadow-[0_14px_32px_rgba(11,18,32,0.09)]"
              >
                <div className="mb-1.5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                  <span className="flex min-w-0 items-center gap-1.5 font-semibold text-[var(--color-ink)]">
                    <PriorityToggle painPoint={pp} onUpdated={onPainPointUpdated} />
                    {pp.title}
                  </span>
                  <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
                    <SlaBadge dueAt={pp.due_at} isBreached={pp.is_breached} lifecycleStatus={pp.lifecycle_status} />
                    <LifecycleBadge status={pp.lifecycle_status} />
                    <TrendBadge trend={pp.trend} />
                    <ReferenceBadge status={pp.reference_status} />
                  </div>
                </div>
                {pp.description && <p className="mb-2 text-sm leading-relaxed text-[var(--color-muted)]">{pp.description}</p>}
                <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                  <span>
                    <span className="font-semibold tabular-nums text-[var(--color-ink-2)]">{pp.post_count}</span> phản hồi
                  </span>
                  {pp.severity_avg !== null && (
                    <span>
                      Mức độ TB:{" "}
                      <span className="font-semibold tabular-nums text-[var(--color-ink-2)]">{pp.severity_avg.toFixed(2)}</span>
                    </span>
                  )}
                  {pp.assigned_user && (
                    <span>
                      Phụ trách:{" "}
                      <span className="font-medium text-[var(--color-ink-2)]">
                        {pp.assigned_user.full_name || pp.assigned_user.email}
                      </span>
                      {pp.department && <span className="text-[var(--color-muted)]"> · {pp.department}</span>}
                    </span>
                  )}
                  <span className="ml-auto text-[var(--color-brand-600)]">Xem chi tiết →</span>
                </div>
              </Link>
              </motion.div>
            ))}
          </CardBody>
        </Card>

        {newsArticles.length > 0 && (
          <Card className="mt-6">
            <CardHeader className="flex items-center justify-between">
              <div>
                <CardTitle>Bài báo liên quan</CardTitle>
                <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                  Tin bên thứ ba nhắc tới chủ đề này — chỉ để tham khảo, không tham gia phân tích AI.
                </p>
              </div>
              <Link href={`/topics/${id}/news`} className="shrink-0 text-xs font-medium text-[var(--color-brand-600)] hover:underline">
                Xem tất cả →
              </Link>
            </CardHeader>
            <CardBody className="space-y-2">
              {newsArticles.map((doc, index) => (
                <motion.a
                  key={doc.id}
                  href={doc.url}
                  target="_blank"
                  rel="noreferrer"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.05 }}
                  whileHover={{ y: -2 }}
                  style={{ borderLeftColor: doc.sentiment ? SENTIMENT_ACCENT_COLOR[doc.sentiment] : "var(--color-line)" }}
                  className="flex items-start gap-3 rounded-2xl border border-[var(--color-line)] border-l-[3px] px-4 py-3 shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-[border-color,box-shadow,background-color] duration-300 hover:border-[var(--color-bone)] hover:bg-[var(--color-cream-2)]/40 hover:shadow-[0_10px_24px_rgba(11,18,32,0.08)]"
                >
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--color-cream-2)] text-[var(--color-brand-700)]">
                    <Newspaper size={14} weight="bold" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--color-ink)]">{doc.title}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {doc.sentiment && <SentimentBadge sentiment={doc.sentiment} />}
                      {doc.published_at && (
                        <span className="text-xs text-[var(--color-muted)]">
                          {new Date(doc.published_at).toLocaleDateString("vi-VN")}
                        </span>
                      )}
                    </div>
                  </div>
                </motion.a>
              ))}
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
