"use client";

import { useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { ShieldCheck } from "@phosphor-icons/react/dist/ssr";
import { api, ApiError } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { Label, FieldError } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Button } from "@/components/ui/Button";
import { Topbar } from "@/components/layout/Topbar";

type Strength = "weak" | "medium" | "strong";

/** Ước lượng độ mạnh mật khẩu đơn giản ở client — chỉ để gợi ý trực quan, quy tắc thật (tối thiểu
 * 8 ký tự) vẫn do backend kiểm tra (xem src/auth/schemas.py). */
function strengthOf(password: string): Strength | null {
  if (!password) return null;
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;
  if (score <= 2) return "weak";
  if (score <= 3) return "medium";
  return "strong";
}

const STRENGTH_META: Record<Strength, { label: string; className: string; bars: number }> = {
  weak: { label: "Yếu", className: "bg-[var(--color-rose)]", bars: 1 },
  medium: { label: "Trung bình", className: "bg-[var(--color-amber-glow)]", bars: 2 },
  strong: { label: "Mạnh", className: "bg-[var(--color-leaf)]", bars: 3 },
};

export default function SecuritySettingsPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  const strength = useMemo(() => strengthOf(newPassword), [newPassword]);

  async function onChangePassword(e: FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setPasswordMsg(null);
    setSavingPassword(true);
    try {
      await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
      setPasswordMsg("Đã đổi mật khẩu.");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Không đổi được mật khẩu");
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <div className="max-w-lg">
      <Topbar title="Bảo mật" subtitle="Đổi mật khẩu tài khoản" />

      <div className="pt-6">
        <Link href="/settings" className="text-sm text-[var(--color-muted)] hover:text-[var(--color-ink)]">
          ← Cài đặt
        </Link>

        <Card className="mt-4 p-6">
          <CardBody className="p-0">
            <form onSubmit={onChangePassword} className="space-y-4">
              <div>
                <Label htmlFor="currentPassword">Mật khẩu hiện tại</Label>
                <PasswordInput
                  id="currentPassword"
                  required
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="newPassword">Mật khẩu mới</Label>
                <PasswordInput
                  id="newPassword"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
                {strength && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className={`h-1.5 w-8 rounded-full ${
                            i < STRENGTH_META[strength].bars ? STRENGTH_META[strength].className : "bg-[var(--color-cream-2)]"
                          }`}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-[var(--color-muted)]">{STRENGTH_META[strength].label}</span>
                  </div>
                )}
              </div>
              <FieldError>{passwordError}</FieldError>
              {passwordMsg && <p className="text-sm text-[var(--color-leaf)]">{passwordMsg}</p>}
              <div className="flex gap-3">
                <Button type="submit" loading={savingPassword}>
                  Đổi mật khẩu
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>

        <div className="mt-4 flex gap-2.5 rounded-2xl border border-[var(--color-line)] bg-[var(--color-cream-2)] p-4">
          <ShieldCheck size={16} className="mt-0.5 shrink-0 text-[var(--color-muted)]" />
          <p className="text-[12.5px] text-[var(--color-muted)]">
            Đổi mật khẩu sẽ không đăng xuất các thiết bị khác đang đăng nhập. Nếu nghi ngờ tài khoản bị lộ, hãy đổi
            mật khẩu ngay và liên hệ quản trị viên.
          </p>
        </div>
      </div>
    </div>
  );
}
