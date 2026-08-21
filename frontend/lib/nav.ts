import {
  HouseLine,
  Hash,
  Heartbeat,
  Database,
  ArrowsLeftRight,
  Bell,
  ChartLineUp,
  GearSix,
  ShieldCheck,
} from "@phosphor-icons/react/dist/ssr";

export type NavItem = {
  href: string;
  label: string;
  Icon: typeof HouseLine;
  badge?: number;
};

/** Nhóm điều hướng dùng chung cho Sidebar (desktop) và Topbar (mobile drawer) — 1 nguồn duy nhất
 * để không lệch danh sách trang giữa 2 nơi hiển thị. */
export function getNavGroups(unreadCount: number): { title: string; items: NavItem[] }[] {
  return [
    {
      title: "Vận hành",
      items: [
        { href: "/dashboard", label: "Trang chủ", Icon: HouseLine },
        { href: "/topics", label: "Chủ đề", Icon: Hash },
        { href: "/pain-points", label: "Pain Point", Icon: Heartbeat },
      ],
    },
    {
      title: "Nguồn dữ liệu",
      items: [{ href: "/data-sources", label: "Nguồn dữ liệu", Icon: Database }],
    },
    {
      title: "Kích hoạt",
      items: [
        { href: "/compare", label: "So sánh giai đoạn", Icon: ArrowsLeftRight },
        { href: "/notifications", label: "Thông báo", Icon: Bell, badge: unreadCount },
        { href: "/reports", label: "Bản tin", Icon: ChartLineUp },
      ],
    },
  ];
}

/** Mục "Quản trị" chỉ hiện với tài khoản is_platform_admin — quyền quản trị TỔNG nền tảng, khác
 * hẳn is_owner của từng topic riêng lẻ. */
export function getSecondaryNav(isAdmin: boolean): NavItem[] {
  const items: NavItem[] = [{ href: "/settings", label: "Cài đặt", Icon: GearSix }];
  if (isAdmin) items.push({ href: "/admin", label: "Quản trị", Icon: ShieldCheck });
  return items;
}
