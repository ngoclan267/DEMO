"use client";

import { useSyncExternalStore } from "react";
import clsx from "clsx";
import { CLOSED_LIFECYCLE_STATUSES, type LifecycleStatus } from "@/lib/types";

/** Không có nguồn dữ liệu ngoài nào thay đổi — chỉ cần phân biệt server/client, không cần subscribe. */
const noopSubscribe = () => () => {};

function computeLabel(dueAt: string, isBreached: boolean): string {
  const absHours = Math.abs(new Date(dueAt).getTime() - Date.now()) / 36e5;
  const amount = absHours >= 48 ? `${Math.round(absHours / 24)} ngày` : `${Math.max(1, Math.round(absHours))} giờ`;
  return isBreached ? `Quá hạn ${amount}` : `Còn ${amount}`;
}

/**
 * Chip hạn xử lý (đếm ngược / quá hạn bao lâu).
 *
 * Chuỗi hiển thị phụ thuộc thời điểm hiện tại, mà Next.js render 1 lần ở server rồi hydrate lại ở
 * client — hai lần cách nhau vài trăm ms sẽ ra chuỗi khác nhau và gây hydration mismatch. Dùng
 * useSyncExternalStore với snapshot phía server trả null: server render ra rỗng, client tính thật
 * sau khi hydrate. Đây là cách React khuyến nghị cho giá trị chỉ có ở client (thay vì đọc
 * Date.now() thẳng trong render hoặc setState trong effect).
 *
 * `isBreached` do server quyết định (xem src/sla.py) chứ không tự so ngày ở client — để toàn hệ
 * thống chỉ có MỘT định nghĩa "quá hạn".
 */
export function SlaBadge({
  dueAt,
  isBreached,
  lifecycleStatus,
}: {
  dueAt: string | null;
  isBreached: boolean;
  lifecycleStatus: LifecycleStatus;
}) {
  const label = useSyncExternalStore(
    noopSubscribe,
    () => (dueAt ? computeLabel(dueAt, isBreached) : null),
    () => null,
  );

  // Case đã đóng thì không còn đếm ngược — hiển thị hạn chỉ gây nhiễu.
  if (!dueAt || CLOSED_LIFECYCLE_STATUSES.includes(lifecycleStatus) || label === null) return null;

  const urgent = !isBreached && label.includes("giờ");
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        isBreached
          ? "bg-[var(--color-rose)]/10 text-[var(--color-rose)]"
          : urgent
            ? "bg-[var(--color-amber-glow)]/10 text-[var(--color-amber-glow)]"
            : "bg-[var(--color-cream-2)] text-[var(--color-muted)]",
      )}
    >
      {label}
    </span>
  );
}
