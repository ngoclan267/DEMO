"use client";

import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { HourlyTrendPoint, PeriodStats, PeriodTrendPoint } from "@/lib/types";

function formatHour(value: string) {
  const d = new Date(value);
  return `${d.getHours()}h`;
}

// Slot 1/2 của bảng màu categorical đã validate (xem globals.css) — thứ tự CỐ ĐỊNH, không cycle —
// identity là "giai đoạn nào" (trước/sau), không phải thứ hạng, nên không dùng thang màu tuần tự.
// Màu KHÔNG đổi theo chỉ số đang chọn bên dưới (Tất cả/Tiêu cực/Tích cực) — bộ lọc chỉ đổi SỐ LIỆU
// vẽ ra, không đổi identity của từng đường, tránh người xem tưởng nhầm đang so 2 chỉ số khác nhau.
const COLOR_A = "var(--viz-cat-1)";
const COLOR_B = "var(--viz-cat-2)";

// Cùng giới hạn/lý do với TrendChart.tsx — nhãn "Ngày N" dày đặc hơn số này sẽ đè lên nhau (giai
// đoạn dài cả tháng, vd preset "Tháng này/Tháng trước", có thể ra tới ~31 điểm).
const MAX_VISIBLE_TICKS = 10;

type Metric = "count" | "negative_count" | "positive_count";

const METRIC_OPTIONS: { value: Metric; label: string }[] = [
  { value: "count", label: "Tất cả" },
  { value: "negative_count", label: "Tiêu cực" },
  { value: "positive_count", label: "Tích cực" },
];

const METRIC_UNIT_LABEL: Record<Metric, string> = {
  count: "phản hồi",
  negative_count: "phản hồi tiêu cực",
  positive_count: "phản hồi tích cực",
};

