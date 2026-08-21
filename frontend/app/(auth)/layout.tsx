"use client";

import type { ReactNode } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";

// Trang /login tự dựng bố cục 2 cột riêng (panel minh hoạ + form, xem app/(auth)/login/page.tsx) để
// khớp độ hoành tráng với trang giới thiệu — cần khung RỘNG hơn nhiều so với 1 form đơn giản như
// register/forgot-password/reset-password/verify-email/billing-return, nên tách nhánh bố cục ở đây
// theo pathname thay vì nới rộng khung MẶC ĐỊNH cho mọi trang xác thực (sẽ làm các form đơn giản
// khác trông lạc lõng giữa khoảng trắng thừa).
export default function AuthLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  const decor = (
    <>
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 h-72 w-72 rounded-full bg-[var(--color-brand-500)]/12 blur-[100px]"
        animate={{ x: [0, 16, 0], y: [0, 10, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -right-24 bottom-[-6rem] h-80 w-80 rounded-full bg-[var(--color-sky)]/12 blur-[110px]"
        animate={{ x: [0, -14, 0], y: [0, -12, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut", delay: 1 }}
      />
    </>
  );

  if (isLogin) {
    return (
      <div className="relative flex min-h-screen flex-1 items-center justify-center overflow-hidden px-4 py-8">
        {decor}
        {children}
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-1 items-center justify-center overflow-hidden px-4">
      {decor}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="relative w-full max-w-sm"
      >
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="mb-8 flex flex-col items-center text-center"
        >
          <Image src="/logo.svg" alt="" width={44} height={44} className="mb-3 h-11 w-11" priority />
          <h1 className="display-xl text-2xl font-semibold text-[var(--color-ink)]">VigiBank</h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">Giám sát phản hồi khách hàng theo thời gian thực</p>
        </motion.div>
        {children}
      </motion.div>
    </div>
  );
}
