"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { motion } from "framer-motion";
import { Plus, SignOut } from "@phosphor-icons/react/dist/ssr";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { AppNotification } from "@/lib/types";
import { getNavGroups, getSecondaryNav } from "@/lib/nav";

/** Chữ cái đầu để làm avatar khi người dùng chưa có ảnh đại diện. */
function initialsOf(nameOrEmail: string): string {
  const trimmed = nameOrEmail.trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return trimmed.slice(0, 2).toUpperCase();
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    function refreshUnreadCount() {
      api
        .get<AppNotification[]>("/notifications?unread_only=true&limit=50")
        .then((items) => {
          if (!cancelled) setUnreadCount(items.length);
        })
        .catch(() => {});
    }
    refreshUnreadCount();
    // Trang /notifications tự đánh dấu đã đọc (từng cái hoặc "đọc tất cả") mà không đổi route —
    // bắn sự kiện để badge cập nhật ngay, không phải đợi điều hướng sang trang khác rồi quay lại.
    window.addEventListener("notifications-changed", refreshUnreadCount);
    return () => {
      cancelled = true;
      window.removeEventListener("notifications-changed", refreshUnreadCount);
    };
  }, [pathname]);

  const groups = getNavGroups(unreadCount);
  const secondaryNav = getSecondaryNav(!!user?.is_platform_admin);

  function linkClass(active: boolean) {
    return clsx(
      "group relative flex h-11 items-center justify-between rounded-md px-3 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-brand-500)]",
      active ? "text-[var(--color-ink)]" : "text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-ink)]",
    );
  }

  // Nền mục đang chọn trượt mượt giữa các link khi đổi trang (layoutId dùng chung — cùng cơ chế
  // "tab pill trượt" đã dùng ở SocialStreamPage) — thay vì bật/tắt màu nền đột ngột như trước, để
  // sidebar (luôn hiện trên mọi trang) mang đúng cảm giác chuyển động mượt của phần còn lại.
  function ActivePill() {
    return (
      <motion.span
        layoutId="sidebar-active-pill"
        className="absolute inset-0 -z-10 rounded-md bg-[var(--color-cream-2)]"
        transition={{ type: "spring", stiffness: 420, damping: 38 }}
      />
    );
  }

  const displayName = user?.full_name || user?.email || "";
  const initial = initialsOf(displayName);

  return (
    <aside className="sticky top-0 hidden h-[100dvh] w-[248px] shrink-0 border-r border-[var(--color-line)] bg-[var(--color-cream)] p-5 md:flex md:flex-col">
      <Link href="/dashboard" className="flex min-h-11 items-center gap-2.5 px-2 text-[15px] font-semibold tracking-[-0.02em]">
        <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8" priority />
        VigiBank
      </Link>

      {/* Chỉ platform admin tạo được chủ đề mới (kèm tài khoản chủ sở hữu, xem /admin và
          POST /topics/admin) — chủ sở hữu/nhân viên của 1 workspace không tự tạo thêm chủ đề. */}
      {user?.is_platform_admin && (
        <Link
          href="/admin"
          className="mt-6 flex h-11 items-center justify-center gap-2 rounded-md bg-[var(--color-ink)] px-4 text-[13.5px] font-semibold text-[var(--color-cream)] transition duration-300 hover:-translate-y-[1px] hover:bg-[var(--color-ink-2)] hover:shadow-[0_10px_24px_rgba(11,18,32,0.18)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-brand-500)]"
        >
          <Plus size={14} weight="bold" />
          Chủ đề mới
        </Link>
      )}

      <nav className="mt-6 flex flex-1 flex-col gap-5 overflow-y-auto text-[13.5px]" aria-label="Điều hướng chính">
        {groups.map((group) => (
          <div key={group.title}>
            <p className="px-3 text-[10.5px] font-semibold tracking-[0.12em] text-[var(--color-muted)] uppercase">
              {group.title}
            </p>
            <div className="mt-1.5 flex flex-col gap-1">
              {group.items.map(({ href, label, Icon, badge }) => {
                const active = pathname === href || pathname.startsWith(href + "/");
                return (
                  <Link key={href} href={href} className={linkClass(active)}>
                    {active && <ActivePill />}
                    <span className="flex items-center gap-2.5">
                      <Icon size={16} weight={active ? "fill" : "regular"} className={active ? "text-[var(--color-brand-700)]" : ""} />
                      {label}
                    </span>
                    {badge && badge > 0 ? (
                      <span className="rounded-full bg-[var(--color-brand-500)] px-2 py-0.5 text-[10.5px] font-semibold text-white">
                        {badge}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}

        <div>
          <p className="px-3 text-[10.5px] font-semibold tracking-[0.12em] text-[var(--color-muted)] uppercase">
            Không gian làm việc
          </p>
          <div className="mt-1.5 flex flex-col gap-1">
            {secondaryNav.map(({ href, label, Icon }) => {
              const active = pathname.startsWith(href);
              return (
                <Link key={href} href={href} className={linkClass(active)}>
                  {active && <ActivePill />}
                  <span className="flex items-center gap-2.5">
                    <Icon size={16} weight={active ? "fill" : "regular"} className={active ? "text-[var(--color-brand-700)]" : ""} />
                    {label}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      <div className="mt-auto rounded-[14px] border border-[var(--color-line)] bg-[var(--color-cream-2)] p-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--color-brand-500)] text-[12px] font-semibold text-white">
            {initial}
          </span>
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[12.5px] font-semibold">{displayName}</div>
            <div className="truncate text-[10.5px] text-[var(--color-muted)]">{user?.email}</div>
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="mt-3 flex h-11 w-full items-center justify-center gap-1.5 rounded-md border border-[var(--color-line)] bg-white text-[12px] font-medium text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-brand-500)]"
        >
          <SignOut size={11} /> Đăng xuất
        </button>
      </div>
    </aside>
  );
}
