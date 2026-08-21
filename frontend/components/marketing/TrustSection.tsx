"use client";

import { motion } from "framer-motion";
import { Fingerprint, LockKey, MagnifyingGlass, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

// 4 điểm đều là cơ chế THẬT đang có trong hệ thống (không phải câu quảng cáo chung chung):
// - PII-safe: PostSummary API chỉ trả content đã làm sạch, không bao giờ trả raw_content.
// - Cô lập theo topic: mỗi chủ đề (workspace) chỉ chủ sở hữu + thành viên được mời mới xem được.
// - Kiểm tra chéo: Cross-Check Agent dùng model AI độc lập thứ 2 khi case còn mơ hồ.
// - Có căn cứ: mọi kết luận đều kèm reasoning + tài liệu đối chiếu cụ thể, xem lại được bất cứ lúc nào.
const TRUST_POINTS = [
  {
    Icon: LockKey,
    title: "Dữ liệu công khai được làm sạch trước khi lưu",
    body: "Nội dung nhạy cảm (vd tên người đánh giá gốc) không bao giờ trả về qua API — chỉ nội dung đã chuẩn hoá được hiển thị.",
  },
  {
    Icon: Fingerprint,
    title: "Cô lập theo từng workspace",
    body: "Mỗi chủ đề chỉ chủ sở hữu và thành viên được mời mới xem được — dữ liệu của ngân hàng này không lẫn sang ngân hàng khác.",
  },
  {
    Icon: MagnifyingGlass,
    title: "Kiểm tra chéo bằng 2 AI độc lập",
    body: "Case còn mơ hồ được một model AI khác kiến trúc phân loại lại độc lập — chỉ kết luận chắc chắn khi cả 2 đồng thuận, không dựa vào 1 ý kiến duy nhất.",
  },
  {
    Icon: ShieldCheck,
    title: "Mọi kết luận đều có căn cứ xem lại được",
    body: "Mỗi phán đoán của AI kèm theo lý do giải thích và tài liệu đối chiếu cụ thể (quy định NHNN, thông báo ngân hàng) — không phải hộp đen.",
  },
];

export function TrustSection() {
  return (
    <section id="bao-mat" className="container-page scroll-mt-24 py-16 md:py-24">
      <div className="overflow-hidden rounded-[24px] border border-[var(--color-line)] bg-[var(--color-ink)] px-6 py-12 text-white sm:px-10 md:px-14 md:py-16">
        <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5 }}
          >
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-semibold text-white/80">
              <ShieldCheck size={14} weight="bold" />
              Đáng tin cậy theo thiết kế
            </span>
            <h2 className="display-xl mt-5 text-[28px] font-semibold leading-tight sm:text-[34px]">
              Dữ liệu phản hồi khách hàng cần nhiều hơn một biểu đồ đẹp.
            </h2>
            <p className="mt-4 max-w-[46ch] text-[14px] leading-relaxed text-white/60">
              Kết luận của AI luôn đi kèm bằng chứng, mỗi workspace được cô lập rõ ràng, và các trường hợp mơ hồ
              được kiểm tra chéo thay vì tin tưởng mù quáng vào 1 lượt phân loại duy nhất.
            </p>
          </motion.div>

          <div className="grid gap-3 sm:grid-cols-2">
            {TRUST_POINTS.map(({ Icon, title, body }, index) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.45, delay: index * 0.08 }}
                className="rounded-[18px] border border-white/10 bg-white/[0.06] p-4 backdrop-blur transition-colors duration-300 hover:bg-white/[0.09]"
              >
                <div className="flex items-center gap-2 text-[var(--color-leaf)]">
                  <Icon size={16} weight="bold" />
                  <h3 className="text-[12.5px] font-semibold text-white">{title}</h3>
                </div>
                <p className="mt-2 text-[12px] leading-relaxed text-white/55">{body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
