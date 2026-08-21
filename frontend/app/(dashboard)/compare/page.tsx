"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { HourlyTrendPoint, PeriodComparisonResponse, PeriodStats, Topic } from "@/lib/types";
import { PERIOD_PRESET_OPTIONS, resolvePreset, type DateRange, type PeriodPreset } from "@/lib/periodPresets";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";
import { PartToWholePie, type PieSlice } from "@/components/dashboard/PartToWholePie";
import { PeriodTrendChart } from "@/components/dashboard/PeriodTrendChart";
import { Topbar } from "@/components/layout/Topbar";

function formatVn(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function negativeRate(stats: PeriodStats): number | null {
  const total = Object.values(stats.sentiment_breakdown).reduce((a, b) => a + b, 0);
  if (total === 0) return null;
  return ((stats.sentiment_breakdown.negative ?? 0) / total) * 100;
}

function toSlices(breakdown: Record<string, number>): PieSlice[] {
  return Object.entries(breakdown).map(([label, value]) => ({ label, value }));
}

/** Chênh lệch giai đoạn B so với A — `goodDirection` quyết định màu (tăng là tốt/xấu/trung tính
 * tuỳ chỉ số, vd tỉ lệ tiêu cực giảm là tốt nhưng tổng phản hồi tăng không hẳn tốt hay xấu). */
function DeltaBadge({ from, to, goodDirection, suffix = "" }: { from: number | null; to: number | null; goodDirection: "down" | "up" | "neutral"; suffix?: string }) {
  if (from === null || to === null) return null;
  const diff = to - from;
  if (diff === 0) return <span className="text-xs font-medium text-[var(--color-muted)]">Không đổi</span>;
  const increased = diff > 0;
  const isGood = goodDirection === "neutral" ? null : increased ? goodDirection === "up" : goodDirection === "down";
  const color = isGood === null ? "text-[var(--color-muted)]" : isGood ? "text-[var(--color-leaf)]" : "text-[var(--color-rose)]";
  const arrow = increased ? "▲" : "▼";
  const magnitude = Math.abs(diff);
  return (
    <span className={`text-xs font-semibold ${color}`}>
      {arrow} {magnitude % 1 === 0 ? magnitude : magnitude.toFixed(1)}
      {suffix}
    </span>
  );
}

function StatCompareRow({
  label,
  periodA,
  periodB,
  goodDirection,
  suffix = "",
}: {
  label: string;
  periodA: number | null;
  periodB: number | null;
  goodDirection: "down" | "up" | "neutral";
  suffix?: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--color-line)] py-3 last:border-0">
      <p className="text-[13px] text-[var(--color-ink-2)]">{label}</p>
      <div className="flex items-center gap-4">
        <span className="w-16 text-right text-[13px] tabular-nums text-[var(--color-muted)]">
          {periodA === null ? "—" : `${periodA % 1 === 0 ? periodA : periodA.toFixed(1)}${suffix}`}
        </span>
        <span className="w-16 text-right text-[15px] font-semibold tabular-nums text-[var(--color-ink)]">
          {periodB === null ? "—" : `${periodB % 1 === 0 ? periodB : periodB.toFixed(1)}${suffix}`}
        </span>
        <div className="w-20 text-right">
          <DeltaBadge from={periodA} to={periodB} goodDirection={goodDirection} suffix={suffix} />
        </div>
      </div>
    </div>
  );
}

