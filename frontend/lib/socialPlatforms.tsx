import type { SocialPlatformConfig } from "@/components/social/SocialStreamPage";

/** Cấu hình DÙNG CHUNG cho mọi nơi hiển thị bài viết mạng xã hội (Facebook, TikTok) — trang luồng
 * riêng của từng nền tảng (xem topics/[id]/facebook, topics/[id]/tiktok) VÀ trang chi tiết pain
 * point (xem topics/[id]/pain-points/[painPointId]) đều dùng chung 1 nguồn để không lệch nhãn/link
 * khi thêm nền tảng mới hoặc đổi chữ. */
export const FACEBOOK_PLATFORM_CONFIG: SocialPlatformConfig = {
  sourceType: "facebook",
  pageTitle: "Luồng Facebook",
  cardTitle: "Bài viết Facebook",
  dialogTitle: "Bài viết Facebook",
  viewOnPlatformLabel: "Xem trên Facebook",
  description: (
    <>
      Bài viết và bình luận thu thập từ Facebook — tách riêng khỏi luồng phản hồi chung vì có cấu trúc bài
      viết/bình luận và số liệu tương tác riêng. Vẫn được tính vào thống kê tổng của chủ đề (cảm xúc, mức độ nghiêm
      trọng, pain point...) như mọi nguồn khác.
    </>
  ),
};

export const TIKTOK_PLATFORM_CONFIG: SocialPlatformConfig = {
  sourceType: "tiktok",
  pageTitle: "Luồng TikTok",
  cardTitle: "Video TikTok",
  dialogTitle: "Video TikTok",
  viewOnPlatformLabel: "Xem trên TikTok",
  description: (
    <>
      Video và bình luận thu thập từ TikTok — tách riêng khỏi luồng phản hồi chung vì có cấu trúc video/bình luận và
      số liệu tương tác riêng. Vẫn được tính vào thống kê tổng của chủ đề (cảm xúc, mức độ nghiêm trọng, pain
      point...) như mọi nguồn khác.
    </>
  ),
};

/** Nguồn nào có cấu trúc bài viết/comment + dialog riêng (khác nguồn "phẳng" như Google Play/App
 * Store, dùng PostDetailModal thường) — trang pain point tra map này để quyết định mở dialog nào
 * khi bấm vào 1 phản hồi (xem PainPointDrillDownPage). */
export const SOCIAL_PLATFORM_CONFIG_BY_SOURCE_TYPE: Record<string, SocialPlatformConfig> = {
  facebook: FACEBOOK_PLATFORM_CONFIG,
  tiktok: TIKTOK_PLATFORM_CONFIG,
};
