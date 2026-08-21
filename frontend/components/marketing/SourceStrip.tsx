"use client";

import { motion } from "framer-motion";
import { AppStoreLogo, Bank, FacebookLogo, GooglePlayLogo, Newspaper, TiktokLogo } from "@phosphor-icons/react/dist/ssr";

// Đúng 6 loại nguồn dự án THẬT SỰ hỗ trợ thu thập (xem SourceType trong src/db/models.py /
// frontend/lib/socialPlatforms.ts) — không liệt kê nguồn chưa hỗ trợ (vd LinkedIn).
const SOURCES = [
  { label: "Google Play", icon: GooglePlayLogo },
  { label: "App Store", icon: AppStoreLogo },
  { label: "Facebook", icon: FacebookLogo },
  { label: "TikTok", icon: TiktokLogo },
  { label: "Website ngân hàng", icon: Bank },
  { label: "Báo chí / Tin tức", icon: Newspaper },
];

export function SourceStrip() {
  return (
    <section className="container-page pb-16 md:pb-20">
      <div className="mx-auto max-w-3xl text-center">
        <p className="text-[11px] font-semibold tracking-[0.2em] text-[var(--color-muted)] uppercase">
          Hợp nhất dữ liệu đang phân mảnh trên nhiều kênh
        </p>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2.5">
        {SOURCES.map(({ label, icon: Icon }, index) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.35, delay: index * 0.06 }}
            className="chip transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-brand-500)]/30 hover:text-[var(--color-brand-700)]"
          >
            <Icon size={15} weight="bold" />
            {label}
          </motion.div>
        ))}
      </div>
    </section>
  );
}
