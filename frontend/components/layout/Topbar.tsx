"use client";

import { useEffect, useState, type ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { List, X, Bell, SignOut } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { AppNotification } from "@/lib/types";
import { getNavGroups, getSecondaryNav } from "@/lib/nav";
import { useAuth } from "@/lib/auth-context";

/** Chữ cái đầu để làm avatar khi người dùng chưa có ảnh đại diện — trùng logic Sidebar.tsx (desktop),
 * lặp lại ở đây vì 2 component độc lập, không đáng tách chung cho 1 hàm nhỏ. */
function initialsOf(nameOrEmail: string): string {
  const trimmed = nameOrEmail.trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return trimmed.slice(0, 2).toUpperCase();
}

/** Thanh trên mỗi trang: tiêu đề/mô tả/CTA riêng từng trang + chuông thông báo + menu điều hướng
 * cho mobile (Sidebar chỉ hiện ở md: trở lên, xem components/layout/Sidebar.tsx). */
export function Topbar({ title, subtitle, cta }: { title: string; subtitle?: string; cta?: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

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
    window.addEventListener("notifications-changed", refreshUnreadCount);
    return () => {
      cancelled = true;
      window.removeEventListener("notifications-changed", refreshUnreadCount);
    };
  }, [pathname]);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- đóng menu mobile khi đổi route, standard pattern
  useEffect(() => setMobileNavOpen(false), [pathname]);

  const groups = getNavGroups(unreadCount);
  const secondaryNav = getSecondaryNav(!!user?.is_platform_admin);

  function mobileLinkClass(active: boolean) {
    return clsx(
      "flex h-11 items-center justify-between rounded-md px-3 text-[13.5px] transition",
      active
        ? "bg-[var(--color-cream-2)] text-[var(--color-ink)]"
        : "text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-ink)]",
    );
  }

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-[var(--color-cream)]/90 backdrop-blur">
      <div className="flex h-[68px] items-center gap-3 px-5 md:px-8">
        <button
          type="button"
          onClick={() => setMobileNavOpen((v) => !v)}
          aria-label={mobileNavOpen ? "Đóng menu" : "Mở menu"}
          aria-expanded={mobileNavOpen}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-[var(--color-ink)] transition-colors hover:bg-[var(--color-cream-2)] md:hidden"
        >
          {mobileNavOpen ? <X size={18} /> : <List size={18} />}
        </button>

        <div className="min-w-0 flex-1">
          <p className="hidden text-[10.5px] font-medium tracking-[0.12em] text-[var(--color-muted)] uppercase md:block">
            Workspace
          </p>
          <h1 className="display-xl truncate text-[18px] font-semibold text-[var(--color-ink)] md:text-[22px]">{title}</h1>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Link
            href="/notifications"
            aria-label="Thông báo"
            className="relative flex h-9 w-9 items-center justify-center rounded-md text-[var(--color-ink)] transition-colors hover:bg-[var(--color-cream-2)]"
          >
            <Bell size={17} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-[var(--color-rose)]" />
            )}
          </Link>
        </div>
      </div>

      {/* CTA của từng trang (vd nút "Chỉnh sửa", link "Quản lý tài khoản" ở /admin) — TRƯỚC ĐÂY ẩn
          hẳn dưới sm: (640px), khiến chức năng chỉ hiện khi xoay ngang điện thoại (đúng lúc chiều
          rộng vượt 640px). Giờ luôn hiện ở mọi kích thước, kèm flex-wrap để nhiều nút tự xuống dòng
          thay vì tràn ngang. subtitle vẫn chỉ hiện ở md: trở lên (mô tả phụ, không phải chức năng). */}
      {(subtitle || cta) && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 pb-4 md:px-8">
          {subtitle && <p className="hidden text-[13.5px] text-[var(--color-muted)] md:block">{subtitle}</p>}
          {cta && <div className="flex flex-wrap items-center gap-2">{cta}</div>}
        </div>
      )}

      {mobileNavOpen && (
        <nav className="max-h-[calc(100dvh-68px)] overflow-y-auto border-t border-[var(--color-line)] px-5 py-4 md:hidden" aria-label="Điều hướng (di động)">
          <Link href="/dashboard" className="mb-4 flex items-center gap-2.5 px-2 text-[15px] font-semibold tracking-[-0.02em]">
            <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8" />
            VigiBank
          </Link>
          <div className="flex flex-col gap-4">
            {groups.map((group) => (
              <div key={group.title}>
                <p className="px-3 text-[10.5px] font-semibold tracking-[0.12em] text-[var(--color-muted)] uppercase">
                  {group.title}
                </p>
                <div className="mt-1.5 flex flex-col gap-1">
                  {group.items.map(({ href, label, Icon, badge }) => {
                    const active = pathname === href || pathname.startsWith(href + "/");
                    return (
                      <Link key={href} href={href} className={mobileLinkClass(active)}>
                        <span className="flex items-center gap-2.5">
                          <Icon size={16} weight={active ? "fill" : "regular"} />
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
                {secondaryNav.map(({ href, label, Icon }) => (
                  <Link key={href} href={href} className={mobileLinkClass(pathname.startsWith(href))}>
                    <span className="flex items-center gap-2.5">
                      <Icon size={16} />
                      {label}
                    </span>
                  </Link>
                ))}
              </div>
            </div>

            {/* Trước đây menu di động KHÔNG có mục này — trên điện thoại không có cách nào đăng
                xuất, vì cả Sidebar (chỉ hiện ở md: trở lên) lẫn menu này đều chưa từng render nút
                đăng xuất. Đặt cuối menu, tách hẳn bằng đường viền trên, cùng bố cục thẻ người dùng +
                nút đăng xuất y hệt Sidebar.tsx (desktop) để 2 nơi nhất quán. */}
            {user && (
              <div className="rounded-[14px] border border-[var(--color-line)] bg-[var(--color-cream-2)] p-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--color-brand-500)] text-[12px] font-semibold text-white">
                    {initialsOf(user.full_name || user.email)}
                  </span>
                  <div className="min-w-0 leading-tight">
                    <div className="truncate text-[12.5px] font-semibold">{user.full_name || user.email}</div>
                    <div className="truncate text-[10.5px] text-[var(--color-muted)]">{user.email}</div>
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
            )}
          </div>
        </nav>
      )}
    </header>
  );
}
