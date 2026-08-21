"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "@/components/layout/Sidebar";
import { TrialQuotaBanner } from "@/components/dashboard/TrialQuotaBanner";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center" role="status" aria-live="polite">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-brand-700)] border-t-transparent" aria-hidden />
        <span className="sr-only">Đang tải</span>
      </div>
    );
  }

  return (
    <div className="flex min-h-[100dvh]">
      <Sidebar />
      {/* overflow-x-clip, KHÔNG dùng overflow-x-hidden — set overflow-x khác 'visible' mà overflow-y
          vẫn 'visible' thì trình duyệt tự ép overflow-y thành 'auto' (quy tắc CSSOM), biến main
          thành 1 scroll container mới khiến mọi Topbar (position: sticky) bên trong hết dính khi
          cuộn trang, dù window vẫn là nơi thực sự nhận sự kiện cuộn. clip không có tác dụng phụ này. */}
      <main className="flex-1 overflow-x-clip">
        {/* Topbar được từng trang tự render (title/subtitle/CTA riêng) — xem Topics/Pain Point/...
            page.tsx. Trang nào CHƯA lên Topbar (chưa tới giai đoạn reskin) vẫn giữ tiêu đề <h1>
            riêng của nó bên trong container-page. */}
        <div className="container-page py-8">
          <TrialQuotaBanner />
          {children}
        </div>
      </main>
    </div>
  );
}
