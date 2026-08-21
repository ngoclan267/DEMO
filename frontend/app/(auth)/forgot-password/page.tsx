"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-ink-2)]">
            Chúng tôi đã gửi liên kết đặt lại mật khẩu.Vui lòng kiểm tra hộp thư (kể cả mục spam).
          </p>
          <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
            Quay lại đăng nhập
          </Link>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ban@congty.com"
            />
          </div>
          <FieldError>{error}</FieldError>
          <Button type="submit" className="w-full" loading={loading}>
            Gửi liên kết đặt lại mật khẩu
          </Button>
        </form>
        <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
          Quay lại đăng nhập
        </Link>
      </CardBody>
    </Card>
  );
}

