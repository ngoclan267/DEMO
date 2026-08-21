/**
 * Hiển thị ngày của 1 phản hồi — ưu tiên `postedAt` (ngày khách thực sự đăng). Khi nguồn không
 * cung cấp được ngày đăng gốc (posted_at NULL — hiện không xảy ra với Google Play/App Store,
 * nhưng vẫn có thể xảy ra với nguồn mới sau này hoặc khi API nguồn đổi định dạng), rơi về
 * `collectedAt` kèm icon + tooltip để không đọc nhầm là ngày đăng thật — nhất là khi so trên biểu
 * đồ xu hướng.
 */
export function PostDate({ postedAt, collectedAt }: { postedAt: string | null; collectedAt: string | null }) {
  const date = postedAt ?? collectedAt;
  if (!date) return null;

  const formatted = new Date(date).toLocaleDateString("vi-VN");

  if (postedAt) {
    return <span className="text-xs text-[var(--color-muted)]">{formatted}</span>;
  }

  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-[var(--color-muted)]"
      title="Không rõ ngày đăng gốc — đây là ngày hệ thống thu thập được phản hồi này."
    >
      <span aria-hidden>⏱</span>
      {formatted}
    </span>
  );
}
