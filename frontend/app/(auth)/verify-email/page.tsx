"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

type VerifyState = "verifying" | "success" | "error";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const { verifyEmail } = useAuth();
  const [state, setState] = useState<VerifyState>(token ? "verifying" : "error");

  // Chỉ gọi verifyEmail một lần khi có token — không phải hành động do người dùng bấm, mà là hệ
  // quả của việc mở trang này (đọc token từ URL), nên đặt trong effect là đúng, không phải sự kiện.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    verifyEmail(token)
      .then(() => {
        if (!cancelled) {
          setState("success");
          setTimeout(() => router.push("/dashboard"), 1500);
        }
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ chạy lại khi token đổi, không phải khi verifyEmail/router đổi
  }, [token]);

  if (state === "verifying") {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-muted)]">Đang xác thực tài khoản...</p>
        </CardBody>
      </Card>
    );
  }

  if (state === "success") {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-leaf)]">Xác thực thành công. Đang chuyển vào hệ thống...</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <p className="text-sm text-[var(--color-rose)]">
          Liên kết không hợp lệ hoặc đã hết hạn. Nhập lại email để nhận liên kết xác thực mới.
        </p>
        <ResendForm />
        <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
          Quay lại đăng nhập
        </Link>
      </CardBody>
    </Card>
  );
}

function ResendForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/auth/resend-verification", { identifier: email });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <p className="mt-3 text-sm text-[var(--color-ink-2)]">
        Nếu email này có tài khoản chưa xác thực, chúng tôi đã gửi liên kết mới — vui lòng kiểm tra hộp thư.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-3 space-y-3">
      <div>
        <Label htmlFor="resendEmail">Email</Label>
        <Input
          id="resendEmail"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="ban@congty.com"
        />
      </div>
      <FieldError>{error}</FieldError>
      <Button type="submit" variant="secondary" loading={loading}>
        Gửi lại liên kết xác thực
      </Button>
    </form>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