function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}-${String(dt.getUTCDate()).padStart(2, "0")}`;
}

function daySpan(from: string, to: string): number {
  const [y1, m1, d1] = from.split("-").map(Number);
  const [y2, m2, d2] = to.split("-").map(Number);
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86_400_000);
}

function formatVn(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

interface MergedPoint {
  dayIndex: number;
  aValue: number | null;
  aDate: string | null;
  bValue: number | null;
  bDate: string | null;
}

/** Gộp trend 2 giai đoạn (độ dài/ngày lịch có thể khác nhau — vd "tháng này" so "tháng trước") về
 * chung 1 trục "ngày thứ N kể từ đầu giai đoạn" để 2 đường so được HÌNH DẠNG diễn biến với nhau,
 * không bị lệch bởi ngày lịch thật khác nhau. `metric` chọn đúng 1 trong 3 chỉ số có sẵn trên mỗi
 * điểm trend (Tất cả/Tiêu cực/Tích cực) — vẫn CÙNG 1 hàm gộp, chỉ khác trường đọc ra. */
function mergeByDayOffset(periodA: PeriodStats, periodB: PeriodStats, metric: Metric): MergedPoint[] {
  const aMap = new Map(periodA.trend.map((p) => [p.date, p[metric]]));
  const bMap = new Map(periodB.trend.map((p) => [p.date, p[metric]]));
  const aDays = daySpan(periodA.date_from, periodA.date_to);
  const bDays = daySpan(periodB.date_from, periodB.date_to);
  const totalDays = Math.max(aDays, bDays);

  const points: MergedPoint[] = [];
  for (let i = 0; i <= totalDays; i++) {
    const aDate = i <= aDays ? addDaysIso(periodA.date_from, i) : null;
    const bDate = i <= bDays ? addDaysIso(periodB.date_from, i) : null;
    points.push({
      dayIndex: i + 1,
      aValue: aDate ? (aMap.get(aDate) ?? 0) : null,
      aDate,
      bValue: bDate ? (bMap.get(bDate) ?? 0) : null,
      bDate,
    });
  }
  return points;
}

function CustomTooltip({ active, payload, label, metric }: TooltipContentProps & { metric: Metric }) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as MergedPoint | undefined;
  if (!point) return null;
  const unit = METRIC_UNIT_LABEL[metric];
  return (
    <div
      style={{
        background: "var(--viz-surface)",
        border: "1px solid var(--viz-grid)",
        borderRadius: 8,
        padding: "8px 10px",
        fontSize: 12,
      }}
    >
      <p style={{ color: "var(--viz-text-secondary)", marginBottom: 4 }}>Ngày thứ {label}</p>
      {point.aDate && (
        <p style={{ color: COLOR_A, margin: 0 }}>
          Giai đoạn trước ({formatVn(point.aDate)}): <strong>{point.aValue}</strong> {unit}
        </p>
      )}
      {point.bDate && (
        <p style={{ color: COLOR_B, margin: 0 }}>
          Giai đoạn này ({formatVn(point.bDate)}): <strong>{point.bValue}</strong> {unit}
        </p>
      )}
    </div>
  );
}

/** Biểu đồ đường so trực quan 2 luồng thời gian (giai đoạn trước/sau) cạnh nhau, bổ sung cho các
 * thẻ số liệu tổng ở trên — xem hình dạng diễn biến theo ngày chứ không chỉ 1 con số cộng dồn.
 * Người dùng tự chọn xem đường Tất cả/Tiêu cực/Tích cực — 3 lựa chọn RIÊNG BIỆT (không chồng cả 3
 * lên nhau) để mỗi lần chỉ có đúng 2 đường (period A/B), không rối mắt. */
export function PeriodTrendChart({
  periodA,
  periodB,
  onDrillDown,
}: {
  periodA: PeriodStats;
  periodB: PeriodStats;
  /** Cung cấp để bật zoom xem chi tiết theo GIỜ khi click vào 1 điểm — nhận ngày THẬT bị click
   * (ưu tiên ngày của giai đoạn B/"giai đoạn này", vì 1 điểm gộp theo dayIndex có thể ứng với 2
   * ngày thật khác nhau của 2 giai đoạn), trả về các điểm theo giờ của ngày đó. */
  onDrillDown?: (date: string) => Promise<HourlyTrendPoint[]>;
}) {
  const [metric, setMetric] = useState<Metric>("count");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [hourlyData, setHourlyData] = useState<HourlyTrendPoint[] | null>(null);
  const [loadingHourly, setLoadingHourly] = useState(false);
  const data = mergeByDayOffset(periodA, periodB, metric);
  const hasData = data.some((p) => (p.aValue ?? 0) > 0 || (p.bValue ?? 0) > 0);

  // interval=N (theo Recharts) nghĩa là "bỏ qua N nhãn giữa 2 nhãn hiện ra", không phải "hiện N nhãn".
  const tickInterval = Math.max(0, Math.ceil(data.length / MAX_VISIBLE_TICKS) - 1);

  async function handleChartClick(state: unknown) {
    if (!onDrillDown) return;
    const point = (state as { activePayload?: { payload: MergedPoint }[] } | undefined)?.activePayload?.[0]?.payload;
    const date = point?.bDate ?? point?.aDate;
    if (!date) return;
    setSelectedDate(date);
    setLoadingHourly(true);
    try {
      setHourlyData(await onDrillDown(date));
    } finally {
      setLoadingHourly(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {METRIC_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setMetric(opt.value)}
            className={`h-8 rounded-full border px-3 text-xs font-medium transition-colors ${
              metric === opt.value
                ? "border-[var(--color-brand-500)] bg-[var(--color-brand-50)] text-[var(--color-brand-700)]"
                : "border-[var(--color-line)] text-[var(--color-ink-2)] hover:border-[var(--color-bone)] hover:bg-[var(--color-brand-50)]/40"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {selectedDate ? (
        <div className="viz-root h-64 rounded-lg bg-[var(--viz-surface)] p-2">
          <div className="mb-1 flex items-center justify-between px-1">
            <button
              onClick={() => {
                setSelectedDate(null);
                setHourlyData(null);
              }}
              className="text-xs font-medium text-[var(--viz-text-secondary)] hover:text-[var(--viz-text-primary)]"
            >
              ← Quay lại xem theo ngày
            </button>
            <span className="text-xs text-[var(--viz-muted)]">{formatVn(selectedDate)} — chi tiết theo giờ</span>
          </div>
          {loadingHourly || hourlyData === null ? (
            <div className="flex h-[calc(100%-28px)] items-center justify-center text-sm text-[var(--viz-muted)]">
              Đang tải...
            </div>
          ) : hourlyData.length === 0 ? (
            <div className="flex h-[calc(100%-28px)] items-center justify-center text-sm text-[var(--viz-muted)]">
              Không có phản hồi nào trong ngày này.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="88%">
              <LineChart data={hourlyData} margin={{ top: 4, right: 16, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="var(--viz-grid)" vertical={false} />
                <XAxis
                  dataKey="hour"
                  tickFormatter={formatHour}
                  stroke="var(--viz-axis)"
                  tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--viz-axis)" }}
                />
                <YAxis
                  allowDecimals={false}
                  stroke="var(--viz-axis)"
                  tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  width={32}
                />
                <Tooltip
                  labelFormatter={(value) => formatHour(String(value))}
                  contentStyle={{
                    background: "var(--viz-surface)",
                    border: "1px solid var(--viz-grid)",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "var(--viz-text-primary)",
                  }}
                />
                <Legend iconType="line" wrapperStyle={{ fontSize: 12, color: "var(--viz-text-secondary)" }} />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="Tổng số phản hồi"
                  stroke="var(--viz-series-total)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="negative_count"
                  name="Phản hồi tiêu cực"
                  stroke="var(--viz-series-negative)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      ) : !hasData ? (
        <div className="viz-root flex h-64 items-center justify-center rounded-lg text-sm text-[var(--viz-muted)]">
          Chưa có đủ dữ liệu để hiển thị xu hướng.
        </div>
      ) : (
        <div className="viz-root h-64 rounded-lg bg-[var(--viz-surface)] p-2">
          {onDrillDown && (
            <p className="px-1 pb-1 text-[11px] text-[var(--viz-muted)]">Bấm vào 1 điểm để xem chi tiết theo giờ trong ngày đó.</p>
          )}
          <ResponsiveContainer width="100%" height={onDrillDown ? "92%" : "100%"}>
            <LineChart
              data={data}
              margin={{ top: 8, right: 16, bottom: 0, left: -16 }}
              onClick={onDrillDown ? handleChartClick : undefined}
              style={onDrillDown ? { cursor: "pointer" } : undefined}
            >
              <CartesianGrid stroke="var(--viz-grid)" vertical={false} />
              <XAxis
                dataKey="dayIndex"
                tickFormatter={(v) => `Ngày ${v}`}
                interval={tickInterval}
                stroke="var(--viz-axis)"
                tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: "var(--viz-axis)" }}
              />
              <YAxis
                allowDecimals={false}
                stroke="var(--viz-axis)"
                tick={{ fill: "var(--viz-muted)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip content={(props) => <CustomTooltip {...props} metric={metric} />} />
              <Legend iconType="line" wrapperStyle={{ fontSize: 12, color: "var(--viz-text-secondary)" }} />
              <Line
                type="monotone"
                dataKey="aValue"
                name="Giai đoạn trước"
                stroke={COLOR_A}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="bValue"
                name="Giai đoạn này"
                stroke={COLOR_B}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
