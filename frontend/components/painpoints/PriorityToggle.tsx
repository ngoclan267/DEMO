"use client";

import { useState, type MouseEvent } from "react";
import { Star } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { PainPointSummary } from "@/lib/types";

/** Nút đánh dấu pain point này là CẤP THIẾT NHẤT với doanh nghiệp — ghi đè thứ hạng mặc định theo
 * severity_avg (xem PATCH /pain-points/{id}/lifecycle, PainPoint.is_priority trong
 * src/db/models.py). Dùng lại ở mọi nơi hiển thị pain point (danh sách theo topic, danh sách gộp
 * mọi topic, trang chi tiết). preventDefault/stopPropagation vì component này thường nằm TRONG 1
 * <Link> bọc cả thẻ pain point — bấm sao không được điều hướng sang trang khác. */
export function PriorityToggle({
  painPoint,
  onUpdated,
}: {
  painPoint: PainPointSummary;
  onUpdated: (updated: PainPointSummary) => void;
}) {
  const [saving, setSaving] = useState(false);

  async function onToggle(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (saving) return;
    setSaving(true);
    try {
      const updated = await api.patch<PainPointSummary>(`/pain-points/${painPoint.id}/lifecycle`, {
        is_priority: !painPoint.is_priority,
      });
      onUpdated(updated);
    } catch {
      // Im lặng bỏ qua — nút giữ nguyên trạng thái cũ, người dùng bấm lại được ngay, không cần
      // banner lỗi cho 1 thao tác đánh dấu nhanh không phá huỷ dữ liệu gì.
    } finally {
      setSaving(false);
    }
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={saving}
      aria-pressed={painPoint.is_priority}
      title={painPoint.is_priority ? "Bỏ đánh dấu cấp thiết nhất" : "Đánh dấu là cấp thiết nhất với doanh nghiệp"}
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors disabled:opacity-50 ${
        painPoint.is_priority
          ? "text-[var(--color-amber-glow)] hover:bg-[var(--color-amber-glow)]/10"
          : "text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-ink-2)]"
      }`}
    >
      <Star size={16} weight={painPoint.is_priority ? "fill" : "regular"} />
    </button>
  );
}
