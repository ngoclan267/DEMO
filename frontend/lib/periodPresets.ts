/** Khoảng ngày cho tính năng "So sánh giai đoạn" (GET /topics/{id}/compare-periods) — tính theo
 * ngày dương lịch của TRÌNH DUYỆT (ứng dụng vốn giả định giờ Việt Nam xuyên suốt, xem VN_TZ ở
 * backend), dạng "YYYY-MM-DD" khớp query param kiểu `date` của FastAPI. */
export interface DateRange {
  from: string;
  to: string;
}

function toIsoDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(d: Date, days: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + days);
  return copy;
}

/** Thứ Hai của tuần chứa `d` (ISO — tuần bắt đầu từ thứ Hai, khớp quy ước lịch phổ biến ở VN). */
function startOfWeek(d: Date): Date {
  const day = d.getDay(); // 0=CN..6=T7
  const diffToMonday = day === 0 ? -6 : 1 - day;
  return addDays(d, diffToMonday);
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export type PeriodPreset = "this_week" | "last_week" | "this_month" | "last_month";

export const PERIOD_PRESET_OPTIONS: { value: PeriodPreset; label: string }[] = [
  { value: "this_week", label: "Tuần này / Tuần trước" },
  { value: "last_week", label: "Tuần trước / 2 tuần trước" },
  { value: "this_month", label: "Tháng này / Tháng trước" },
  { value: "last_month", label: "Tháng trước / 2 tháng trước" },
];

/** Trả về { periodA, periodB } — periodA là giai đoạn TRƯỚC (baseline), periodB là giai đoạn SAU
 * (giai đoạn đang so sánh tới) — khớp thứ tự period_a/period_b của backend. */
export function resolvePreset(preset: PeriodPreset, today: Date = new Date()): { periodA: DateRange; periodB: DateRange } {
  if (preset === "this_week" || preset === "last_week") {
    const thisWeekStart = startOfWeek(today);
    const bStart = preset === "this_week" ? thisWeekStart : addDays(thisWeekStart, -7);
    const bEnd = preset === "this_week" ? today : addDays(bStart, 6);
    const aStart = addDays(bStart, -7);
    const aEnd = addDays(bStart, -1);
    return {
      periodA: { from: toIsoDate(aStart), to: toIsoDate(aEnd) },
      periodB: { from: toIsoDate(bStart), to: toIsoDate(bEnd) },
    };
  }

  const thisMonthStart = startOfMonth(today);
  const bStart = preset === "this_month" ? thisMonthStart : new Date(thisMonthStart.getFullYear(), thisMonthStart.getMonth() - 1, 1);
  const bEnd = preset === "this_month" ? today : addDays(thisMonthStart, -1);
  const aStart = new Date(bStart.getFullYear(), bStart.getMonth() - 1, 1);
  const aEnd = addDays(bStart, -1);
  return {
    periodA: { from: toIsoDate(aStart), to: toIsoDate(aEnd) },
    periodB: { from: toIsoDate(bStart), to: toIsoDate(bEnd) },
  };
}
