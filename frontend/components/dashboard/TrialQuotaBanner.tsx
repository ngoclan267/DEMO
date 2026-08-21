"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

/** Banner mời nâng cấp cho tài khoản dùng thử — 2 tầng ĐỘC LẬP, không khoá đăng nhập/dashboard ở
 * cả 2 trường hợp (chỉ tạm dừng PHÂN TÍCH thêm, xem _trial_users_blocked_from_analysis trong
 * src/analysis/runner.py):
 *
 *   1. HẾT HẲN (user.trial_expired = hết hạn THỜI GIAN hoặc hết trần TRỌN ĐỜI) — tạm dừng phân
 *      tích VĨNH VIỄN tới khi nâng cấp. Ưu tiên hiển thị nhánh này TRƯỚC (return sớm), vì đã hết
 *      hẳn thì banner "hết trần hôm nay" bên dưới không còn ý nghĩa gì thêm.
 *   2. HẾT TRẦN NGÀY (còn hạn dùng thử, nhưng chạm 1 trong 2 trần NGÀY độc lập nhau) — chỉ tạm dừng
 *      tới ngày mai:
 *      - PHÂN TÍCH (trial_daily_call_count >= trial_daily_call_limit) — tạm dừng Classification/
 *        Verification/Consensus cho post mới. Dữ liệu vẫn được THU THẬP bình thường nếu trần này
 *        chưa chạm.
 *      - THU THẬP (trial_daily_crawl_count >= trial_daily_crawl_limit) — tạm dừng Collector Agent
 *        lấy thêm bản ghi mới, xem _trial_daily_crawl_remaining trong src/pipeline/runner.py.
 *
 * Số hiển thị CHO NGƯỜI DÙNG là trial_daily_responses_analyzed (đếm Prediction thật — số PHẢN HỒI),
 * KHÔNG phải trial_daily_call_count (đếm lượt gọi LLM thô — 1 phản hồi tốn 2-3 lượt) — hiển thị
 * thẳng call_count kèm chữ "phân tích" từng khiến người dùng hiểu nhầm đó là số phản hồi. */
export function TrialQuotaBanner() {
  const { user } = useAuth();
  if (!user) return null;

  if (user.trial_expired) {
    return (
      <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-[var(--color-rose)]/30 bg-[var(--color-rose)]/8 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[13.5px] font-medium text-[var(--color-ink)]">Tài khoản dùng thử đã hết hạn.</p>
          <p className="mt-0.5 text-[12.5px] text-[var(--color-ink-2)]">
            Dữ liệu và pain point cũ vẫn xem/xử lý được bình thường — chỉ phản hồi MỚI sẽ không được phân tích thêm cho
            tới khi nâng cấp.
          </p>
        </div>
        <Link
          href="/billing/upgrade"
          className="inline-flex h-10 shrink-0 items-center justify-center rounded-md bg-[var(--color-brand-500)] px-4 text-[13.5px] font-semibold text-white transition-colors hover:bg-[var(--color-brand-600)]"
        >
          Nâng cấp ngay
        </Link>
      </div>
    );
  }

  const analysisCapped =
    user.trial_daily_call_limit !== null &&
    user.trial_daily_call_count !== null &&
    user.trial_daily_call_count >= user.trial_daily_call_limit;
  const crawlCapped =
    user.trial_daily_crawl_limit !== null &&
    user.trial_daily_crawl_count !== null &&
    user.trial_daily_crawl_count >= user.trial_daily_crawl_limit;

  if (!analysisCapped && !crawlCapped) return null;

  const responses = user.trial_daily_responses_analyzed;
  const crawlCount = user.trial_daily_crawl_count;
  const crawlLimit = user.trial_daily_crawl_limit;

  let headline: string;
  let detail: string;
  if (analysisCapped && crawlCapped) {
    headline = `Tài khoản dùng thử đã chạm CẢ 2 giới hạn miễn phí hôm nay: ${responses?.toLocaleString("vi-VN")} phản hồi đã phân tích, ${crawlCount?.toLocaleString("vi-VN")} bản ghi đã thu thập.`;
    detail = "Cả thu thập dữ liệu mới lẫn phân tích AI đều tạm dừng tới ngày mai — nâng cấp để tiếp tục ngay, không giới hạn.";
  } else if (analysisCapped) {
    headline = `Bạn đã được phân tích ${responses?.toLocaleString("vi-VN")} phản hồi miễn phí hôm nay`;
    detail = "Dữ liệu mới vẫn được thu thập bình thường, phân tích sẽ tiếp tục vào ngày mai — hoặc nâng cấp ngay để không giới hạn số phản hồi/ngày.";
  } else {
    headline = `Tài khoản dùng thử đã thu thập đủ ${crawlLimit?.toLocaleString("vi-VN")} bản ghi miễn phí hôm nay.`;
    detail =
      "Có thể còn nhiều phản hồi/tài liệu khác đang chờ ngoài kia mà chưa kịp thu thập — tạm dừng tới ngày mai. Nâng cấp để thu thập KHÔNG GIỚI HẠN, không bỏ lỡ dữ liệu nào.";
  }

  return (
    <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-[var(--color-amber-glow)]/30 bg-[var(--color-amber-glow)]/8 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-[13.5px] font-medium text-[var(--color-ink)]">{headline}</p>
        <p className="mt-0.5 text-[12.5px] text-[var(--color-ink-2)]">
          {detail}
          {analysisCapped && user.trial_daily_call_count !== null && user.trial_daily_call_limit !== null && (
            <>
              {" "}
            </>
          )}
        </p>
      </div>
      <Link
        href="/billing/upgrade"
        className="inline-flex h-10 shrink-0 items-center justify-center rounded-md bg-[var(--color-brand-500)] px-4 text-[13.5px] font-semibold text-white transition-colors hover:bg-[var(--color-brand-600)]"
      >
        Nâng cấp ngay
      </Link>
    </div>
  );
}
