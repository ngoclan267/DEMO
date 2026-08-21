"use client";

import { motion } from "framer-motion";
import { Clock, Scales, Siren, UsersThree } from "@phosphor-icons/react/dist/ssr";

const BENEFITS = [
  {
    Icon: Siren,
    title: "Phát hiện khủng hoảng truyền thông sớm",
    body: "Nhìn thấy 1 vấn đề đang lan rộng khi mới có vài chục phản hồi, thay vì khi báo chí/mạng xã hội đã đưa tin.",
  },
  {
    Icon: Clock,
    title: "Tiết kiệm thời gian rà soát thủ công",
    body: "Không cần đọc thủ công hàng nghìn đánh giá mỗi tháng — AI tự lọc ra đúng nhóm vấn đề đáng chú ý.",
  },
  {
    Icon: Scales,
    title: "Có căn cứ khi phản hồi khách hàng/báo chí",
    body: "Mỗi pain point được đối chiếu với văn bản chính thức (quy định NHNN, thông báo, chính sách của ngân hàng) — trả lời có căn cứ, không phỏng đoán.",
  },
  {
    Icon: UsersThree,
    title: "Phân công và theo dõi xử lý rõ ràng",
    body: "Giao case cho đúng người/phòng ban, có hạn xử lý (SLA) theo mức độ nghiêm trọng — không case nào bị bỏ sót.",
  },
];

export function MarketingBenefits() {
  return (
    <section id="loi-ich" className="container-page scroll-mt-24 py-16 md:py-24">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className="max-w-[42rem]"
      >
        <p className="eyebrow">Vì sao dùng VigiBank</p>
        <h2 className="display-xl mt-2 text-[30px] font-semibold text-[var(--color-ink)] md:text-[40px]">Lợi ích mang lại</h2>
        <p className="mt-4 max-w-[52ch] text-[14.5px] leading-relaxed text-[var(--color-muted)]">
          Không chỉ thu thập đánh giá — hệ thống giúp đội ngũ vận hành phát hiện sớm, phản hồi có căn
          cứ và xử lý đúng hạn trước khi 1 vấn đề nhỏ lan thành khủng hoảng truyền thông.
        </p>
      </motion.div>

      <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
        {BENEFITS.map(({ Icon, title, body }, index) => (
          <motion.div
            key={title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.45, delay: index * 0.08 }}
            className="card-soft flex gap-4 p-5 transition-all duration-300 hover:-translate-y-1 hover:border-[var(--color-brand-500)]/25 hover:shadow-[0_16px_40px_rgba(11,18,32,0.08)]"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-brand-500)]/10 text-[var(--color-brand-700)]">
              <Icon size={18} weight="bold" />
            </span>
            <div className="min-w-0">
              <p className="text-[15px] font-semibold text-[var(--color-ink)]">{title}</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-[var(--color-muted)]">{body}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
