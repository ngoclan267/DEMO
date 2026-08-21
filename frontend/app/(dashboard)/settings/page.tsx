"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Bell, CaretRight, ShieldCheck } from "@phosphor-icons/react/dist/ssr";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Topbar } from "@/components/layout/Topbar";

const NAV_ROWS = [
  {
    href: "/settings/notifications",
    label: "Cài đặt thông báo",
    description: "Bật/tắt và chọn kênh thông báo cho từng chủ đề",
    Icon: Bell,
  },
  {
    href: "/settings/security",
    label: "Bảo mật",
    description: "Đổi mật khẩu tài khoản",
    Icon: ShieldCheck,
  },
];

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [profileMsg, setProfileMsg] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    setProfileError(null);
    setProfileMsg(null);
    setSavingProfile(true);
    try {
      await api.patch("/auth/me", { full_name: fullName || null });
      await refreshUser();
      setProfileMsg("Đã lưu thông tin cá nhân.");
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : "Không lưu được");
    } finally {
      setSavingProfile(false);
    }
  }

  return (
    <div className="max-w-lg">
      <Topbar title="Cài đặt" />

      <div className="space-y-6 pt-6">
        <Card className="p-6">
          <CardHeader className="border-none p-0 pb-4">
            <CardTitle>Thông tin cá nhân</CardTitle>
          </CardHeader>
          <CardBody className="p-0">
            <form onSubmit={onSaveProfile} className="space-y-4">
              <div>
                <Label>Tên đăng nhập</Label>
                <Input value={user?.username || "(chưa đặt)"} disabled />
              </div>
              <div>
                <Label>Email</Label>
                <div className="flex items-center gap-2">
                  <Input value={user?.email || ""} disabled className="flex-1" />
                  {user && (
                    <span
                      className={
                        user.is_verified
                          ? "shrink-0 rounded-full bg-[var(--color-leaf)]/10 px-2.5 py-1 text-xs font-medium text-[var(--color-leaf)]"
                          : "shrink-0 rounded-full bg-[var(--color-amber-glow)]/10 px-2.5 py-1 text-xs font-medium text-[var(--color-amber-glow)]"
                      }
                    >
                      {user.is_verified ? "Đã xác thực" : "Chưa xác thực"}
                    </span>
                  )}
                </div>
              </div>
              <div>
                <Label htmlFor="fullName">Họ tên</Label>
                <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </div>
              <FieldError>{profileError}</FieldError>
              {profileMsg && <p className="text-sm text-[var(--color-leaf)]">{profileMsg}</p>}
              <Button type="submit" loading={savingProfile}>
                Lưu
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Khác</CardTitle>
          </CardHeader>
          <CardBody className="divide-y divide-[var(--color-line)] p-0">
            {NAV_ROWS.map(({ href, label, description, Icon }) => (
              <Link key={href} href={href} className="flex items-center gap-3 px-5 py-4 transition-colors hover:bg-[var(--color-cream-2)]/50">
                <Icon size={18} className="shrink-0 text-[var(--color-muted)]" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-[var(--color-ink)]">{label}</p>
                  <p className="text-xs text-[var(--color-muted)]">{description}</p>
                </div>
                <CaretRight size={14} className="shrink-0 text-[var(--color-muted)]" />
              </Link>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
