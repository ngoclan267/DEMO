"use client";

import { useState, type FormEvent } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Bank, ShieldCheck, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Button } from "@/components/ui/Button";

// Tài khoản demo công khai, chủ đích lộ sẵn ở giao diện — KHÔNG phải bí mật. Tạo bằng
// scripts/seed_demo_accounts.py. Mỗi ngân hàng 1 tài khoản làm việc riêng, minh hoạ đăng nhập theo
// workspace + mời thêm thành viên (chủ sở hữu topic = admin của riêng workspace đó, xem
// /topics/[id]/members). KHÔNG còn tài khoản quản trị demo ở đây — quyền quản trị TỔNG nền tảng
// giờ chỉ có ở 1 tài khoản thật duy nhất, không lộ sẵn mật khẩu công khai như trước.
const DEMO_ACCOUNTS = [
  { label: "SHB Saha", identifier: "demo.shb@vigibank-demo.com", password: "Demo12345!", Icon: Bank },
  { label: "TPBank", identifier: "demo.tpbank@vigibank-demo.com", password: "Demo12345!", Icon: Bank },
];

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // 403 nghĩa là mật khẩu đúng nhưng tài khoản chưa xác thực email (xem routes_auth.login) —
  // khác biệt hẳn với sai mật khẩu (401), nên cần chỗ để bấm gửi lại email ngay tại đây.
  const [unverified, setUnverified] = useState(false);
  const [resent, setResent] = useState(false);
  const [resending, setResending] = useState(false);

  async function attemptLogin(loginIdentifier: string, loginPassword: string) {
    setError(null);
    setUnverified(false);
    setResent(false);
    setLoading(true);
    try {
      await login(loginIdentifier, loginPassword);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setUnverified(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Đăng nhập thất bại");
      }
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    attemptLogin(identifier, password);
  }

  // Đăng nhập thẳng vào vùng làm việc của ngân hàng đó luôn, không chỉ điền sẵn ô rồi bắt bấm thêm
  // lần nữa — vẫn cập nhật 2 ô input để người dùng thấy tài khoản/mật khẩu vừa dùng.
  function loginAsDemo(account: (typeof DEMO_ACCOUNTS)[number]) {
    setIdentifier(account.identifier);
    setPassword(account.password);
    attemptLogin(account.identifier, account.password);
  }

  async function onResend() {
    setResending(true);
    try {
      await api.post("/auth/resend-verification", { identifier });
      setResent(true);
    } catch {
      // resend-verification không tiết lộ lỗi cụ thể (xem backend) — coi như đã gửi để không lộ
      // thông tin tài khoản.
      setResent(true);
    } finally {
      setResending(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="grid w-full max-w-[960px] overflow-hidden rounded-[24px] border border-[var(--color-line)] bg-white shadow-[0_30px_80px_rgba(11,18,32,0.14)] lg:grid-cols-[1fr_420px]"
    >
      {/* Panel trái — chỉ hiện ở màn rộng, cùng ngôn ngữ thị giác với hero trang giới thiệu (thẻ
          mockup + thẻ cảnh báo nổi) để đăng nhập không còn là 1 form rời rạc, lạc tông. */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-[linear-gradient(150deg,var(--color-brand-50)_0%,var(--color-cream-2)_45%,#ffffff_100%)] p-9 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-16 -right-16 h-56 w-56 rounded-full bg-[var(--color-brand-500)]/12 blur-[80px]"
        />

        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="relative flex items-center gap-2.5"
        >
          <Image src="/logo.svg" alt="" width={36} height={36} className="h-9 w-9" priority />
          <span className="text-[15px] font-semibold tracking-[-0.02em] text-[var(--color-ink)]">VigiBank</span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.18 }}
          className="relative"
        >
          <p className="eyebrow">Command center cho ngân hàng</p>
          <h1 className="display-xl mt-2 text-[26px] font-semibold leading-tight text-[var(--color-ink)]">
            Lắng nghe phản hồi, gom vấn đề, truy về nguồn gốc.
          </h1>
          <p className="mt-3 max-w-[38ch] text-[13.5px] leading-relaxed text-[var(--color-muted)]">
            Mỗi ngân hàng là 1 workspace riêng biệt — dữ liệu và pain point của bạn không lẫn với tổ chức khác.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="relative overflow-hidden rounded-[16px] border border-[var(--color-line)] bg-white/90 p-4 shadow-[0_16px_40px_rgba(11,18,32,0.08)] backdrop-blur"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10.5px] font-medium tracking-[0.1em] text-[var(--color-muted)] uppercase">Pain point đáng chú ý</p>
              <p className="mt-1 text-[13px] font-semibold text-[var(--color-ink)]">Lỗi đăng nhập sau cập nhật 3.4.7</p>
            </div>
            <span className="chip shrink-0 !py-0.5 !text-[11px]">Nghiêm trọng</span>
          </div>
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: [6, 0, -4, 0] }}
            transition={{ opacity: { duration: 0.4, delay: 0.6 }, y: { duration: 0.4, delay: 0.6, times: [0, 0.4, 0.7, 1] } }}
            className="mt-3 flex items-center gap-2 rounded-xl border border-[var(--color-rose)]/20 bg-[var(--color-rose)]/8 px-2.5 py-2"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-rose)]/15 text-[var(--color-rose)]">
              <WarningCircle size={13} weight="fill" />
            </span>
            <p className="text-[11px] font-medium text-[var(--color-ink-2)]">Vượt ngưỡng cảnh báo — 32 phản hồi/24h</p>
          </motion.div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.45 }}
          className="relative flex items-center gap-2 text-[11.5px] text-[var(--color-muted)]"
        >
          <ShieldCheck size={15} className="text-[var(--color-leaf)]" />
          Dữ liệu cô lập riêng theo từng workspace
        </motion.div>
      </section>

      {/* Panel phải — form đăng nhập thật. */}
      <div className="p-6 sm:p-8">
        <div className="mb-6 flex flex-col items-center text-center lg:hidden">
          <Image src="/logo.svg" alt="" width={44} height={44} className="mb-3 h-11 w-11" priority />
          <h1 className="display-xl text-2xl font-semibold text-[var(--color-ink)]">VigiBank</h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">Giám sát phản hồi khách hàng theo thời gian thực</p>
        </div>

        <p className="mb-2.5 text-[12px] font-medium tracking-[0.08em] text-[var(--color-muted)] uppercase">Dùng thử ngay</p>
        <div className="mb-5 grid grid-cols-2 gap-2">
          {DEMO_ACCOUNTS.map((account, index) => (
            <motion.button
              key={account.identifier}
              type="button"
              disabled={loading}
              onClick={() => loginAsDemo(account)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.15 + index * 0.06 }}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              className="flex flex-col items-center justify-center gap-1 rounded-xl border border-[var(--color-line)] bg-white px-2 py-2.5 text-[12px] font-medium text-[var(--color-ink-2)] transition-colors hover:border-[var(--color-bone)] hover:bg-[var(--color-cream-2)]/50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <account.Icon size={15} className="text-[var(--color-muted)]" />
              {account.label}
            </motion.button>
          ))}
        </div>
        <p className="mb-5 text-center text-xs text-[var(--color-muted)]">— hoặc đăng nhập bằng tài khoản của bạn —</p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="identifier">Email hoặc tên đăng nhập</Label>
            <Input
              id="identifier"
              required
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="ban@congty.com"
            />
          </div>
          <div>
            <Label htmlFor="password">Mật khẩu</Label>
            <PasswordInput
              id="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          <FieldError>{error}</FieldError>

          <AnimatePresence mode="wait">
            {unverified &&
              (resent ? (
                <motion.p
                  key="resent"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className="text-sm text-[var(--color-leaf)]"
                >
                  Đã gửi lại email xác thực — vui lòng kiểm tra hộp thư.
                </motion.p>
              ) : (
                <motion.div
                  key="unverified"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="rounded-2xl border border-[var(--color-amber-glow)]/25 bg-[var(--color-amber-glow)]/8 px-3 py-2.5 text-sm text-[var(--color-ink-2)]"
                >
                  <p>Tài khoản chưa được xác thực email.</p>
                  <button
                    type="button"
                    onClick={onResend}
                    disabled={resending}
                    className="mt-1 font-medium text-brand-700 hover:underline disabled:opacity-60"
                  >
                    {resending ? "Đang gửi..." : "Gửi lại email xác thực"}
                  </button>
                </motion.div>
              ))}
          </AnimatePresence>

          <Button type="submit" className="w-full" loading={loading}>
            Đăng nhập
          </Button>
        </form>
        <div className="mt-4 flex items-center justify-between text-sm">
          <Link href="/forgot-password" className="text-brand-600 hover:underline">
            Quên mật khẩu?
          </Link>
          <Link href="/contact" className="text-brand-600 hover:underline">
            Liên hệ tư vấn
          </Link>
        </div>
      </div>
    </motion.div>
  );
}
