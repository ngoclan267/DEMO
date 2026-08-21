"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Envelope } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { AppNotification, Topic } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Topbar } from "@/components/layout/Topbar";

const CHANNEL_LABEL: Record<string, string> = {
  email: "Email",
  web: "Website",
  both: "Email + Website",
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", { dateStyle: "medium", timeStyle: "short" });
}

export default function ReportsPage() {
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [digests, setDigests] = useState<AppNotification[]>([]);

  useEffect(() => {
    Promise.all([
      api.get<Topic[]>("/topics"),
      api.get<AppNotification[]>("/notifications?limit=100"),
    ]).then(([allTopics, allNotifications]) => {
      setTopics(allTopics);
      setDigests(allNotifications.filter((n) => n.notification_type === "daily_digest"));
    });
  }, []);

  const enabledTopics = topics?.filter((t) => t.status === "active" && t.notify_enabled) ?? null;

  function lastDigestFor(topicId: string): AppNotification | null {
    const forTopic = digests.filter((d) => d.topic_id === topicId);
    if (forTopic.length === 0) return null;
    return forTopic.reduce((latest, d) => (d.sent_at > latest.sent_at ? d : latest));
  }

  return (
    <div>
      <Topbar title="Bản tin" subtitle="Tổng hợp tự động hàng ngày cho các chủ đề đang bật thông báo." />

      <div className="space-y-4 pt-6">
        {enabledTopics === null && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {enabledTopics && enabledTopics.length === 0 && (
          <Card>
            <CardBody className="mx-auto max-w-sm p-8 text-center">
              <p className="text-[14px] font-semibold text-[var(--color-ink)]">Chưa có chủ đề nào bật bản tin</p>
              <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">
                Bật &quot;Thông báo khi vượt ngưỡng&quot; ở trang chỉnh sửa chủ đề để nhận bản tin tổng hợp hàng ngày.
              </p>
            </CardBody>
          </Card>
        )}

        {enabledTopics?.map((topic, index) => {
          const last = lastDigestFor(topic.id);
          return (
            <motion.div
              key={topic.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.05 }}
              whileHover={{ y: -2 }}
            >
              <Card className="overflow-hidden shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-shadow duration-300 hover:shadow-[0_12px_28px_rgba(11,18,32,0.08)]">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle>{topic.name}</CardTitle>
                      <p className="mt-0.5 text-xs text-[var(--color-muted)]">Chạy tự động 1 lần/ngày, tổng hợp phản hồi 24h qua</p>
                    </div>
                    <span className="chip">
                      <Envelope size={13} /> {CHANNEL_LABEL[topic.notify_channel] || topic.notify_channel}
                    </span>
                  </div>
                </CardHeader>
                <CardBody>
                  {last ? (
                    <div>
                      <p className="text-xs text-[var(--color-muted)]">Bản tin gần nhất — {formatDateTime(last.sent_at)}</p>
                      <p className="mt-1.5 text-sm text-[var(--color-ink-2)]">{last.message}</p>
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-[var(--color-line)] p-4 text-[12.5px] text-[var(--color-muted)]">
                      Chưa có bản tin nào được gửi cho chủ đề này — bản tin chạy vào 7:00 sáng hàng ngày, chỉ tạo khi
                      có phản hồi mới trong 24h qua.
                    </div>
                  )}
                </CardBody>
              </Card>
            </motion.div>
          );
        })}

        <div className="rounded-2xl border border-dashed border-[var(--color-line)] p-4 text-[12.5px] text-[var(--color-muted)]">
          Muốn xem lại toàn bộ lịch sử bản tin (không chỉ lần gần nhất)? Xem tất cả ở trang{" "}
          <Link href="/notifications" className="text-[var(--color-brand-600)] hover:underline">
            Thông báo
          </Link>
          .
        </div>
      </div>
    </div>
  );
}
