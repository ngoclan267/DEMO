"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, WarningCircle } from "@phosphor-icons/react/dist/ssr";

export function MarketingHero() {
  return (
    <section className="container-page relative grid grid-cols-1 items-center gap-10 overflow-hidden pt-14 pb-16 md:pt-20 md:pb-24 lg:grid-cols-[1fr_0.9fr] lg:gap-14">
      {/* Khối màu nền mờ trang trí — dùng ĐÚNG token màu sẵn có (brand/sky), không thêm màu mới. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 -left-32 h-80 w-80 rounded-full bg-[var(--color-brand-500)]/10 blur-[100px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute top-32 -right-24 h-96 w-96 rounded-full bg-[var(--color-sky)]/10 blur-[110px]"
      />

      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
        className="relative max-w-[42rem]"
      >
        <p className="eyebrow">Giám sát & phân tích phản hồi khách hàng ngân hàng</p>
        <h1 className="display-xl mt-3 text-[34px] font-semibold text-[var(--color-ink)] sm:text-[42px] md:text-[52px]">
          Phát hiện pain point trước khi nó thành{" "}
          <span className="text-[var(--color-brand-700)]">khủng hoảng truyền thông</span>
        </h1>
        <p className="mt-5 max-w-[52ch] text-[15.5px] leading-relaxed text-[var(--color-muted)] md:text-[16.5px]">
          Tự động thu thập đánh giá từ Google Play, App Store, Facebook, TikTok và website ngân hàng, dùng AI phân
          loại và đối chiếu với văn bản chính thức, gom thành pain point khi đủ ngưỡng cảnh báo — để đội ngũ vận
          hành xử lý kịp thời trước khi lan rộng.
        </p>
        <div className="mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <Link href="/login" className="btn-primary group">
            Đăng nhập
            <ArrowUpRight size={16} weight="bold" className="ml-1.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
          <Link href="/contact" className="btn-ghost">
            Liên hệ tư vấn
          </Link>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
        className="relative min-w-0"
      >
        <div className="overflow-hidden rounded-[16px] border border-[var(--color-line)] bg-white shadow-[0_24px_60px_rgba(11,18,32,0.10)] transition-shadow duration-500 hover:shadow-[0_28px_70px_rgba(11,18,32,0.14)]">
          <div className="flex items-center gap-3 border-b border-[var(--color-line)] px-4 py-3 text-[12px] text-[var(--color-muted)]">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-rose)]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-amber-glow)]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-leaf)]" />
            <span className="ml-2 truncate font-mono text-[11px] tracking-[0.12em] uppercase">/dashboard</span>
          </div>
          <div className="grid grid-cols-3 divide-x divide-[var(--color-line)] border-b border-[var(--color-line)]">
            <HeroStat label="Chủ đề" value="4" />
            <HeroStat label="Pain point mở" value="12" tone="danger" />
            <HeroStat label="Quá hạn" value="2" tone="danger" />
          </div>
          <div className="p-4 md:p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] font-medium tracking-[0.12em] text-[var(--color-muted)] uppercase">Pain point đáng chú ý</p>
                <p className="mt-1.5 text-[13.5px] font-semibold text-[var(--color-ink)]">Lỗi đăng nhập sau cập nhật 3.4.7</p>
              </div>
              <span className="chip shrink-0">Nghiêm trọng</span>
            </div>
            <svg viewBox="0 0 100 30" className="mt-5 h-16 w-full" preserveAspectRatio="none" aria-hidden>
              <defs>
                <linearGradient id="hero-grad" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#c81e1e" stopOpacity="0.22" />
                  <stop offset="100%" stopColor="#c81e1e" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0,24 L14,20 L28,21 L42,15 L56,16 L70,9 L84,10 L100,3 L100,30 L0,30 Z" fill="url(#hero-grad)" />
              <motion.path
                d="M0,24 L14,20 L28,21 L42,15 L56,16 L70,9 L84,10 L100,3"
                fill="none"
                stroke="var(--color-rose)"
                strokeWidth="1.6"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1.4, delay: 0.5, ease: "easeInOut" }}
              />
            </svg>
          </div>
        </div>

        {/* Thẻ nổi minh hoạ cảnh báo real-time — dùng đúng khái niệm "ngưỡng cảnh báo" của dự án
            (Topic.alert_threshold), không phải trang trí vô nghĩa. */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: [10, 0, -6, 0] }}
          transition={{
            opacity: { duration: 0.5, delay: 0.9 },
            y: { duration: 0.5, delay: 0.9, times: [0, 0.3, 0.65, 1] },
          }}
          className="absolute -bottom-6 -left-3 hidden items-center gap-3 rounded-[16px] border border-[var(--color-line)] bg-white px-4 py-3 shadow-[0_16px_40px_rgba(11,18,32,0.14)] sm:flex lg:-left-8"
        >
          <motion.span
            animate={{ y: [0, -3, 0] }}
            transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut", delay: 1.4 }}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--color-rose)]/10 text-[var(--color-rose)]"
          >
            <WarningCircle size={18} weight="fill" />
          </motion.span>
          <div>
            <p className="text-[11.5px] font-semibold text-[var(--color-ink)]">Vượt ngưỡng cảnh báo</p>
            <p className="text-[10.5px] text-[var(--color-muted)]">32 phản hồi trong 24 giờ</p>
          </div>
        </motion.div>
      </motion.div>
    </section>
  );
}

function HeroStat({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <div className="bg-[var(--color-cream)] p-2.5 sm:p-3.5 md:p-4">
      <p className="truncate text-[9.5px] font-medium tracking-[0.06em] text-[var(--color-muted)] uppercase sm:text-[10.5px] sm:tracking-[0.1em]">
        {label}
      </p>
      <p className={`display-xl mt-1.5 text-[22px] font-semibold sm:text-[26px] md:text-[30px] ${tone === "danger" ? "text-[var(--color-rose)]" : "text-[var(--color-ink)]"}`}>
        {value}
      </p>
    </div>
  );
}
