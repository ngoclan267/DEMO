/** Xây dựng Source.config cho nguồn TikTok — dùng chung ở mọi nơi tạo nguồn (tạo chủ đề mới,
 * chỉnh sửa chủ đề, trang quản trị), giống lib/facebookSource.ts. Không có khái niệm Trang/Nhóm
 * như Facebook — TikTok chỉ có 1 loại hồ sơ công khai. */
export const TIKTOK_POST_ACTOR_ID = "clockworks/tiktok-scraper";

/** Chấp nhận URL hồ sơ đầy đủ (https://www.tiktok.com/@tpbank) hoặc chỉ tên (tpbank, @tpbank) —
 * chuẩn hoá về đúng username trần mà actor cần trong "profiles". */
export function normalizeTikTokHandle(input: string): string {
  const trimmed = input.trim();
  const match = trimmed.match(/tiktok\.com\/@([^/?#]+)/i);
  if (match) return match[1];
  return trimmed.replace(/^@/, "");
}

export function buildTikTokSourceConfig(handle: string, actorIdOverride?: string) {
  return {
    post_actor_id: (actorIdOverride || TIKTOK_POST_ACTOR_ID).trim(),
    post_run_input: { profiles: [normalizeTikTokHandle(handle)], resultsPerPage: 50 },
  };
}
