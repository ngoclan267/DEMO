"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { AdminContactSummary } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Topbar } from "@/components/layout/Topbar";

type HandledFilter = "all" | "pending" | "handled";

const FILTERS: { value: HandledFilter; label: string }[] = [
  { value: "pending", label: "Chưa xử lý" },
  { value: "handled", label: "Đã xử lý" },
  { value: "all", label: "Tất cả" },
];

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function AdminContactsPage() {
  const { user } = useAuth();
  const [filter, setFilter] = useState<HandledFilter>("pending");
  const [rows, setRows] = useState<AdminContactSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load(f: HandledFilter) {
    const params = new URLSearchParams();
    if (f === "pending") params.set("handled", "false");
    if (f === "handled") params.set("handled", "true");
    api
      .get<AdminContactSummary[]>(`/admin/contacts?${params.toString()}`)
      .then(setRows)
      .catch(() => setError("Không tải được danh sách liên hệ"));
  }

  useEffect(() => {
    if (!user?.is_platform_admin) return;
    setRows(null);
    setError(null);
    load(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load() đọc filter qua tham số, không cần liệt kê lại
  }, [user, filter]);

  async function toggleHandled(row: AdminContactSummary) {
    const nextHandled = !row.is_handled;
    try {
      await api.patch(`/admin/contacts/${row.id}`, { is_handled: nextHandled });
      toast.success(nextHandled ? "Đã đánh dấu xử lý" : "Đã bỏ đánh dấu xử lý");
      // Đổi trạng thái xong có thể không còn khớp bộ lọc hiện tại (vd đang xem "Chưa xử lý") — tải
      // lại đúng theo filter thay vì chỉ sửa state tại chỗ, để danh sách luôn khớp bộ lọc đang chọn.
      load(filter);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Không cập nhật được trạng thái");
    }
  }

  if (!user?.is_platform_admin) {
    return (
      <div>
        <Topbar title="Yêu cầu liên hệ" />
        <Card className="mt-6 p-8 text-center">
          <p className="text-[14px] font-semibold text-[var(--color-ink)]">Không có quyền truy cập</p>
          <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">Trang này chỉ dành cho tài khoản quản trị nền tảng.</p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <Topbar title="Yêu cầu liên hệ" subtitle="Doanh nghiệp gửi từ form &ldquo;Liên hệ tư vấn&rdquo; trên trang giới thiệu — cùng nội dung đã gửi qua email." />

      <div className="pt-6">
        <Link href="/admin" className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]">
          ← Quay lại trang quản trị
        </Link>

        <div className="mt-4 mb-4 flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`h-9 rounded-full border px-3.5 text-sm font-medium transition-colors ${
                filter === f.value
                  ? "border-[var(--color-brand-500)] bg-[var(--color-brand-50)] text-[var(--color-brand-700)]"
                  : "border-[var(--color-line)] text-[var(--color-ink-2)] hover:border-[var(--color-bone)] hover:bg-[var(--color-brand-50)]/40"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p className="text-sm text-[var(--color-rose)]">{error}</p>}
        {rows === null && !error && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {rows && (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] text-[13px]">
                <thead>
                  <tr className="bg-[var(--color-cream-2)] text-[11px] tracking-[0.14em] text-[var(--color-muted)] uppercase">
                    <th className="px-5 py-3 text-left font-medium">Doanh nghiệp</th>
                    <th className="px-5 py-3 text-left font-medium">Người liên hệ</th>
                    <th className="px-5 py-3 text-left font-medium">Lời nhắn</th>
                    <th className="px-5 py-3 text-left font-medium">Thời gian</th>
                    <th className="px-5 py-3 text-right font-medium">Thao tác</th>
                    <th className="px-5 py-3 text-right font-medium">Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t border-[var(--color-line)] align-top hover:bg-[var(--color-cream-2)]/40">
                      <td className="px-5 py-3">
                        <p className="font-medium text-[var(--color-ink)]">{row.company_name}</p>
                      </td>
                      <td className="px-5 py-3">
                        <p className="text-[var(--color-ink-2)]">{row.contact_name}</p>
                        <p className="text-xs text-[var(--color-muted)]">{row.email}</p>
                        {row.phone && <p className="text-xs text-[var(--color-muted)]">{row.phone}</p>}
                      </td>
                      <td className="max-w-[280px] px-5 py-3 text-[var(--color-ink-2)]">
                        {row.message || <span className="text-[var(--color-muted)]">—</span>}
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap text-[var(--color-ink-2)]">{formatDateTime(row.created_at)}</td>
                      <td className="px-5 py-3 text-right whitespace-nowrap">
                        <Link
                          href={`/admin?${new URLSearchParams({
                            owner_email: row.email,
                            ...(row.contact_name ? { owner_full_name: row.contact_name } : {}),
                          }).toString()}`}
                          className="inline-flex h-8 items-center rounded-full border border-[var(--color-brand-500)] bg-[var(--color-brand-50)] px-3 text-xs font-medium text-[var(--color-brand-700)] transition-colors hover:bg-[var(--color-brand-100)]"
                        >
                          Tạo tài khoản
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => toggleHandled(row)}
                          className={`h-8 rounded-full border px-3 text-xs font-medium transition-colors ${
                            row.is_handled
                              ? "border-[var(--color-leaf)]/30 bg-[var(--color-leaf)]/10 text-[var(--color-leaf)] hover:bg-[var(--color-leaf)]/20"
                              : "border-[var(--color-amber-glow)]/30 bg-[var(--color-amber-glow)]/10 text-[var(--color-amber-glow)] hover:bg-[var(--color-amber-glow)]/20"
                          }`}
                        >
                          {row.is_handled ? "Đã xử lý" : "Chưa xử lý"}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-sm text-[var(--color-muted)]">
                        Không có yêu cầu liên hệ nào khớp bộ lọc.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