export default function ComparePage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicId, setTopicId] = useState<string | null>(null);
  const [preset, setPreset] = useState<PeriodPreset | "custom">("this_week");
  const [periodA, setPeriodA] = useState<DateRange>(() => resolvePreset("this_week").periodA);
  const [periodB, setPeriodB] = useState<DateRange>(() => resolvePreset("this_week").periodB);
  const [data, setData] = useState<PeriodComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Topic[]>("/topics").then((all) => {
      setTopics(all);
      if (all.length > 0) setTopicId(all[0].id);
    });
  }, []);

  function applyPreset(p: PeriodPreset) {
    setPreset(p);
    const { periodA: a, periodB: b } = resolvePreset(p);
    setPeriodA(a);
    setPeriodB(b);
  }

  const rangesValid = periodA.from <= periodA.to && periodB.from <= periodB.to;

  useEffect(() => {
    if (!topicId || !rangesValid) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      period_a_from: periodA.from,
      period_a_to: periodA.to,
      period_b_from: periodB.from,
      period_b_to: periodB.to,
    });
    api
      .get<PeriodComparisonResponse>(`/topics/${topicId}/compare-periods?${params.toString()}`)
      .then(setData)
      .catch(() => setError("Không tải được dữ liệu so sánh."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- periodA/periodB là object mới mỗi lần set, so theo field .from/.to bên dưới
  }, [topicId, periodA.from, periodA.to, periodB.from, periodB.to]);

  const negRateA = data ? negativeRate(data.period_a) : null;
  const negRateB = data ? negativeRate(data.period_b) : null;

  const pieA = useMemo(() => (data ? toSlices(data.period_a.negative_by_group) : []), [data]);
  const pieB = useMemo(() => (data ? toSlices(data.period_b.negative_by_group) : []), [data]);

  return (
    <div>
      <Topbar
        title="So sánh giai đoạn"
        subtitle="So sánh phản hồi giữa 2 mốc thời gian trong cùng 1 chủ đề — phát hiện xu hướng đang tốt lên hay xấu đi."
      />

      <div className="pt-6">
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Chủ đề</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {topics.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTopicId(t.id)}
                  className={`h-9 rounded-full border px-3.5 text-sm font-medium transition-colors ${
                    topicId === t.id
                      ? "border-[var(--color-brand-500)] bg-[var(--color-brand-50)] text-[var(--color-brand-700)]"
                      : "border-[var(--color-line)] text-[var(--color-ink-2)] hover:border-[var(--color-bone)] hover:bg-[var(--color-brand-50)]/40"
                  }`}
                >
                  {t.name}
                </button>
              ))}
              {topics.length === 0 && <p className="text-sm text-[var(--color-muted)]">Chưa có chủ đề nào.</p>}
            </div>
          </CardBody>
        </Card>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Mốc thời gian</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {PERIOD_PRESET_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => applyPreset(opt.value)}
                  className={`h-9 rounded-full border px-3.5 text-sm font-medium transition-colors ${
                    preset === opt.value
                      ? "border-[var(--color-brand-500)] bg-[var(--color-brand-50)] text-[var(--color-brand-700)]"
                      : "border-[var(--color-line)] text-[var(--color-ink-2)] hover:border-[var(--color-bone)] hover:bg-[var(--color-brand-50)]/40"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
              <button
                onClick={() => setPreset("custom")}
                className={`h-9 rounded-full border px-3.5 text-sm font-medium transition-colors ${
                  preset === "custom"
                    ? "border-[var(--color-brand-500)] bg-[var(--color-brand-50)] text-[var(--color-brand-700)]"
                    : "border-[var(--color-line)] text-[var(--color-ink-2)] hover:border-[var(--color-bone)] hover:bg-[var(--color-brand-50)]/40"
                }`}
              >
                Tuỳ chỉnh
              </button>
            </div>

            {preset === "custom" ? (
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <Label>Giai đoạn trước — từ</Label>
                  <Input type="date" value={periodA.from} onChange={(e) => setPeriodA((p) => ({ ...p, from: e.target.value }))} />
                  <Label className="mt-2">Giai đoạn trước — đến</Label>
                  <Input type="date" value={periodA.to} onChange={(e) => setPeriodA((p) => ({ ...p, to: e.target.value }))} />
                </div>
                <div>
                  <Label>Giai đoạn này — từ</Label>
                  <Input type="date" value={periodB.from} onChange={(e) => setPeriodB((p) => ({ ...p, from: e.target.value }))} />
                  <Label className="mt-2">Giai đoạn này — đến</Label>
                  <Input type="date" value={periodB.to} onChange={(e) => setPeriodB((p) => ({ ...p, to: e.target.value }))} />
                </div>
              </div>
            ) : (
              <p className="mt-3 text-xs text-[var(--color-muted)]">
                Giai đoạn trước: {formatVn(periodA.from)} – {formatVn(periodA.to)} · Giai đoạn này: {formatVn(periodB.from)} –{" "}
                {formatVn(periodB.to)}
              </p>
            )}
            {!rangesValid && <p className="mt-2 text-xs text-[var(--color-rose)]">Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.</p>}
          </CardBody>
        </Card>

        {!topicId ? (
          <p className="text-sm text-[var(--color-muted)]">Chọn 1 chủ đề ở trên để xem so sánh.</p>
        ) : error ? (
          <p className="text-sm text-[var(--color-rose)]">{error}</p>
        ) : loading || !data ? (
          <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>
        ) : (
          <>
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Tổng quan</CardTitle>
                <p className="mt-0.5 text-xs text-[var(--color-muted)]">Cột trái: giai đoạn trước · Cột giữa: giai đoạn này · Cột phải: chênh lệch</p>
              </CardHeader>
              <CardBody>
                <StatCompareRow label="Tổng phản hồi" periodA={data.period_a.post_count} periodB={data.period_b.post_count} goodDirection="neutral" />
                <StatCompareRow label="Tỉ lệ tiêu cực" periodA={negRateA} periodB={negRateB} goodDirection="down" suffix="%" />
                <StatCompareRow
                  label="Pain point mới phát sinh"
                  periodA={data.period_a.pain_point_count}
                  periodB={data.period_b.pain_point_count}
                  goodDirection="down"
                />
              </CardBody>
            </Card>

            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Xu hướng theo ngày</CardTitle>
                <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                  2 đường xếp theo &ldquo;ngày thứ N kể từ đầu giai đoạn&rdquo; để so hình dạng diễn biến, không phụ thuộc ngày lịch thật
                  của mỗi giai đoạn có trùng nhau hay không.
                </p>
              </CardHeader>
              <CardBody>
                <PeriodTrendChart
                  periodA={data.period_a}
                  periodB={data.period_b}
                  onDrillDown={(date) => api.get<HourlyTrendPoint[]>(`/topics/${topicId}/trend/hourly?date=${date}`)}
                />
              </CardBody>
            </Card>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Phân bổ tiêu cực — giai đoạn trước</CardTitle>
                </CardHeader>
                <CardBody>
                  <PartToWholePie data={pieA} valueLabel="Phản hồi tiêu cực" />
                </CardBody>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Phân bổ tiêu cực — giai đoạn này</CardTitle>
                </CardHeader>
                <CardBody>
                  <PartToWholePie data={pieB} valueLabel="Phản hồi tiêu cực" />
                </CardBody>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
