"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { CaretLeft, CaretRight } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { LifecycleStatus, PainPointSummary, Topic } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import {
  SeverityBadge,
  TrendBadge,
  ReferenceBadge,
  LifecycleBadge,
  LIFECYCLE_OPTIONS,
  severityBucket,
  SEVERITY_ACCENT_COLOR,
} from "@/components/ui/Badges";
import { SlaBadge } from "@/components/painpoints/SlaBadge";
import { PriorityToggle } from "@/components/painpoints/PriorityToggle";
import { sortPainPoints } from "@/lib/painPointSort";
import { Topbar } from "@/components/layout/Topbar";

type PainPointRow = PainPointSummary & { topicId: string; topicName: string };

// Trang (không phải "tải thêm") — gộp pain point từ MỌI chủ đề nên danh sách có thể dài (vd 6 chủ
// đề x tối đa 9 nhóm/chủ đề ~ 50+ dòng), lướt hết rất mỏi tay. Toàn bộ dữ liệu vẫn tải 1 lần (API
// pain-points không hỗ trợ phân trang phía server) — chỉ CẮT hiển thị phía client theo trang.
const PAGE_SIZE = 12;

export default function CrossTopicPainPointsPage() {
  const [rows, setRows] = useState<PainPointRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<LifecycleStatus | "all">("all");
  const [page, setPage] = useState(0);

  useEffect(() => {
    api
      .get<Topic[]>("/topics")
      .then(async (topics) => {
        const active = topics.filter((t) => t.status === "active");
        const perTopic = await Promise.all(
          active.map(async (topic) => {
            const pps = await api.get<PainPointSummary[]>(`/topics/${topic.id}/pain-points`).catch(() => []);
            return pps.map((pp) => ({ ...pp, topicId: topic.id, topicName: topic.name }));
          }),
        );
        // Mỗi topic tự trả về ĐÚNG thứ tự (ưu tiên rồi severity, xem _pain_point_order_by ở
        // backend), nhưng gộp nhiều topic lại thì cần sắp lại LẦN NỮA cho đúng thứ tự CHUNG —
        // nối trực tiếp các mảng đã sắp riêng không cho ra 1 thứ tự đúng xuyên suốt cả danh sách.
        setRows(sortPainPoints(perTopic.flat()));
      })
      .catch(() => setError("Không tải được danh sách pain point"));
  }, []);

  const filtered = rows?.filter((r) => statusFilter === "all" || r.lifecycle_status === statusFilter) ?? null;
  const totalPages = filtered ? Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)) : 1;
  // Đổi bộ lọc mà giữ nguyên số trang cũ dễ rơi vào trang rỗng (vd đang ở trang 4, lọc còn 1
  // trang) — luôn quay về trang đầu khi đổi bộ lọc.
  const currentPage = Math.min(page, totalPages - 1);
  const pageItems = filtered?.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE) ?? null;

  function changeFilter(value: LifecycleStatus | "all") {
    setStatusFilter(value);
    setPage(0);
  }

  function onPainPointUpdated(updated: PainPointSummary) {
    setRows((prev) =>
      prev ? sortPainPoints(prev.map((r) => (r.id === updated.id ? { ...r, ...updated } : r))) : prev,
    );
  }

  return (
    <div>
      <Topbar
        title="Pain Point"
        subtitle="Toàn bộ pain point đang theo dõi, gộp từ mọi chủ đề — bấm ★ để đánh dấu cấp thiết nhất với doanh nghiệp, mặc định sắp theo mức độ nghiêm trọng."
      />

      <div className="pt-6">
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <button
            onClick={() => changeFilter("all")}
            className={
              statusFilter === "all"
                ? "h-8 rounded-full bg-[var(--color-ink)] px-3.5 text-[12.5px] font-medium text-white"
                : "h-8 rounded-full border border-[var(--color-line)] bg-white px-3.5 text-[12.5px] font-medium text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
            }
          >
            Tất cả
          </button>
          {LIFECYCLE_OPTIONS.map((o) => (
            <button
              key={o.value}
              onClick={() => changeFilter(o.value)}
              className={
                statusFilter === o.value
                  ? "h-8 rounded-full bg-[var(--color-ink)] px-3.5 text-[12.5px] font-medium text-white"
                  : "h-8 rounded-full border border-[var(--color-line)] bg-white px-3.5 text-[12.5px] font-medium text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
              }
            >
              {o.label}
            </button>
          ))}
        </div>

        {error && <p className="text-sm text-[var(--color-rose)]">{error}</p>}
        {rows === null && !error && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {filtered && filtered.length === 0 && (
          <Card>
            <CardBody className="mx-auto max-w-sm p-8 text-center">
              <p className="text-[14px] font-semibold text-[var(--color-ink)]">Chưa có pain point nào</p>
              <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">
                Pain point được tạo tự động khi 1 nhóm phản hồi cùng chủ đề đạt ngưỡng cảnh báo.
              </p>
            </CardBody>
          </Card>
        )}

        <div className="space-y-2.5">
          <AnimatePresence initial={false}>
            {pageItems?.map((pp, index) => (
              <motion.div
                key={pp.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.04 }}
              >
                <Link
                  href={`/topics/${pp.topicId}/pain-points/${pp.id}`}
                  style={{ borderLeftColor: pp.severity_avg !== null ? SEVERITY_ACCENT_COLOR[severityBucket(pp.severity_avg)] : "var(--color-line)" }}
                  className="card-soft flex flex-col gap-3 border-l-[3px] p-4 transition duration-300 hover:-translate-y-[1px] hover:shadow-[0_18px_50px_rgba(11,18,32,0.08)] md:flex-row md:items-center"
                >
                  <div className="min-w-0 flex-1">
                    <p className="eyebrow">{pp.topicName}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 font-semibold text-[var(--color-ink)]">
                      <PriorityToggle painPoint={pp} onUpdated={onPainPointUpdated} />
                      {pp.title}
                    </p>
                    {pp.description && <p className="mt-1 line-clamp-2 text-[13px] text-[var(--color-muted)]">{pp.description}</p>}
                  </div>
                  <div className="flex flex-shrink-0 flex-wrap items-center gap-2">
                    <SeverityBadge score={pp.severity_avg} />
                    <TrendBadge trend={pp.trend} />
                    <ReferenceBadge status={pp.reference_status} />
                    <LifecycleBadge status={pp.lifecycle_status} />
                    <SlaBadge dueAt={pp.due_at} isBreached={pp.is_breached} lifecycleStatus={pp.lifecycle_status} />
                    <span className="text-xs text-[var(--color-muted)]">{pp.post_count} phản hồi</span>
                  </div>
                </Link>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {filtered && filtered.length > PAGE_SIZE && (
          <div className="mt-5 flex items-center justify-center gap-3">
            <button
              onClick={() => setPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0}
              aria-label="Trang trước"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--color-line)] bg-white text-[var(--color-ink-2)] transition-colors hover:bg-[var(--color-cream-2)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <CaretLeft size={14} />
            </button>
            <span className="text-[12.5px] font-medium text-[var(--color-muted)] tabular-nums">
              Trang {currentPage + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, currentPage + 1))}
              disabled={currentPage >= totalPages - 1}
              aria-label="Trang sau"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--color-line)] bg-white text-[var(--color-ink-2)] transition-colors hover:bg-[var(--color-cream-2)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <CaretRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
