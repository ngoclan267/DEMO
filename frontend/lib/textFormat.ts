/** Nội dung crawl thô (Facebook, website ngân hàng) thường là 1 khối text liền không xuống dòng —
 * BeautifulSoup/Apify nối các đoạn <p> lại bằng dấu cách khi trích xuất (xem
 * src/pipeline/collectors/bank_website.py::_extract_main_text), nên không có \n\n thật để dựa vào.
 * Tách theo CÂU rồi gom nhóm lại thành đoạn để dễ đọc hơn — đây KHÔNG phải phát hiện đoạn văn thật
 * (dữ liệu gốc không giữ thông tin đó), chỉ là tạo chỗ ngắt mắt đọc hợp lý. */
const SENTENCES_PER_PARAGRAPH = 3;

export function splitIntoParagraphs(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];

  // Nội dung gốc ĐÃ có xuống dòng thật (vd bình luận Facebook nhiều dòng) thì tôn trọng luôn,
  // không tự ý gộp lại theo câu.
  if (/\n\s*\n/.test(trimmed)) {
    return trimmed
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean);
  }

  const sentences = trimmed
    .split(/(?<=[.!?…])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (sentences.length <= 1) return [trimmed];

  const paragraphs: string[] = [];
  for (let i = 0; i < sentences.length; i += SENTENCES_PER_PARAGRAPH) {
    paragraphs.push(sentences.slice(i, i + SENTENCES_PER_PARAGRAPH).join(" "));
  }
  return paragraphs;
}

/** Cắt danh sách đoạn văn tới gần đúng `charLimit` ký tự, LUÔN giữ nguyên vẹn từng đoạn (không cắt
 * giữa câu) — dùng cho chế độ "thu gọn". Luôn trả về ít nhất 1 đoạn dù đoạn đầu đã vượt charLimit. */
export function truncateParagraphs(paragraphs: string[], charLimit: number): string[] {
  const result: string[] = [];
  let total = 0;
  for (const p of paragraphs) {
    result.push(p);
    total += p.length;
    if (total >= charLimit) break;
  }
  return result;
}
