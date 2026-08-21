"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PostDetail } from "@/lib/types";
import {
  SentimentBadge,
  SeverityBadge,
  ReferenceBadge,
  ReferenceRelationBadge,
  IdentityBadge,
  ContentReliabilityBadge,
  ConsensusBadge,
  CrossCheckBadge,
} from "@/components/ui/Badges";
import { Button } from "@/components/ui/Button";
import { PostDate } from "@/components/posts/PostDate";
import { Dialog } from "@/components/ui/Dialog";

const SOURCE_LABEL: Record<string, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn",
  facebook: "Facebook",
  tiktok: "TikTok",
};

export function PostDetailModal({ postId, onClose }: { postId: string; onClose: () => void }) {
  const [post, setPost] = useState<PostDetail | null>(null);
  // Mặc định MỞ SẴN — đây là nội dung nhân sự CSKH cần đọc nhanh nhất để trả lời/giải thích phản
  // hồi, bắt phải bấm thêm 1 lần mới thấy chỉ làm chậm việc xử lý.
  const [showSources, setShowSources] = useState(true);

  useEffect(() => {
    api.get<PostDetail>(`/posts/${postId}`).then((p) => {
      setPost(p);
      setShowSources(true);
    });
  }, [postId]);

  return (
    <Dialog open onClose={onClose} title="Chi tiết phản hồi" size="lg">
      {!post ? (
        <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>
      ) : (
        <>
          <p className="mb-4 whitespace-pre-wrap text-sm text-[var(--color-ink)]">{post.content}</p>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <SentimentBadge sentiment={post.sentiment} />
            <SeverityBadge score={post.severity_score} />
            {post.topic_label && (
              <span className="rounded-full bg-[var(--color-cream-2)] px-2.5 py-0.5 text-xs font-medium text-[var(--color-ink-2)]">
                {post.topic_label}
              </span>
            )}
            <PostDate postedAt={post.posted_at} collectedAt={post.collected_at} />
          </div>

          {post.reply_content && (
            <section className="mb-4 rounded-2xl border border-[var(--color-brand-100)] bg-[var(--color-brand-50)] p-3">
              <h3 className="mb-1.5 flex items-center justify-between text-xs font-semibold tracking-wide text-[var(--color-brand-700)] uppercase">
                <span>Phản hồi từ ngân hàng</span>
                {post.reply_at && (
                  <span className="text-[11px] font-normal normal-case text-[var(--color-brand-600)]">
                    {new Date(post.reply_at).toLocaleDateString("vi-VN")}
                  </span>
                )}
              </h3>
              <p className="whitespace-pre-wrap text-sm text-[var(--color-ink-2)]">{post.reply_content}</p>
            </section>
          )}

          {/* 3 nhóm tách bạch. Trước đây 2 dòng "Trạng thái xác minh" + "Kết luận" nằm phẳng
              cạnh nhau nên "Chưa xác minh" + "Xác nhận là vấn đề thật" đọc thành mâu thuẫn —
              thực tế chúng nói về 2 chuyện hoàn toàn khác nhau. */}
          <div className="mb-4 space-y-3">
            <section className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-cream-2)]/40 p-3.5">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-[var(--color-muted)] uppercase">Đánh giá của AI</h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[var(--color-muted)]">Độ tin cậy nội dung</span>
                  <ContentReliabilityBadge reliability={post.content_reliability} />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[var(--color-muted)]">Kết luận</span>
                  <div className="flex items-center gap-1.5">
                    <ConsensusBadge status={post.consensus_status} />
                    <CrossCheckBadge agreed={post.cross_check_agreed} />
                  </div>
                </div>
                {post.reasoning && <p className="pt-1 text-xs leading-relaxed text-[var(--color-muted)]">{post.reasoning}</p>}
              </div>
            </section>

            <section className="rounded-2xl border border-[var(--color-line)] p-3.5">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-[var(--color-muted)] uppercase">
                Đối chiếu văn bản chính thức
              </h3>
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="text-[var(--color-muted)]">Kết quả</span>
                <ReferenceBadge status={post.reference_status} />
              </div>
              <p className="mt-1.5 text-xs text-[var(--color-muted)]">
                Đối chiếu với quy định NHNN và thông báo chính thức của ngân hàng.
              </p>

              {post.reference_sources.length > 0 && (
                <div className="mt-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-[var(--color-ink-2)]">
                      Dùng tài liệu dưới đây để giải thích nhanh cho khách hàng:
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowSources((v) => !v)}
                      className="shrink-0 text-xs font-medium text-[var(--color-brand-600)] hover:text-[var(--color-brand-700)] hover:underline"
                    >
                      {showSources ? "Ẩn ▲" : `Xem (${post.reference_sources.length}) ▼`}
                    </button>
                  </div>

                  {showSources && (
                    <ul className="mt-2 space-y-2">
                      {post.reference_sources.map((src) => (
                        <li key={src.doc_id} className="rounded-xl bg-[var(--color-cream-2)]/60 p-2">
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-xs font-medium text-[var(--color-ink-2)]">{src.title}</span>
                            <ReferenceRelationBadge relation={src.relation} />
                          </div>
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1 inline-block break-all text-xs text-[var(--color-brand-600)] hover:underline"
                          >
                            {src.url} ↗
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-[var(--color-line)] p-3.5">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-[var(--color-muted)] uppercase">
                Xác minh danh tính khách hàng
              </h3>
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="text-[var(--color-muted)]">Trạng thái</span>
                <IdentityBadge status={post.verification_status} />
              </div>
              <p className="mt-1.5 text-xs text-[var(--color-muted)]">
                Chưa kết nối CRM nên không đối chiếu được người viết với khách hàng thật. Các đánh giá phía trên
                chỉ dựa trên nội dung công khai.
              </p>
            </section>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--color-line)] pt-4 text-sm">
            <div>
              <p className="text-[var(--color-muted)]">Nguồn</p>
              <p className="font-medium text-[var(--color-ink-2)]">
                {post.source ? SOURCE_LABEL[post.source.source_type] || post.source.source_type : "—"}
              </p>
            </div>
            {post.source_url ? (
              <a href={post.source_url} target="_blank" rel="noopener noreferrer">
                <Button variant="secondary">Xem bài viết gốc ↗</Button>
              </a>
            ) : (
              post.source?.app_url && (
                <a href={post.source.app_url} target="_blank" rel="noopener noreferrer">
                  <Button variant="secondary">Xem trên cửa hàng ứng dụng ↗</Button>
                </a>
              )
            )}
          </div>
        </>
      )}
    </Dialog>
  );
}
