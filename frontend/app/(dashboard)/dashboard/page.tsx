"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Database, Heartbeat, MagnifyingGlass, ShieldCheck } from "@phosphor-icons/react/dist/ssr";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { DashboardSummary, HourlyTrendPoint, PainPointSummary, Topic, TrendPoint } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatTile } from "@/components/dashboard/StatTile";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { SeverityBadge, TrendBadge, LifecycleBadge, severityBucket, SEVERITY_ACCENT_COLOR } from "@/components/ui/Badges";
import { sortPainPoints } from "@/lib/painPointSort";
import { Topbar } from "@/components/layout/Topbar";

type PainPointRow = PainPointSummary & { topicId: string; topicName: string };

const ABOUT_STEPS = [
  {
    Icon: Database,
    title: "Thu thập tự động",
    body: "Theo dõi liên tục đánh giá từ Google Play, App Store và website ngân hàng — không cần thao tác thủ công.",
  },
  {
    Icon: MagnifyingGlass,
    title: "Phân tích bằng AI",
    body: "Phân loại chủ đề, chấm mức độ nghiêm trọng, đối chiếu với quy định NHNN và chính sách chính thức của ngân hàng.",
  },
  {
    Icon: Heartbeat,
    title: "Gom thành pain point",
    body: "Khi một nhóm phản hồi cùng vấn đề vượt ngưỡng cảnh báo, hệ thống tự động tạo case theo dõi kèm xu hướng.",
  },
  {
    Icon: ShieldCheck,
    title: "Xử lý kịp thời",
    body: "Giao việc, theo dõi hạn xử lý (SLA) theo mức độ nghiêm trọng, nhận thông báo ngay khi có diễn biến mới.",
  },
];

// Scheduler chạy nền liên tục phân tích thêm phản hồi/tạo pain point mới — làm mới mỗi 30s để số
// liệu tổng quan tự "nhảy số" mà không cần tải lại trang (xem lib/usePolling.ts).
const DASHBOARD_POLL_INTERVAL_MS = 30_000;

