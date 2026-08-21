"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { AdminUserDetail } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Topbar } from "@/components/layout/Topbar";

function formatUsd(value: number): string {
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("vi-VN");
}

export default function AdminUserDetailPage() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const userId = params.id;

  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [fullName, setFullName] = useState("");
  const [isPaid, setIsPaid] = useState(false);
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  // yyyy-mm-dd cho <input type="date"> — "" nghĩa là KHÔNG giới hạn (trial_ends_at=null), gửi lên
  // là null, không phải chuỗi rỗng (xem onSave).
  const [trialEndsAt, setTrialEndsAt] = useState("");

  function load() {
    api
      .get<AdminUserDetail>(`/admin/users/${userId}`)
      .then((data) => {
        setDetail(data);
        setFullName(data.full_name || "");
        setIsPaid(data.is_paid);
        setIsPlatformAdmin(data.is_platform_admin);
        setTrialEndsAt(data.trial_ends_at ? data.trial_ends_at.slice(0, 10) : "");
      })
      .catch(() => setError("Không tải được thông tin tài khoản"));
  }

  function setTrialDaysFromNow(days: number) {
    const d = new Date();
    d.setDate(d.getDate() + days);
    setTrialEndsAt(d.toISOString().slice(0, 10));
  }

  useEffect(() => {
    if (!user?.is_platform_admin || !userId) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, userId]);

  if (!user?.is_platform_admin) {
    return (
      <div>
        <Topbar title="Chi tiết tài khoản" />
        <Card className="mt-6 p-8 text-center">
          <p className="text-[14px] font-semibold text-[var(--color-ink)]">Không có quyền truy cập</p>
          <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">Trang này chỉ dành cho tài khoản quản trị nền tảng.</p>
        </Card>
      </div>
    );
  }

  async function onSave() {
    setError(null);
    setSaving(true);
    try {
      const updated = await api.patch<AdminUserDetail>(`/admin/users/${userId}`, {
        full_name: fullName || null,
        is_paid: isPaid,
        is_platform_admin: isPlatformAdmin,
        trial_ends_at: trialEndsAt || null,
      });
      setDetail((prev) => (prev ? { ...prev, ...updated } : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được thay đổi");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    setError(null);
    setDeleting(true);
    try {
      await api.delete(`/admin/users/${userId}`);
      router.push("/admin/users");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không xoá được tài khoản");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div>
      <Topbar title="Chi tiết tài khoản" subtitle={detail?.email} />

      <div className="pt-6">
        <Link href="/admin/users" className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]">
          ← Quay lại danh sách tài khoản
        </Link>

        {error && <p className="mt-3 text-sm text-[var(--color-rose)]">{error}</p>}
        {!detail && !error && <p className="mt-3 text-sm text-[var(--color-muted)]">Đang tải...</p>}

        {detail && (
          <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.4fr]">
            <div className="space-y-6">
              <Card className="p-6">
                <CardHeader className="border-none p-0 pb-4">
                  <CardTitle>Thông tin tài khoản</CardTitle>
                </CardHeader>
                <CardBody className="space-y-4 p-0">
                  <div>
                    <Label>Email</Label>
                    <p className="text-[14px] text-[var(--color-ink)]">{detail.email}</p>
                  </div>
                  <div>
                    <Label htmlFor="fullName">Họ tên</Label>
                    <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      id="isPaid"
                      type="checkbox"
                      checked={isPaid}
                      onChange={(e) => setIsPaid(e.target.checked)}
                      className="h-4 w-4 rounded border-[var(--color-line)] accent-[var(--color-brand-500)]"
                    />
                    <Label htmlFor="isPaid" className="mb-0 normal-case tracking-normal">
                      Đã trả phí (bỏ chọn = dùng thử)
                    </Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      id="isPlatformAdmin"
                      type="checkbox"
                      checked={isPlatformAdmin}
                      onChange={(e) => setIsPlatformAdmin(e.target.checked)}
                      className="h-4 w-4 rounded border-[var(--color-line)] accent-[var(--color-brand-500)]"
                    />
                    <Label htmlFor="isPlatformAdmin" className="mb-0 normal-case tracking-normal">
                      Quyền quản trị nền tảng
                    </Label>
                  </div>
                  <div>
                    <Label htmlFor="trialEndsAt">Ngày hết hạn dùng thử</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="trialEndsAt"
                        type="date"
                        value={trialEndsAt}
                        onChange={(e) => setTrialEndsAt(e.target.value)}
                        className="w-auto"
                      />
                      <Button type="button" variant="ghost" onClick={() => setTrialDaysFromNow(14)}>
                        +14 ngày
                      </Button>
                      {trialEndsAt && (
                        <Button type="button" variant="ghost" onClick={() => setTrialEndsAt("")}>
                          Bỏ giới hạn
                        </Button>
                      )}
                    </div>
                    <p className="mt-1.5 text-[11px] text-[var(--color-muted)]">
                      Để trống = KHÔNG áp trần lượt gọi AI miễn phí (cả trần ngày lẫn trọn đời) cho tài khoản
                      này, dù đã bỏ chọn &quot;Đã trả phí&quot; ở trên — 2 field độc lập nhau.
                    </p>
                  </div>
                  <p className="text-[12px] text-[var(--color-muted)]">Tạo lúc: {formatDate(detail.created_at)}</p>
                  <FieldError>{error}</FieldError>
                  <Button onClick={onSave} loading={saving}>
                    Lưu thay đổi
                  </Button>
                </CardBody>
              </Card>

              <Card className="p-6">
                <CardHeader className="border-none p-0 pb-4">
                  <CardTitle>Mức tiêu thụ token (tổng)</CardTitle>
                </CardHeader>
                <CardBody className="space-y-2 p-0 text-[13px]">
                  <p className="flex justify-between">
                    <span className="text-[var(--color-muted)]">Số lượt gọi AI</span>
                    <span
                      className={`tabular-nums ${
                        detail.trial_analysis_call_limit && detail.usage.call_count >= detail.trial_analysis_call_limit
                          ? "font-semibold text-[var(--color-rose)]"
                          : "text-[var(--color-ink)]"
                      }`}
                    >
                      {detail.usage.call_count.toLocaleString("vi-VN")}
                      {detail.trial_analysis_call_limit && ` / ${detail.trial_analysis_call_limit.toLocaleString("vi-VN")} (mức miễn phí dùng thử)`}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-[var(--color-muted)]">Token đầu vào</span>
                    <span className="tabular-nums text-[var(--color-ink)]">{detail.usage.total_input_tokens.toLocaleString("vi-VN")}</span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-[var(--color-muted)]">Token đầu ra</span>
                    <span className="tabular-nums text-[var(--color-ink)]">{detail.usage.total_output_tokens.toLocaleString("vi-VN")}</span>
                  </p>
                  <p className="flex justify-between border-t border-[var(--color-line)] pt-2 font-semibold">
                    <span className="text-[var(--color-ink)]">Chi phí ước tính</span>
                    <span className="tabular-nums text-[var(--color-ink)]">
                      {formatUsd(detail.usage.estimated_cost_usd)}
                      {detail.usage.has_unpriced_usage && "*"}
                    </span>
                  </p>
                  {detail.usage.has_unpriced_usage && (
                    <p className="text-[11px] text-[var(--color-muted)]">* Có model chưa xác định được đơn giá — chi phí thật có thể cao hơn số hiển thị.</p>
                  )}
                </CardBody>
              </Card>

              <Card className="border-[var(--color-rose)]/40 p-6">
                <CardHeader className="border-none p-0 pb-3">
                  <CardTitle className="text-[var(--color-rose)]">Khu vực nguy hiểm</CardTitle>
                </CardHeader>
                <CardBody className="p-0">
                  {!confirmDelete ? (
                    <Button variant="secondary" onClick={() => setConfirmDelete(true)}>
                      Xoá tài khoản này
                    </Button>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-[13px] text-[var(--color-ink)]">
                        Xoá tài khoản sẽ xoá toàn bộ chủ đề, nguồn dữ liệu và dữ liệu liên quan. Không thể hoàn tác. Chắc chắn?
                      </p>
                      <div className="flex gap-2">
                        <Button variant="danger" onClick={onDelete} loading={deleting}>
                          Xác nhận xoá
                        </Button>
                        <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                          Huỷ
                        </Button>
                      </div>
                    </div>
                  )}
                </CardBody>
              </Card>
            </div>

            <Card className="overflow-hidden p-0">
              <CardHeader className="p-6 pb-4">
                <CardTitle>Chủ đề đang quản lý ({detail.topics.length})</CardTitle>
              </CardHeader>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-[13px]">
                  <thead>
                    <tr className="bg-[var(--color-cream-2)] text-[11px] tracking-[0.14em] text-[var(--color-muted)] uppercase">
                      <th className="px-6 py-3 text-left font-medium">Tên chủ đề</th>
                      <th className="px-4 py-3 text-right font-medium">Nguồn</th>
                      <th className="px-4 py-3 text-right font-medium">Phản hồi</th>
                      <th className="px-4 py-3 text-right font-medium">Pain point</th>
                      <th className="px-6 py-3 text-right font-medium">Chi phí AI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.topics.map((topic) => (
                      <tr key={topic.id} className="border-t border-[var(--color-line)]">
                        <td className="px-6 py-3">
                          <Link href={`/topics/${topic.id}`} className="font-medium text-[var(--color-ink)] hover:text-[var(--color-brand-500)]">
                            {topic.name}
                          </Link>
                          <p className="text-xs text-[var(--color-muted)]">{topic.status === "active" ? "Đang hoạt động" : "Đã lưu trữ"}</p>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-[var(--color-ink-2)]">{topic.source_count}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-[var(--color-ink-2)]">{topic.post_count}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-[var(--color-ink-2)]">{topic.pain_point_count}</td>
                        <td className="px-6 py-3 text-right tabular-nums text-[var(--color-ink-2)]">
                          {formatUsd(topic.usage.estimated_cost_usd)}
                          {topic.usage.has_unpriced_usage && "*"}
                        </td>
                      </tr>
                    ))}
                    {detail.topics.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-6 py-8 text-center text-sm text-[var(--color-muted)]">
                          Tài khoản chưa có chủ đề nào.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
