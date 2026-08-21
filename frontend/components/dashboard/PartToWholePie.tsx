"use client";

import { useMemo, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

// Bảng màu categorical đã validate (xem globals.css) — thứ tự CỐ ĐỊNH theo slot, không cycle lại.
const CATEGORY_COLORS = [
  "var(--viz-cat-1)",
  "var(--viz-cat-2)",
  "var(--viz-cat-3)",
  "var(--viz-cat-4)",
  "var(--viz-cat-5)",
  "var(--viz-cat-6)",
];
const OTHER_COLOR = "var(--viz-muted)";

// Pie/donut chỉ đọc được "phần-trong-tổng thể ở cái nhìn đầu tiên" khi ≤ 6 lát — quá đó các lát
// nhỏ chèn nhau, không đọc nổi. Gộp phần còn lại vào "Khác" thay vì vẽ hết (vd 9 nhóm topic_label).
const MAX_SLICES = 5;

export interface PieSlice {
  label: string;
  value: number;
}

function sortedNonZero(slices: PieSlice[]): PieSlice[] {
  return [...slices].filter((s) => s.value > 0).sort((a, b) => b.value - a.value);
}

function foldToTopN(sorted: PieSlice[], maxSlices: number): PieSlice[] {
  if (sorted.length <= maxSlices) return sorted;
  const top = sorted.slice(0, maxSlices);
  const restTotal = sorted.slice(maxSlices).reduce((sum, s) => sum + s.value, 0);
  return [...top, { label: "Khác", value: restTotal }];
}

/** Biểu đồ tròn phần-trong-tổng-thể dùng chung — kèm bảng số liệu thay thế (xem accessibility
 * trong skill dataviz: mọi biểu đồ cần có bản xem dạng bảng tương đương).
 *
 * "Khác" trên biểu đồ KHÔNG phải 1 nhóm dữ liệu thật (topic_label/topic_name luôn có tên rõ ràng,
 * chỉ hết chỗ vẽ mới bị gộp) — người xem không có cách nào biết bên trong gồm những gì nếu chỉ nhìn
 * lát bánh. Bảng số liệu vì vậy KHÔNG gộp (không bị giới hạn không gian như biểu đồ, hiển thị đủ
 * mọi nhóm gốc), và tooltip của lát "Khác" liệt kê rõ thành phần bên trong — thay vì để người dùng
 * đoán "khác" ở đây là khác cái gì. */
export function PartToWholePie({ data, valueLabel }: { data: PieSlice[]; valueLabel: string }) {
  const [showTable, setShowTable] = useState(false);
  const fullSlices = useMemo(() => sortedNonZero(data), [data]);
  const chartSlices = useMemo(() => foldToTopN(fullSlices, MAX_SLICES), [fullSlices]);
  // Đúng các nhóm bị gộp vào lát "Khác" ở trên (cùng nguồn fullSlices, cùng ngưỡng MAX_SLICES) —
  // dùng để làm giàu tooltip, không tính lại logic gộp lần 2.
  const otherSlices = useMemo(() => fullSlices.slice(MAX_SLICES), [fullSlices]);
  const total = fullSlices.reduce((sum, s) => sum + s.value, 0);

  if (total === 0) {
    return (
      <div className="viz-root flex h-56 items-center justify-center rounded-lg text-sm text-[var(--viz-muted)]">
        Chưa có đủ dữ liệu.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button onClick={() => setShowTable((v) => !v)} className="text-xs text-brand-600 hover:underline">
          {showTable ? "Xem biểu đồ" : "Xem dạng bảng"}
        </button>
      </div>

      {showTable ? (
        <div className="viz-root overflow-x-auto rounded-lg border border-[var(--viz-grid)]">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--viz-grid)] text-[var(--viz-text-secondary)]">
                <th className="px-3 py-2 font-medium">Nhóm</th>
                <th className="px-3 py-2 text-right font-medium">{valueLabel}</th>
                <th className="px-3 py-2 text-right font-medium">Tỉ lệ</th>
              </tr>
            </thead>
            <tbody>
              {fullSlices.map((s) => (
                <tr key={s.label} className="border-b border-[var(--viz-grid)] last:border-0">
                  <td className="px-3 py-1.5 text-[var(--viz-text-primary)]">{s.label}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-[var(--viz-text-primary)]">{s.value}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-[var(--viz-text-secondary)]">
                    {Math.round((s.value / total) * 1000) / 10}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="viz-root h-64 rounded-lg bg-[var(--viz-surface)] p-2">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartSlices}
                dataKey="value"
                nameKey="label"
                innerRadius="55%"
                outerRadius="85%"
                paddingAngle={2}
                stroke="var(--viz-surface)"
                strokeWidth={2}
              >
                {chartSlices.map((s, i) => (
                  <Cell
                    key={s.label}
                    fill={s.label === "Khác" ? OTHER_COLOR : CATEGORY_COLORS[i % CATEGORY_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name) => {
                  const v = Number(value) || 0;
                  const pct = Math.round((v / total) * 1000) / 10;
                  // Lát "Khác" giải thích rõ NGAY trong tooltip đang gộp những nhóm nào — không bắt
                  // người dùng phải bấm "Xem dạng bảng" mới hiểu "khác" ở đây là khác cái gì.
                  if (String(name) === "Khác" && otherSlices.length > 0) {
                    const detail = otherSlices.map((s) => `${s.label}: ${s.value}`).join(", ");
                    return [`${v} (${pct}%) — gồm ${detail}`, String(name)];
                  }
                  return [`${v} (${pct}%)`, String(name)];
                }}
                contentStyle={{
                  background: "var(--viz-surface)",
                  border: "1px solid var(--viz-grid)",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "var(--viz-text-primary)",
                }}
              />
              <Legend
                layout="vertical"
                align="right"
                verticalAlign="middle"
                iconType="circle"
                wrapperStyle={{ fontSize: 12, color: "var(--viz-text-secondary)" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
