"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { Label, FieldError } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Button } from "@/components/ui/Button";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const passwordMismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: newPassword });
      setDone(true);
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đặt lại được mật khẩu");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-rose)]">Liên kết không hợp lệ — thiếu token đặt lại mật khẩu.</p>
          <Link href="/forgot-password" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
            Yêu cầu liên kết mới
          </Link>
        </CardBody>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-leaf)]">Đặt lại mật khẩu thành công. Đang chuyển tới trang đăng nhập...</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="newPassword">Mật khẩu mới</Label>
            <PasswordInput
              id="newPassword"
              required
              minLength={8}
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Tối thiểu 8 ký tự"
            />
          </div>
          <div>
            <Label htmlFor="confirmPassword">Xác nhận mật khẩu mới</Label>
            <PasswordInput
              id="confirmPassword"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Nhập lại mật khẩu mới"
              aria-invalid={passwordMismatch}
              className={passwordMismatch ? "border-[var(--color-rose)] focus:border-[var(--color-rose)] focus:ring-[var(--color-rose)]/15" : undefined}
            />
            {passwordMismatch && <p className="mt-1 text-xs text-[var(--color-rose)]">Mật khẩu xác nhận không khớp.</p>}
          </div>
          <FieldError>{error}</FieldError>
          <Button type="submit" className="w-full" loading={loading}>
            Đặt lại mật khẩu
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
