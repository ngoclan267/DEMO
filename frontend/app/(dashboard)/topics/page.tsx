"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { BellSimple, BellSimpleSlash } from "@phosphor-icons/react/dist/ssr";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { DashboardSummary, Topic, TopicStatus } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { SeverityBadge, severityBucket, SEVERITY_ACCENT_COLOR } from "@/components/ui/Badges";
import { Sparkline } from "@/components/ui/Sparkline";
import { Topbar } from "@/components/layout/Topbar";

const SOURCE_LABEL: Record<string, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn",
  bank_website: "Website ngân hàng",
  facebook: "Facebook",
  tiktok: "TikTok",
};

const STATUS_FILTERS: { value: TopicStatus | "all"; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "active", label: "Đang chạy" },
  { value: "archived", label: "Đã lưu trữ" },
];

type TopicWithSummary = Topic & { summary: DashboardSummary | null };

/** Mức nghiêm trọng cao nhất trong các pain point ĐANG MỞ — đại diện cho "độ nóng" của topic trên
 * thẻ danh sách. top_pain_points chỉ là top 5 nhưng đã đủ đại diện cho mục đích hiển thị nhanh này. */
function highestOpenSeverity(summary: DashboardSummary | null): number | null {
  if (!summary) return null;
  const open = summary.top_pain_points.filter((p) => p.lifecycle_status !== "resolved" && p.lifecycle_status !== "duplicate" && p.lifecycle_status !== "ignored");
  const scores = open.map((p) => p.severity_avg).filter((s): s is number => s !== null);
  return scores.length > 0 ? Math.max(...scores) : null;
}

export default function TopicsPage() {
  const { user } = useAuth();
  const [topics, setTopics] = useState<TopicWithSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<TopicStatus | "all">("all");

  useEffect(() => {
    api
      .get<Topic[]>("/topics")
      .then(async (all) => {
        const withSummary = await Promise.all(
          all.map(async (topic) => {
            const summary = await api.get<DashboardSummary>(`/topics/${topic.id}/dashboard`).catch(() => null);
            return { ...topic, summary };
          }),
        );
        setTopics(withSummary);
      })
      .catch(() => setError("Không tải được danh sách chủ đề"));
  }, []);

  async function toggleMute(topic: TopicWithSummary, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const nextEnabled = !topic.notify_enabled;
    try {
      await api.patch(`/topics/${topic.id}`, { notify_enabled: nextEnabled });
      setTopics((prev) => prev?.map((t) => (t.id === topic.id ? { ...t, notify_enabled: nextEnabled } : t)) ?? prev);
      toast.success(nextEnabled ? "Đã bật thông báo" : "Đã tắt thông báo");
    } catch {
      toast.error("Không đổi được trạng thái thông báo");
    }
  }

  const filtered = topics?.filter((t) => statusFilter === "all" || t.status === statusFilter) ?? null;

  return (
    <div>
      <Topbar
        title="Chủ đề"
        subtitle="Mỗi chủ đề theo dõi một app/thương hiệu riêng, có dữ liệu và pain point riêng."
        cta={
          user?.is_platform_admin ? (
            <Link href="/admin">
              <Button>+ Chủ đề mới</Button>
            </Link>
          ) : undefined
        }
      />

      <div className="pt-6">
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={
                statusFilter === f.value
                  ? "h-8 rounded-full bg-[var(--color-ink)] px-3.5 text-[12.5px] font-medium text-white"
                  : "h-8 rounded-full border border-[var(--color-line)] bg-white px-3.5 text-[12.5px] font-medium text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
              }
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p className="text-sm text-[var(--color-rose)]">{error}</p>}

        {topics === null && !error && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {filtered && filtered.length === 0 && (
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
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered?.map((topic, index) => {
            const severity = highestOpenSeverity(topic.summary);
            const sparklineData = topic.summary?.trend.map((t) => t.count) ?? [];
            return (
              <motion.div
                key={topic.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: Math.min(index, 8) * 0.05 }}
              >
              <Link href={`/topics/${topic.id}`}>
                <Card
                  style={{ borderLeftColor: severity !== null ? SEVERITY_ACCENT_COLOR[severityBucket(severity)] : "var(--color-line)" }}
                  className="relative flex h-full flex-col border-l-[3px] p-5 transition duration-300 hover:-translate-y-[1px] hover:shadow-[0_18px_50px_rgba(11,18,32,0.08)]"
                >
                  {topic.status === "archived" && (
                    <span className="absolute top-3 right-3 rounded-full bg-[var(--color-amber-glow)]/10 px-2 py-0.5 text-[10.5px] font-medium text-[var(--color-amber-glow)]">
                      Đã lưu trữ
                    </span>
                  )}
                  <div className="mb-2 flex items-start justify-between gap-2 pr-16">
                    <h2 className="display-xl text-[16px] font-semibold text-[var(--color-ink)]">{topic.name}</h2>
                  </div>
                  {severity !== null && (
                    <div className="mb-2">
                      <SeverityBadge score={severity} />
                    </div>
                  )}
                  <div className="mb-3 flex flex-wrap gap-1.5">
                    {topic.keywords.slice(0, 4).map((k) => (
                      <span key={k} className="rounded-full bg-[var(--color-cream-2)] px-2 py-0.5 font-mono text-[11px] text-[var(--color-ink-2)]">
                        {k}
                      </span>
                    ))}
                  </div>

                  <div className="mt-auto">
                    {sparklineData.length >= 2 && (
                      <Sparkline data={sparklineData} className="h-8 w-full" stroke="var(--color-brand-500)" />
                    )}
                    <div className="mt-3 flex flex-wrap gap-1">
                      {topic.sources.map((s) => (
                        <span key={s.id} className="chip">
                          {SOURCE_LABEL[s.type] || s.type}
                        </span>
                      ))}
                      {topic.sources.length === 0 && <span className="text-xs text-[var(--color-muted)]">Chưa có nguồn dữ liệu</span>}
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t border-[var(--color-line)] pt-3">
                      <span className="text-[12px] text-[var(--color-muted)]">Ngưỡng cảnh báo: {topic.alert_threshold}</span>
                      <button
                        onClick={(e) => toggleMute(topic, e)}
                        aria-label={topic.notify_enabled ? "Tắt thông báo" : "Bật thông báo"}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-ink)]"
                      >
                        {topic.notify_enabled ? <BellSimple size={15} /> : <BellSimpleSlash size={15} />}
                      </button>
                    </div>
                  </div>
                </Card>
              </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
