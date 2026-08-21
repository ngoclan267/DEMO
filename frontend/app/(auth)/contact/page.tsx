"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

export default function ContactPage() {
  const [companyName, setCompanyName] = useState("");
  const [contactName, setContactName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/contact", {
        company_name: companyName,
        contact_name: contactName,
        email,
        phone: phone || null,
        message: message || null,
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gửi được yêu cầu, vui lòng thử lại");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-ink-2)]">
            Đã ghi nhận yêu cầu của <strong>{companyName}</strong>. Đội ngũ VigiBank sẽ liên hệ lại qua email{" "}
            <strong>{email}</strong> trong thời gian sớm nhất để khởi tạo không gian làm việc cho bạn.
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
        <p className="mb-5 text-sm text-[var(--color-muted)]">
          Mỗi ngân hàng là 1 workspace riêng, được đội ngũ VigiBank khởi tạo trực tiếp. Để lại thông tin, chúng tôi sẽ
          liên hệ tạo chủ đề và tài khoản làm việc cho doanh nghiệp bạn.
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="companyName">
              Tên doanh nghiệp <span className="text-[var(--color-rose)]">*</span>
            </Label>
            <Input
              id="companyName"
              required
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="VD: TPBank"
            />
          </div>

          <div>
            <Label htmlFor="contactName">
              Người liên hệ <span className="text-[var(--color-rose)]">*</span>
            </Label>
            <Input
              id="contactName"
              required
              autoComplete="name"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              placeholder="Nguyễn Văn A"
            />
          </div>

          <div>
            <Label htmlFor="email">
              Email <span className="text-[var(--color-rose)]">*</span>
            </Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ban@nganhang.com"
            />
          </div>

          <div>
            <Label htmlFor="phone">Điện thoại</Label>
            <Input
              id="phone"
              autoComplete="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="09xxxxxxxx"
            />
          </div>

          <div>
            <Label htmlFor="message">Lời nhắn</Label>
            <textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              placeholder="Nhu cầu theo dõi/nguồn dữ liệu quan tâm..."
              className="w-full rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-[14px] text-[var(--color-ink)] outline-none transition focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-500)]/20"
            />
          </div>

          <FieldError>{error}</FieldError>
          <Button type="submit" className="w-full" loading={loading}>
            Gửi yêu cầu tư vấn
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-[var(--color-muted)]">
          Đã có tài khoản?{" "}
          <Link href="/login" className="font-medium text-brand-600 hover:underline">
            Đăng nhập
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}
