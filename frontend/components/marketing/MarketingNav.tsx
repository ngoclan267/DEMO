import Image from "next/image";
import Link from "next/link";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-[var(--color-cream)]/90 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 text-[15px] font-semibold tracking-[-0.02em]">
          <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8" priority />
          VigiBank
        </Link>
        {/* Nhảy nhanh tới từng phần trên chính trang này — ẩn ở mobile vì thanh header đã chật với
            2 nút Đăng nhập/Tạo tài khoản, mobile vẫn lướt bình thường được vì trang không quá dài. */}
        <nav aria-label="Chuyển nhanh tới nội dung" className="hidden items-center gap-6 md:flex">
          <a href="#loi-ich" className="text-[13.5px] font-medium text-[var(--color-ink-2)] hover:text-[var(--color-ink)]">
            Lợi ích
          </a>
          <a href="#cach-hoat-dong" className="text-[13.5px] font-medium text-[var(--color-ink-2)] hover:text-[var(--color-ink)]">
            Cách hoạt động
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="btn-ghost !h-9 !px-4">
            Đăng nhập
          </Link>
          <Link href="/contact" className="btn-primary !h-9 !px-4">
            Liên hệ tư vấn
          </Link>
        </div>
      </div>
    </header>
  );
}
