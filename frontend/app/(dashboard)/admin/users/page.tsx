"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { AdminUserSummary } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Topbar } from "@/components/layout/Topbar";

function formatUsd(value: number): string {
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
}

export default function AdminUsersPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<AdminUserSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setQ(searchInput), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (!user?.is_platform_admin) return;
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    api
      .get<AdminUserSummary[]>(`/admin/users?${params.toString()}`)
      .then(setRows)
      .catch(() => setError("Không tải được danh sách tài khoản"));
  }, [user, q]);

  if (!user?.is_platform_admin) {
    return (
      <div>
        <Topbar title="Quản lý tài khoản" />
        <Card className="mt-6 p-8 text-center">
          <p className="text-[14px] font-semibold text-[var(--color-ink)]">Không có quyền truy cập</p>
          <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">Trang này chỉ dành cho tài khoản quản trị nền tảng.</p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <Topbar title="Quản lý tài khoản" subtitle="Toàn bộ tài khoản, số topic đang có, và mức tiêu thụ token/chi phí ước tính." />

      <div className="pt-6">
        <Link href="/admin" className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]">
          ← Quay lại trang quản trị
        </Link>

        <Card className="mt-4 mb-4 p-5">
          <CardBody className="p-0">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Tìm theo email/tên..."
            />
          </CardBody>
        </Card>

        {error && <p className="text-sm text-[var(--color-rose)]">{error}</p>}
        {rows === null && !error && <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {rows && (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px] text-[13px]">
                <thead>
                  <tr className="bg-[var(--color-cream-2)] text-[11px] tracking-[0.14em] text-[var(--color-muted)] uppercase">
                    <th className="px-5 py-3 text-left font-medium">Tài khoản</th>
                    <th className="px-5 py-3 text-left font-medium">Vai trò</th>
                    <th className="px-5 py-3 text-left font-medium">Trạng thái</th>
                    <th className="px-5 py-3 text-right font-medium">Số topic</th>
                    <th className="px-5 py-3 text-right font-medium">Token đầu vào</th>
                    <th className="px-5 py-3 text-right font-medium">Token đầu ra</th>
                    <th className="px-5 py-3 text-right font-medium">Chi phí ước tính</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t border-[var(--color-line)] hover:bg-[var(--color-cream-2)]/40">
                      <td className="px-5 py-3">
                        <Link href={`/admin/users/${row.id}`} className="block">
                          <p className="font-medium text-[var(--color-ink)]">{row.full_name || row.email}</p>
                          {row.full_name && <p className="text-xs text-[var(--color-muted)]">{row.email}</p>}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-[var(--color-ink-2)]">
                        {row.is_platform_admin ? "Quản trị" : "Người dùng"}
                      </td>
                      <td className="px-5 py-3 text-[var(--color-ink-2)]">
                        {row.is_paid ? (
                          "Đã trả phí"
                        ) : row.trial_analysis_call_limit ? (
                          <span
                            className={
                              row.usage.call_count >= row.trial_analysis_call_limit
                                ? "font-medium text-[var(--color-rose)]"
                                : ""
                            }
                          >
                            Dùng thử — {row.usage.call_count.toLocaleString("vi-VN")}/
                            {row.trial_analysis_call_limit.toLocaleString("vi-VN")} lượt
                          </span>
                        ) : (
                          "Dùng thử"
                        )}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-[var(--color-ink-2)]">{row.topic_count}</td>
                      <td className="px-5 py-3 text-right tabular-nums text-[var(--color-ink-2)]">
                        {row.usage.total_input_tokens.toLocaleString("vi-VN")}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-[var(--color-ink-2)]">
                        {row.usage.total_output_tokens.toLocaleString("vi-VN")}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-[var(--color-ink-2)]">
                        {formatUsd(row.usage.estimated_cost_usd)}
                        {row.usage.has_unpriced_usage && <span title="Có model chưa rõ giá">*</span>}
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-5 py-8 text-center text-sm text-[var(--color-muted)]">
                        Không có tài khoản nào khớp tìm kiếm.
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
