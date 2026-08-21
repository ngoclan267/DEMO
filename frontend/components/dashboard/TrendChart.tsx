"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HourlyTrendPoint, TrendPoint } from "@/lib/types";

function formatDate(value: string) {
  const d = new Date(value);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

function formatHour(value: string) {
  const d = new Date(value);
  return `${d.getHours()}h`;
}

// Số nhãn ngày tối đa hiện trên trục X — chart chỉ rộng ~1 thẻ card, nhãn kiểu "1/8" (~3-4 ký tự)
// dày đặc hơn con số này sẽ đè chồng lên nhau đọc không nổi (quan sát thật: 30 điểm dữ liệu/tháng
// hiện đủ 30 nhãn liền nhau không có khoảng trắng). Không hardcode 1 khoảng cách cố định vì dữ liệu
// có thể chỉ vài ngày (không cần bỏ bớt nhãn nào) hoặc cả tháng — tính THEO SỐ ĐIỂM DỮ LIỆU THẬT để
// luôn ra khoảng đều nhau, không phụ thuộc con số 30 ngày cụ thể của khung thời gian đang chọn.
const MAX_VISIBLE_TICKS = 10;

interface TrendChartProps {
  data: TrendPoint[];
  /** Cung cấp để bật zoom xem chi tiết theo GIỜ khi click vào biểu đồ — nhận ngày (TrendPoint.date)
   * bị click, trả về các điểm theo giờ của đúng ngày đó (caller tự quyết định gọi endpoint nào —
   * /pain-points/{id}/trend/hourly hay /topics/{id}/trend/hourly, xem các trang dùng component
   * này). Không truyền thì chart giữ nguyên hành vi cũ, không click được.
   */
  onDrillDown?: (date: string) => Promise<HourlyTrendPoint[]>;
}

export function TrendChart({ data, onDrillDown }: TrendChartProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [hourlyData, setHourlyData] = useState<HourlyTrendPoint[] | null>(null);
  const [loadingHourly, setLoadingHourly] = useState(false);

  async function handleChartClick(state: { activeLabel?: string | number }) {
    if (!onDrillDown || state.activeLabel === undefined) return;
    const date = String(state.activeLabel);
    setSelectedDate(date);
    setLoadingHourly(true);
    try {
      setHourlyData(await onDrillDown(date));
    } finally {
      setLoadingHourly(false);
    }
  }

  if (selectedDate) {
    return (
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
          <span className="text-xs text-[var(--viz-muted)]">{formatDate(selectedDate)} — chi tiết theo giờ</span>
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
    );
  }

  if (data.length === 0) {
    return (
      <div className="viz-root flex h-64 items-center justify-center rounded-lg text-sm text-[var(--viz-muted)]">
        Chưa có đủ dữ liệu để hiển thị xu hướng.
      </div>
    );
  }

  // interval=N (theo Recharts) nghĩa là "bỏ qua N nhãn giữa 2 nhãn hiện ra" — vd interval=1 hiện
  // đúng 1 nhãn rồi bỏ 1 nhãn kế tiếp (1/8, 3/8, 5/8...), không phải "hiện N nhãn".
  const tickInterval = Math.max(0, Math.ceil(data.length / MAX_VISIBLE_TICKS) - 1);

  return (
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
            dataKey="date"
            tickFormatter={formatDate}
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
          <Tooltip
            labelFormatter={(value) => formatDate(String(value))}
            contentStyle={{
              background: "var(--viz-surface)",
              border: "1px solid var(--viz-grid)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--viz-text-primary)",
            }}
          />
          <Legend
            iconType="line"
            wrapperStyle={{ fontSize: 12, color: "var(--viz-text-secondary)" }}
          />
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
    </div>
  );
}
