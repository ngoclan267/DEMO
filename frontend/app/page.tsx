"use client";

import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { MarketingNav } from "@/components/marketing/MarketingNav";
import { MarketingHero } from "@/components/marketing/MarketingHero";
import { SourceStrip } from "@/components/marketing/SourceStrip";
import { MarketingBenefits } from "@/components/marketing/MarketingBenefits";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { TrustSection } from "@/components/marketing/TrustSection";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || !user) return;
    router.replace("/dashboard");
  }, [loading, user, router]);

  if (loading || user) return null;

  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <MarketingNav />
      <main className="flex-1">
        <MarketingHero />
        <SourceStrip />
        <MarketingBenefits />
        <HowItWorks />
        <TrustSection />
        <section className="container-page pb-20">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.5 }}
            className="card-soft flex flex-col items-start gap-4 p-6 transition-shadow duration-300 hover:shadow-[0_16px_40px_rgba(11,18,32,0.08)] md:flex-row md:items-center md:justify-between md:p-8"
          >
            <div>
              <p className="eyebrow">Bắt đầu ngay</p>
              <p className="display-xl mt-1 text-[18px] font-semibold text-[var(--color-ink)] md:text-[20px]">
                Xem thử với tài khoản demo hoặc tạo chủ đề theo dõi của riêng bạn
              </p>
            </div>
            <Link href="/login" className="btn-primary shrink-0">
              Vào trang đăng nhập
            </Link>
          </motion.div>
        </section>
      </main>
      <footer className="border-t border-[var(--color-line)] py-6">
        <div className="container-page text-center text-xs text-[var(--color-muted)]">
          VigiBank — Giám sát phản hồi khách hàng ngân hàng theo thời gian thực
        </div>
      </footer>
    </div>
  );
}
