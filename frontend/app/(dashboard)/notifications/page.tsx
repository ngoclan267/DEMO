"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";
import { api, ApiError } from "@/lib/api";
import type { AppNotification, NotificationType } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SEVERITY_OPTIONS, severityBucket, SEVERITY_ACCENT_COLOR } from "@/components/ui/Badges";
import { Topbar } from "@/components/layout/Topbar";

const TYPE_ICON: Record<NotificationType, string> = {
  threshold_alert: "🔔",
  assigned: "📌",
  resolved: "✅",
  daily_digest: "📰",
  department_assigned: "🏢",
  contact_request: "📩",
};

/** contact_request không gắn topic nào (doanh nghiệp gửi form CHƯA có tài khoản) — về thẳng trang
 * quản trị yêu cầu liên hệ, khác mọi loại thông báo khác luôn dẫn về 1 topic/pain point cụ thể. */
function notificationHref(n: AppNotification): string {
  if (n.notification_type === "contact_request") return "/admin/contacts";
  return n.pain_point_id ? `/topics/${n.topic_id}/pain-points/${n.pain_point_id}` : `/topics/${n.topic_id}`;
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.round(hours / 24);
  return `${days} ngày trước`;
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<AppNotification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");

  function load() {
    setError(null);
    api
      .get<AppNotification[]>("/notifications?limit=100")
      .then(setNotifications)
      .catch(() => setError("Không tải được danh sách thông báo."));
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount, standard pattern
  useEffect(load, []);

  async function markRead(n: AppNotification) {
    if (n.read_status === "read") return;
    // Không chặn điều hướng nếu lỗi — người dùng vẫn đang bấm để MỞ thông báo, đánh dấu đã đọc chỉ
    // là phụ; thất bại thì giữ nguyên trạng thái unread, thử lại ở lần bấm sau.
    try {
      await api.patch(`/notifications/${n.id}/read`);
      load();
      window.dispatchEvent(new Event("notifications-changed"));
    } catch {
      // bỏ qua — xem chú thích ở trên
    }
  }

  async function markAllRead() {
    setMarkingAll(true);
    try {
      await api.patch("/notifications/read-all");
      load();
      // Sidebar/Topbar giữ unreadCount riêng, chỉ tự làm mới khi đổi route — báo ngay để badge cập
      // nhật mà không cần người dùng điều hướng đi rồi quay lại.
      window.dispatchEvent(new Event("notifications-changed"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đánh dấu đã đọc được, thử lại sau.");
    } finally {
      setMarkingAll(false);
    }
  }

  const hasUnread = notifications?.some((n) => n.read_status === "unread") ?? false;

  // Lọc ở client — danh sách thông báo vốn đã giới hạn 100 gần nhất trong 1 lần gọi API, không
  // cần thêm endpoint tìm kiếm riêng.
  const filtered = useMemo(() => {
    if (!notifications) return null;
    return notifications.filter((n) => {
      if (search && !n.message?.toLowerCase().includes(search.toLowerCase())) return false;
      if (severityFilter) {
        if (n.severity === null) return false;
        if (severityBucket(n.severity) !== severityFilter) return false;
      }
      return true;
    });
  }, [notifications, search, severityFilter]);

  return (
    <div>
      <Topbar
        title="Thông báo"
        cta={
          hasUnread ? (
            <Button variant="secondary" loading={markingAll} onClick={markAllRead}>
              Đánh dấu đã đọc tất cả
            </Button>
          ) : undefined
        }
      />

      <div className="pt-6">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="relative flex-1 sm:max-w-xs">
            <MagnifyingGlass size={15} className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-[var(--color-muted)]" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm trong nội dung thông báo..."
              className="!h-10 !rounded-full !pl-9"
            />
          </div>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="h-10 rounded-full border border-[var(--color-line)] bg-white px-3.5 text-[13px] text-[var(--color-ink)] outline-none focus:border-[var(--color-brand-500)]"
          >
            <option value="">Mọi mức độ</option>
            {SEVERITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {filtered && (
            <span className="ml-auto text-[12.5px] text-[var(--color-muted)]">{filtered.length} thông báo</span>
          )}
        </div>

        {error && <p className="mb-3 text-sm text-[var(--color-rose)]">{error}</p>}

        {notifications === null && !error && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {filtered && filtered.length === 0 && (
          <Card>
            <CardBody className="p-8 text-center text-sm text-[var(--color-muted)]">
              {notifications && notifications.length === 0 ? "Chưa có thông báo nào." : "Không có thông báo nào khớp bộ lọc."}
            </CardBody>
          </Card>
        )}

        <div className="space-y-2">
          <AnimatePresence initial={false}>
            {filtered?.map((n, index) => (
              <motion.div
                key={n.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.03 }}
                whileHover={{ y: -2 }}
              >
                <Link
                  href={notificationHref(n)}
                  onClick={() => markRead(n)}
                  style={{ borderLeftColor: n.severity !== null ? SEVERITY_ACCENT_COLOR[severityBucket(n.severity)] : "var(--color-line)" }}
                  className={`card-soft flex items-start gap-3 border-l-[3px] p-4 shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-[background-color,box-shadow] duration-300 hover:shadow-[0_10px_24px_rgba(11,18,32,0.08)] ${
                    n.read_status === "unread" ? "hover:bg-[var(--color-cream-2)]/50" : "opacity-80 hover:opacity-100"
                  }`}
                >
                  <span aria-hidden className="mt-0.5 shrink-0 text-base leading-none">
                    {TYPE_ICON[n.notification_type]}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={n.read_status === "unread" ? "text-sm font-medium text-[var(--color-ink)]" : "text-sm text-[var(--color-ink-2)]"}>
                      {n.message}
                    </p>
                    <p className="mt-1 text-xs text-[var(--color-muted)]">{timeAgo(n.sent_at)}</p>
                  </div>
                  {n.read_status === "unread" && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--color-brand-500)]" />}
                </Link>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
