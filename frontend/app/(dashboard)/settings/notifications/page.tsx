"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { NotifyChannel, Topic } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { Topbar } from "@/components/layout/Topbar";

const CHANNEL_OPTIONS: { value: NotifyChannel; label: string }[] = [
  { value: "both", label: "Email + Website" },
  { value: "email", label: "Chỉ Email" },
  { value: "web", label: "Chỉ Website" },
];

const selectClass =
  "h-9 rounded-lg border border-[var(--color-line)] bg-white px-2.5 text-[12.5px] text-[var(--color-ink)] outline-none focus:border-[var(--color-brand-500)] disabled:cursor-not-allowed disabled:opacity-50";

export default function NotificationSettingsPage() {
  const [topics, setTopics] = useState<Topic[] | null>(null);

  useEffect(() => {
    api.get<Topic[]>("/topics").then(setTopics);
  }, []);

  async function updateTopic(topicId: string, patch: { notify_enabled?: boolean; notify_channel?: NotifyChannel }) {
    const previous = topics;
    setTopics((prev) => prev?.map((t) => (t.id === topicId ? { ...t, ...patch } : t)) ?? prev);
    try {
      await api.patch(`/topics/${topicId}`, patch);
      toast.success("Đã lưu");
    } catch {
      setTopics(previous);
      toast.error("Không lưu được, thử lại sau");
    }
  }

  return (
    <div>
      <Topbar title="Cài đặt thông báo" subtitle="Bật/tắt và chọn kênh nhận cảnh báo cho từng chủ đề." />

      <div className="pt-6">
        <Link href="/settings" className="text-sm text-[var(--color-muted)] hover:text-[var(--color-ink)]">
          ← Cài đặt
        </Link>

        <Card className="mt-4 overflow-hidden">
          {topics === null ? (
            <CardBody>
              <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>
            </CardBody>
          ) : topics.length === 0 ? (
            <CardBody>
              <p className="text-sm text-[var(--color-muted)]">Chưa có chủ đề nào.</p>
            </CardBody>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-[13px]">
                <thead>
                  <tr className="bg-[var(--color-cream-2)] text-[11px] tracking-[0.14em] text-[var(--color-muted)] uppercase">
                    <th className="px-5 py-3 text-left font-medium">Chủ đề</th>
                    <th className="px-5 py-3 text-left font-medium">Bật thông báo</th>
                    <th className="px-5 py-3 text-left font-medium">Kênh</th>
                  </tr>
                </thead>
                <tbody>
                  {topics.map((topic) => (
                    <tr key={topic.id} className="border-t border-[var(--color-line)]">
                      <td className="px-5 py-3.5 font-medium text-[var(--color-ink)]">{topic.name}</td>
                      <td className="px-5 py-3.5">
                        <ToggleSwitch
                          checked={topic.notify_enabled}
                          onChange={(checked) => updateTopic(topic.id, { notify_enabled: checked })}
                          label={`Bật thông báo cho ${topic.name}`}
                          disabled={!topic.is_owner}
                        />
                      </td>
                      <td className="px-5 py-3.5">
                        <select
                          className={selectClass}
                          value={topic.notify_channel}
                          disabled={!topic.notify_enabled || !topic.is_owner}
                          onChange={(e) => updateTopic(topic.id, { notify_channel: e.target.value as NotifyChannel })}
                        >
                          {CHANNEL_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <p className="mt-3 text-xs text-[var(--color-muted)]">
          Bao gồm cảnh báo vượt ngưỡng, giao việc, đã xử lý xong và bản tin tổng hợp hàng ngày. Chỉ chủ sở hữu chủ đề
          mới đổi được thiết lập này.
        </p>
      </div>
    </div>
  );
}
