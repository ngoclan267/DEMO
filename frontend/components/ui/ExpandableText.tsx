"use client";

import { useState } from "react";
import { splitIntoParagraphs, truncateParagraphs } from "@/lib/textFormat";

// Nội dung ngắn hơn ngưỡng này hiện trọn vẹn luôn, không có nút "Xem thêm" (đa số comment/review
// bình thường) — chỉ nội dung dài (bài viết trang chủ, tài liệu đối chiếu...) mới cần thu gọn.
const COLLAPSE_CHAR_THRESHOLD = 480;

/** Hiển thị nội dung text thô (crawl được, không có cấu trúc đoạn văn thật) theo dạng dễ đọc hơn:
 * tự tách thành nhiều đoạn ngắn theo câu, giới hạn độ rộng dòng (measure) cho vừa tầm mắt, và thu
 * gọn nội dung dài kèm nút "Xem thêm/Thu gọn" thay vì dồn hết thành 1 khối chữ ngay lập tức. */
export function ExpandableText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);

  if (!text.trim()) return null;

  const paragraphs = splitIntoParagraphs(text);
  const isLong = text.length > COLLAPSE_CHAR_THRESHOLD;
  const visible = expanded || !isLong ? paragraphs : truncateParagraphs(paragraphs, COLLAPSE_CHAR_THRESHOLD);

  return (
    <div>
      <div className="max-w-[68ch] space-y-2.5">
        {visible.map((p, i) => (
          <p key={i} className="text-sm leading-7 text-[var(--color-ink-2)]">
            {p}
            {!expanded && isLong && i === visible.length - 1 && <span className="text-[var(--color-muted)]">…</span>}
          </p>
        ))}
      </div>
      {isLong && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded((v) => !v);
          }}
          className="mt-1.5 text-xs font-medium text-[var(--color-brand-600)] hover:underline"
        >
          {expanded ? "Thu gọn ▲" : "Xem thêm ▾"}
        </button>
      )}
    </div>
  );
}
