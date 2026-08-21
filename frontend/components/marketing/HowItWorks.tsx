"use client";

import { motion } from "framer-motion";

const STEPS = [
  {
    title: "Thu thập tự động",
    body: "Theo dõi liên tục đánh giá từ Google Play, App Store, Facebook, TikTok và thông báo chính thức từ website ngân hàng — không cần thao tác thủ công.",
  },
  {
    title: "Phân tích & kiểm tra chéo bằng AI",
    body: "Phân loại chủ đề, đánh giá mức độ nghiêm trọng, đối chiếu với quy định NHNN và chính sách chính thức. Case còn mơ hồ được một model AI độc lập thứ 2 phân loại lại — chỉ kết luận khi cả 2 đồng thuận.",
  },
  {
    title: "Gom thành pain point",
    body: "Khi một nhóm phản hồi cùng vấn đề vượt ngưỡng cảnh báo, hệ thống tự động tạo case theo dõi kèm mức độ nghiêm trọng và xu hướng tăng/giảm.",
  },
  {
    title: "Xử lý kịp thời",
    body: "Giao việc cho đúng người/phòng ban, theo dõi hạn xử lý (SLA) theo mức độ nghiêm trọng, nhận thông báo qua email hoặc trên web ngay khi có diễn biến mới.",
  },
];

export function HowItWorks() {
  return (
    <section id="cach-hoat-dong" className="container-page scroll-mt-24 py-16 md:py-24">
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="lg:sticky lg:top-28 lg:self-start"
        >
          <h2 className="display-xl text-[30px] font-semibold text-[var(--color-ink)] md:text-[40px]">
            Luồng hoạt động <span className="text-[var(--color-brand-700)]">4 bước</span>
          </h2>
          <p className="mt-4 max-w-[42ch] text-[14.5px] leading-relaxed text-[var(--color-muted)]">
            Từ hàng nghìn phản hồi rải rác mỗi ngày, hệ thống tự động chắt lọc thành những vấn đề
            thực sự đáng chú ý — kèm bằng chứng đối chiếu, để đội ngũ vận hành không bỏ sót và
            không mất thời gian vào những gì đã có lời giải thích chính thức.
          </p>
        </motion.div>

        <ol className="space-y-0 border-t border-[var(--color-line)]">
          {STEPS.map((step, i) => (
            <motion.li
              key={step.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.45, delay: i * 0.07 }}
              className="grid grid-cols-[auto_1fr] gap-5 border-b border-[var(--color-line)] py-6 md:gap-8 md:py-7"
            >
              <span className="font-mono text-[13px] font-medium text-[var(--color-muted)] tabular-nums">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <h3 className="display-xl text-[20px] font-semibold text-[var(--color-ink)] md:text-[22px]">{step.title}</h3>
                <p className="mt-2 max-w-[50ch] text-[14px] leading-relaxed text-[var(--color-muted)]">{step.body}</p>
              </div>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}
