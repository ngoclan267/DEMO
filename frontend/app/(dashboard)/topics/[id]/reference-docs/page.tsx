"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { useParams } from "next/navigation";
import { ArrowSquareOut, CaretDown, CaretRight } from "@phosphor-icons/react/dist/ssr";
import { api } from "@/lib/api";
import type { OfficialDocument, Topic } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { DocumentCategoryBadge, DOCUMENT_CATEGORY_OPTIONS } from "@/components/ui/Badges";
import { ExpandableText } from "@/components/ui/ExpandableText";
import { Topbar } from "@/components/layout/Topbar";

const PAGE_SIZE = 20;

function formatDate(value: string | null): string | null {
  return value ? new Date(value).toLocaleDateString("vi-VN") : null;
}

export default function ReferenceDocsPage() {
  const { id } = useParams<{ id: string }>();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [category, setCategory] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const [docs, setDocs] = useState<OfficialDocument[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    api.get<Topic>(`/topics/${id}`).then(setTopic);
  }, [id]);

  // Gõ từ khoá không gọi API ngay mỗi phím — đợi 400ms sau lần gõ cuối (giống mẫu ở trang posts).
  useEffect(() => {
    const timer = setTimeout(() => setQ(searchInput), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  async function loadMore(currentOffset: number) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(currentOffset) });
      if (category) params.set("category", category);
      if (q) params.set("q", q);
      const page = await api.get<OfficialDocument[]>(`/topics/${id}/official-documents?${params.toString()}`);
      // "Tất cả" (không lọc category) vẫn loại tin bên thứ ba (NewsApifyCollector) khỏi trang này —
      // trang này chỉ dành cho nguồn đối chiếu CHÍNH THỨC của doanh nghiệp, tin bên thứ 3 đã hiển
      // thị riêng ở dashboard chủ đề (mục "Bài báo liên quan").
      const filtered = category ? page : page.filter((d) => d.category !== "news");
      setDocs((prev) => (currentOffset === 0 ? filtered : [...prev, ...filtered]));
      setOffset(currentOffset + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-filter-change, standard pattern
    setDocs([]);
    setOpenId(null);
    loadMore(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, category, q]);

  return (
    <div>
      <Topbar title="Nguồn đối chiếu" subtitle={topic ? topic.name : undefined} />

      <div className="pt-6">
        <Link href={`/topics/${id}`} className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]">
          ← Quay lại dashboard
        </Link>

        <p className="mt-3 mb-4 text-sm leading-relaxed text-[var(--color-muted)]">
          Toàn bộ thông báo, chính sách, biểu phí, sản phẩm... crawl được từ website chính thức của doanh nghiệp — dùng để
          đối chiếu khi trả lời hoặc đính chính thắc mắc của khách hàng. Chọn 1 tiêu đề để xem nội dung đầy đủ.
        </p>

        <Card className="mt-4 mb-4 p-5">
          <CardBody className="space-y-3 p-0">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Tìm theo từ khoá trong tiêu đề/nội dung..."
            />
            <div className="flex flex-wrap gap-1.5">
              {[{ value: "", label: "Tất cả" }, ...DOCUMENT_CATEGORY_OPTIONS].map((o) => (
                <button
                  key={o.value || "all"}
                  type="button"
                  onClick={() => setCategory(o.value)}
                  aria-pressed={category === o.value}
                  className={clsx(
                    "rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors",
                    category === o.value
                      ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                      : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]",
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Danh sách tài liệu</CardTitle>
          </CardHeader>
          <CardBody className="space-y-2">
            <AnimatePresence initial={false}>
              {docs.map((doc, index) => {
                const isOpen = openId === doc.id;
                return (
                  <motion.div
                    key={doc.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.03 }}
                    whileHover={{ y: -2 }}
                    className="rounded-2xl border border-[var(--color-line)] bg-white shadow-[0_1px_2px_rgba(11,18,32,0.03)] transition-shadow duration-300 hover:shadow-[0_10px_24px_rgba(11,18,32,0.08)]"
                  >
                    <button
                      type="button"
                      onClick={() => setOpenId(isOpen ? null : doc.id)}
                      className="flex w-full items-start gap-3 px-4 py-3 text-left"
                    >
                      <span className="mt-0.5 shrink-0 text-[var(--color-muted)]">
                        {isOpen ? <CaretDown size={14} /> : <CaretRight size={14} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-[var(--color-ink)]">{doc.title}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2">
                          <DocumentCategoryBadge category={doc.category} />
                          {formatDate(doc.published_at || doc.last_seen_at) && (
                            <span className="text-xs text-[var(--color-muted)]">
                              {formatDate(doc.published_at || doc.last_seen_at)}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                    {isOpen && (
                      <div className="border-t border-[var(--color-line)] px-4 py-4">
                        {doc.content ? (
                          <ExpandableText text={doc.content} />
                        ) : (
                          <p className="text-sm text-[var(--color-muted)]">Chưa có nội dung.</p>
                        )}
                        <a
                          href={doc.url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-brand-600)] hover:underline"
                        >
                          Xem trang gốc <ArrowSquareOut size={12} />
                        </a>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>

            {docs.length === 0 && !loading && (
              <p className="text-sm text-[var(--color-muted)]">Chưa có tài liệu đối chiếu nào khớp bộ lọc.</p>
            )}

            {hasMore && (
              <div className="pt-2">
                <Button variant="secondary" onClick={() => loadMore(offset)} loading={loading}>
                  Tải thêm
                </Button>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
