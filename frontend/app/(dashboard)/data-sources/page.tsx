"use client";

import { useEffect, useState } from "react";
import { CheckCircle, XCircle } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { DashboardSummary, Source, Topic } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Topbar } from "@/components/layout/Topbar";

const SOURCE_LABEL: Record<string, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn",
  bank_website: "Website ngân hàng",
  facebook: "Facebook",
  news_article: "Bài báo/tin tức",
  tiktok: "TikTok",
};

type Row = {
  topicName: string;
  source: Source;
  postCount: number;
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "Chưa thu thập lần nào";
  return new Date(iso).toLocaleString("vi-VN", { dateStyle: "medium", timeStyle: "short" });
}

export default function DataSourcesPage() {
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    api.get<Topic[]>("/topics").then(async (topics) => {
      const active = topics.filter((t) => t.status === "active");
      const perTopic = await Promise.all(
        active.map(async (topic) => {
          const summary = await api.get<DashboardSummary>(`/topics/${topic.id}/dashboard`).catch(() => null);
          return topic.sources.map((source) => ({
            topicName: topic.name,
            source,
            postCount: summary?.source_breakdown[source.type] ?? 0,
          }));
        }),
      );
      setRows(perTopic.flat());
    });
  }, []);

  const totalSources = rows?.length ?? 0;
  const activeSources = rows?.filter((r) => r.source.is_active).length ?? 0;
  const totalPosts = rows?.reduce((sum, r) => sum + r.postCount, 0) ?? 0;

  return (
    <div>
      <Topbar title="Nguồn dữ liệu" subtitle="Tổng quan các nguồn thu thập phản hồi trên mọi chủ đề." />

      <div className="pt-6">
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="p-5">
            <p className="text-[11px] font-medium tracking-[0.1em] text-[var(--color-muted)] uppercase">Tổng số nguồn</p>
            <p className="display-xl mt-1.5 text-[28px] font-semibold text-[var(--color-ink)]">{totalSources}</p>
          </Card>
          <Card className="p-5">
            <p className="text-[11px] font-medium tracking-[0.1em] text-[var(--color-muted)] uppercase">Đang hoạt động</p>
            <p className="display-xl mt-1.5 text-[28px] font-semibold text-[var(--color-leaf)]">{activeSources}</p>
          </Card>
          <Card className="p-5">
            <p className="text-[11px] font-medium tracking-[0.1em] text-[var(--color-muted)] uppercase">Tổng bản ghi đã thu thập</p>
            <p className="display-xl mt-1.5 text-[28px] font-semibold text-[var(--color-ink)]">{totalPosts.toLocaleString("vi-VN")}</p>
          </Card>
        </div>

        <div className="mb-6 rounded-2xl border border-dashed border-[var(--color-line)] p-4 text-[12.5px] text-[var(--color-muted)]">
          Hệ thống tự động thu thập phản hồi mới theo lịch chạy nền — chưa hỗ trợ đồng bộ thủ công. Thêm/tắt nguồn ở
          trang chỉnh sửa từng chủ đề.
        </div>

        <Card className="overflow-hidden">
          {rows === null ? (
            <CardBody>
              <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>
            </CardBody>
          ) : rows.length === 0 ? (
            <CardBody>
              <p className="text-sm text-[var(--color-muted)]">Chưa có nguồn dữ liệu nào.</p>
            </CardBody>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-[13px]">
                <thead>
                  <tr className="bg-[var(--color-cream-2)] text-[11px] tracking-[0.14em] text-[var(--color-muted)] uppercase">
                    <th className="px-5 py-3 text-left font-medium">Chủ đề</th>
                    <th className="px-5 py-3 text-left font-medium">Nguồn</th>
                    <th className="px-5 py-3 text-left font-medium">Trạng thái</th>
                    <th className="px-5 py-3 text-right font-medium">Số bản ghi (bài viết/phản hồi)</th>
                    <th className="px-5 py-3 text-right font-medium">Lần thu thập gần nhất</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.source.id} className="border-t border-[var(--color-line)]">
                      <td className="px-5 py-3 text-[var(--color-ink-2)]">{row.topicName}</td>
                      <td className="px-5 py-3 font-medium text-[var(--color-ink)]">{SOURCE_LABEL[row.source.type] || row.source.type}</td>
                      <td className="px-5 py-3">
                        {row.source.is_active ? (
                          <span className="inline-flex items-center gap-1.5 text-[var(--color-leaf)]">
                            <CheckCircle size={14} weight="fill" /> Đang bật
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-[var(--color-muted)]">
                            <XCircle size={14} /> Đã tắt
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-[var(--color-ink-2)]">{row.postCount.toLocaleString("vi-VN")}</td>
                      <td className="px-5 py-3 text-right text-[var(--color-muted)]">{formatDateTime(row.source.last_crawled_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
