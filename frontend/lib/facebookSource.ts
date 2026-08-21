/** Xây dựng Source.config cho nguồn Facebook — dùng chung ở mọi nơi tạo nguồn (tạo chủ đề mới,
 * chỉnh sửa chủ đề, trang quản trị) để tránh 3 chỗ tự map khác nhau rồi lệch nhau theo thời gian.
 *
 * Trang (Page) và Nhóm (Group) công khai là 2 actor Apify KHÁC NHAU (dù cùng do Apify chính thức
 * duy trì) — field output cũng khác nhau (vd "likes" vs "likesCount"), xem
 * src/pipeline/collectors/facebook.py::DEFAULT_POST_FIELD_MAP / DEFAULT_GROUP_FIELD_MAP. Chọn sai
 * loại sẽ khiến actor chạy "thành công" (không lỗi) nhưng luôn trả về 0 kết quả. */
export type FacebookKind = "page" | "group";

export const FACEBOOK_PAGE_ACTOR_ID = "apify/facebook-posts-scraper";
export const FACEBOOK_GROUP_ACTOR_ID = "apify/facebook-groups-scraper";

const FACEBOOK_GROUP_FIELD_MAP = {
  id: "id",
  content: "text",
  posted_at: "time",
  url: "url",
  like_count: "likesCount",
  comment_count: "commentsCount",
  share_count: "sharesCount",
};

/** Tự nhận diện Trang/Nhóm từ chính URL đã nhập — URL dạng facebook.com/groups/... luôn là Nhóm,
 * còn lại coi là Trang. Dùng để tự chọn đúng loại ngay khi người dùng gõ/dán URL, tránh phải nhớ tự
 * bấm nút Trang/Nhóm (bấm sai loại thì actor chạy "thành công" nhưng luôn trả về 0 kết quả — không
 * báo lỗi rõ ràng nên rất dễ bị bỏ sót). */
export function detectFacebookKind(url: string): FacebookKind {
  return /facebook\.com\/groups\//i.test(url) ? "group" : "page";
}

export function buildFacebookSourceConfig(kind: FacebookKind, url: string, actorIdOverride?: string) {
  if (kind === "group") {
    return {
      post_actor_id: (actorIdOverride || FACEBOOK_GROUP_ACTOR_ID).trim(),
      post_field_map: FACEBOOK_GROUP_FIELD_MAP,
      post_run_input: { startUrls: [{ url }], resultsLimit: 50 },
    };
  }
  return {
    post_actor_id: (actorIdOverride || FACEBOOK_PAGE_ACTOR_ID).trim(),
    post_run_input: { startUrls: [{ url }], resultsLimit: 100 },
  };
}