export default function OverviewDashboardPage() {
  const { user } = useAuth();
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [summaries, setSummaries] = useState<Map<string, DashboardSummary>>(new Map());
  const [topPainPoints, setTopPainPoints] = useState<PainPointRow[]>([]);

  const load = useCallback(async () => {
    const all = await api.get<Topic[]>("/topics");
    setTopics(all);
    const active = all.filter((t) => t.status === "active");
    const entries = await Promise.all(
      active.map(async (topic) => {
        const summary = await api.get<DashboardSummary>(`/topics/${topic.id}/dashboard`).catch(() => null);
        return [topic, summary] as const;
      }),
    );
    const map = new Map<string, DashboardSummary>();
    const rows: PainPointRow[] = [];
    for (const [topic, summary] of entries) {
      if (!summary) continue;
      map.set(topic.id, summary);
      for (const pp of summary.top_pain_points) {
        rows.push({ ...pp, topicId: topic.id, topicName: topic.name });
      }
    }
    setSummaries(map);
    setTopPainPoints(
      sortPainPoints(
        rows.filter(
          (pp) => pp.lifecycle_status !== "resolved" && pp.lifecycle_status !== "duplicate" && pp.lifecycle_status !== "ignored",
        ),
      ).slice(0, 5),
    );
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount, standard pattern
    load();
  }, [load]);

  usePolling(load, DASHBOARD_POLL_INTERVAL_MS);

  const loaded = topics !== null;
  const totalPosts = Array.from(summaries.values()).reduce((sum, s) => sum + s.total_posts_count, 0);
  const totalNegative = Array.from(summaries.values()).reduce((sum, s) => sum + s.negative_posts_count, 0);
  const totalOverdue = Array.from(summaries.values()).reduce((sum, s) => sum + s.overdue_count, 0);
  const activeTopicCount = topics?.filter((t) => t.status === "active").length ?? 0;

  // Gộp trend theo NGÀY trên mọi chủ đề (cộng dồn count/negative_count cùng ngày) — tái dùng
  // nguyên TrendChart, không cần component riêng cho biểu đồ tổng quan.
  const combinedTrend: TrendPoint[] = (() => {
    const byDate = new Map<string, TrendPoint>();
    for (const summary of summaries.values()) {
      for (const point of summary.trend) {
        const existing = byDate.get(point.date);
        if (existing) {
          existing.count += point.count;
          existing.negative_count += point.negative_count;
        } else {
          byDate.set(point.date, { ...point });
        }
      }
    }
    return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
  })();

  // Gộp trend theo GIỜ trên mọi chủ đề đang active cho đúng 1 ngày — cùng cách cộng dồn với
  // combinedTrend ở trên (theo ngày), chỉ khác gọi endpoint /trend/hourly cho TỪNG topic rồi merge
  // client-side, vì backend chưa có endpoint "tổng hợp mọi topic" sẵn (dashboard tổng vốn đã hoạt
  // động theo cách gọi N lần rồi cộng dồn ở FE, xem load() phía trên).
  async function loadCombinedHourlyTrend(date: string): Promise<HourlyTrendPoint[]> {
    const activeTopicIds = Array.from(summaries.keys());
    const perTopic = await Promise.all(
      activeTopicIds.map((topicId) =>
        api.get<HourlyTrendPoint[]>(`/topics/${topicId}/trend/hourly?date=${date}`).catch(() => []),
      ),
    );
    const byHour = new Map<string, HourlyTrendPoint>();
    for (const points of perTopic) {
      for (const point of points) {
        const existing = byHour.get(point.hour);
        if (existing) {
          existing.count += point.count;
          existing.negative_count += point.negative_count;
        } else {
          byHour.set(point.hour, { ...point });
        }
      }
    }
    return Array.from(byHour.values()).sort((a, b) => a.hour.localeCompare(b.hour));
  }

  return (
    <div>
      <Topbar title="Trang chủ" subtitle="Tổng quan tình hình phản hồi khách hàng trên mọi chủ đề đang theo dõi." />

      <div className="pt-6">
        <Card className="mb-6 p-6">
          <p className="eyebrow">Giới thiệu hệ thống</p>
          <p className="display-xl mt-1 text-[18px] font-semibold text-[var(--color-ink)]">
            VigiBank theo dõi và phân tích phản hồi khách hàng theo thời gian thực
          </p>
          <p className="mt-2 max-w-[70ch] text-[13.5px] leading-relaxed text-[var(--color-muted)]">
            Mỗi ngân hàng là một &quot;chủ đề&quot; (workspace) riêng biệt. Hệ thống tự động thu thập đánh giá, dùng AI phân
            tích và gom thành các &quot;pain point&quot; — vấn đề đang được nhiều khách hàng cùng phản ánh — để đội ngũ vận
            hành phát hiện và xử lý sớm trước khi lan thành khủng hoảng truyền thông.
          </p>
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {ABOUT_STEPS.map(({ Icon, title, body }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: i * 0.06 }}
                whileHover={{ y: -2 }}
                className="rounded-2xl border border-[var(--color-line)] p-3.5 shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-shadow duration-300 hover:shadow-[0_12px_28px_rgba(11,18,32,0.08)]"
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--color-cream-2)] text-[var(--color-brand-700)]">
                    <Icon size={14} weight="bold" />
                  </span>
                  <span className="font-mono text-[11px] font-medium text-[var(--color-muted)] tabular-nums">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                <p className="mt-2.5 text-[13px] font-semibold text-[var(--color-ink)]">{title}</p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--color-muted)]">{body}</p>
              </motion.div>
            ))}
          </div>
        </Card>

        {!loaded ? (
          <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>
        ) : activeTopicCount === 0 ? (
          <Card>
            <CardBody className="mx-auto max-w-sm p-8 text-center">
              <p className="text-[14px] font-semibold text-[var(--color-ink)]">Chưa có chủ đề nào</p>
              <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">
                {user?.is_platform_admin
                  ? "Tạo chủ đề đầu tiên để bắt đầu theo dõi phản hồi khách hàng."
                  : "Liên hệ quản trị viên nền tảng để được cấp chủ đề làm việc."}
              </p>
              {user?.is_platform_admin && (
                <Link href="/admin" className="mt-4 inline-block">
                  <Button>+ Chủ đề mới</Button>
                </Link>
              )}
            </CardBody>
          </Card>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
              <StatTile label="Chủ đề đang theo dõi" value={activeTopicCount} href="/topics" />
              <StatTile label="Tổng phản hồi" value={totalPosts.toLocaleString("vi-VN")} tone="brand" />
              <StatTile
                label="Phản hồi tiêu cực"
                value={totalNegative.toLocaleString("vi-VN")}
                hint={totalPosts > 0 ? `${Math.round((totalNegative / totalPosts) * 100)}% trên tổng` : undefined}
                tone="danger"
              />
              <StatTile
                label="Case quá hạn xử lý"
                value={totalOverdue}
                href="/pain-points"
                tone={totalOverdue > 0 ? "danger" : "neutral"}
              />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
              <Card>
                <CardHeader>
                  <CardTitle>Xu hướng phản hồi (30 ngày, mọi chủ đề)</CardTitle>
                </CardHeader>
                <CardBody>
                  {combinedTrend.length === 0 ? (
                    <p className="text-sm text-[var(--color-muted)]">Chưa có dữ liệu.</p>
                  ) : (
                    <TrendChart data={combinedTrend} onDrillDown={loadCombinedHourlyTrend} />
                  )}
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Pain point đáng chú ý</CardTitle>
                </CardHeader>
                <CardBody className="space-y-2">
                  {topPainPoints.length === 0 && <p className="text-sm text-[var(--color-muted)]">Chưa có pain point nào cần xử lý.</p>}
                  {topPainPoints.map((pp, index) => (
                    <motion.div
                      key={pp.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.05 }}
                      whileHover={{ y: -2 }}
                    >
                      <Link
                        href={`/topics/${pp.topicId}/pain-points/${pp.id}`}
                        style={{ borderLeftColor: pp.severity_avg !== null ? SEVERITY_ACCENT_COLOR[severityBucket(pp.severity_avg)] : "var(--color-line)" }}
                        className="block rounded-xl border border-[var(--color-line)] border-l-[3px] px-3 py-2.5 shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-[border-color,box-shadow] duration-300 hover:border-[var(--color-bone)] hover:shadow-[0_10px_24px_rgba(11,18,32,0.08)]"
                      >
                        <p className="eyebrow">{pp.topicName}</p>
                        <p className="mt-0.5 text-[13px] font-medium text-[var(--color-ink)]">{pp.title}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <SeverityBadge score={pp.severity_avg} />
                          <TrendBadge trend={pp.trend} />
                          <LifecycleBadge status={pp.lifecycle_status} />
                        </div>
                      </Link>
                    </motion.div>
                  ))}
                </CardBody>
              </Card>
            </div>

            <Card className="flex flex-col items-start gap-4 p-6 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="eyebrow">Tiếp theo</p>
                <p className="display-xl mt-1 text-[16px] font-semibold text-[var(--color-ink)]">Xem toàn bộ pain point cần xử lý</p>
                <p className="mt-1 text-[13px] text-[var(--color-muted)]">Lọc, giao việc và theo dõi hạn xử lý cho từng case trên mọi chủ đề.</p>
              </div>
              <Link href="/pain-points">
                <Button>Xem Pain Point →</Button>
              </Link>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
