"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { Trash } from "@phosphor-icons/react/dist/ssr";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Source, SourceType, Topic } from "@/lib/types";
import { buildFacebookSourceConfig, detectFacebookKind, type FacebookKind } from "@/lib/facebookSource";
import { buildTikTokSourceConfig, TIKTOK_POST_ACTOR_ID } from "@/lib/tiktokSource";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Topbar } from "@/components/layout/Topbar";

const SOURCE_LABEL: Record<SourceType, string> = {
  google_play: "Google Play",
  app_store: "App Store",
  linkedin: "LinkedIn (chưa hỗ trợ)",
  bank_website: "Website ngân hàng (nguồn đối chiếu)",
  facebook: "Facebook (qua Apify)",
  news_article: "Bài báo/tin tức (qua Apify)",
  tiktok: "TikTok (qua Apify)",
};

// Gợi ý khởi điểm — actor CỘNG ĐỒNG (không phải do Apify chính thức duy trì), xác nhận tồn tại
// trên Apify Store nhưng KHÔNG đảm bảo input/output khớp 100% mọi lúc. Nên vào Apify Store (mục
// News) kiểm tra/đổi actor phù hợp trước khi dùng thật.
const DEFAULT_NEWS_ACTOR_ID = "scrapesage/google-news-scraper";

const selectClass =
  "h-12 rounded-xl border border-[var(--color-line)] bg-white px-3 text-[14px] text-[var(--color-ink)] outline-none transition focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-500)]/20";

export default function EditTopicPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [alertThreshold, setAlertThreshold] = useState(10);
  const [notifyEnabled, setNotifyEnabled] = useState(true);
  const [notifyChannel, setNotifyChannel] = useState<"email" | "web" | "both">("both");
  const [autoAssignEnabled, setAutoAssignEnabled] = useState(false);

  const [newSourceType, setNewSourceType] = useState<SourceType>("google_play");
  const [newSourceQuery, setNewSourceQuery] = useState("");
  // bank_website không tìm theo tên (query) như 3 nguồn kia — cần URL trang chủ thật để crawl
  // thông báo/chính sách/biểu phí (xem BankWebsiteCollector, src/pipeline/collectors/bank_website.py).
  const [newSourceUrl, setNewSourceUrl] = useState("");
  // Dùng khi newSourceType === "news_article" HOẶC "facebook" — không có actor Apify "chính thức"
  // ổn định cho tin tức lẫn bài viết Facebook nên phải cho tự chọn (xem NewsApifyCollector,
  // FacebookApifyCollector). Rỗng lúc khởi tạo (không prefill DEFAULT_NEWS_ACTOR_ID) để tránh vô
  // tình mang actor tin tức sang khi đổi loại nguồn sang facebook.
  const [newSourceActorId, setNewSourceActorId] = useState("");
  // Chỉ dùng khi newSourceType === "facebook" — Trang và Nhóm công khai dùng 2 actor Apify khác
  // nhau (xem lib/facebookSource.ts).
  const [newSourceFacebookKind, setNewSourceFacebookKind] = useState<FacebookKind>("page");

  const [deleteSourceTarget, setDeleteSourceTarget] = useState<Source | null>(null);
  const [deleteTopicOpen, setDeleteTopicOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function loadTopic() {
    api.get<Topic>(`/topics/${id}`).then((t) => {
      setTopic(t);
      setName(t.name);
      setKeywordsText(t.keywords.join(", "));
      setAlertThreshold(t.alert_threshold);
      setNotifyEnabled(t.notify_enabled);
      setNotifyChannel(t.notify_channel);
      setAutoAssignEnabled(t.auto_assign_enabled);
    });
  }

  useEffect(loadTopic, [id]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.patch(`/topics/${id}`, {
        name,
        keywords: keywordsText
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
        alert_threshold: alertThreshold,
        notify_enabled: notifyEnabled,
        notify_channel: notifyChannel,
        auto_assign_enabled: autoAssignEnabled,
      });
      toast.success("Đã lưu thay đổi");
      router.push(`/topics/${id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được thay đổi");
    } finally {
      setSaving(false);
    }
  }

  async function addSource() {
    if (newSourceType === "bank_website") {
      if (!newSourceUrl.trim()) return;
      await api.post<Source>(`/topics/${id}/sources`, {
        type: newSourceType,
        config: { seed_urls: [newSourceUrl.trim()] },
      });
      setNewSourceUrl("");
    } else if (newSourceType === "facebook") {
      if (!newSourceUrl.trim()) return;
      await api.post<Source>(`/topics/${id}/sources`, {
        type: newSourceType,
        config: buildFacebookSourceConfig(newSourceFacebookKind, newSourceUrl.trim(), newSourceActorId),
      });
      setNewSourceUrl("");
      setNewSourceActorId("");
    } else if (newSourceType === "news_article") {
      if (!newSourceQuery.trim()) return;
      await api.post<Source>(`/topics/${id}/sources`, {
        type: newSourceType,
        config: {
          actor_id: (newSourceActorId || DEFAULT_NEWS_ACTOR_ID).trim(),
          run_input: { searchTerms: [newSourceQuery.trim()], maxItems: 100 },
        },
      });
      setNewSourceQuery("");
    } else if (newSourceType === "tiktok") {
      if (!newSourceQuery.trim()) return;
      await api.post<Source>(`/topics/${id}/sources`, {
        type: newSourceType,
        config: buildTikTokSourceConfig(newSourceQuery.trim(), newSourceActorId),
      });
      setNewSourceQuery("");
      setNewSourceActorId("");
    } else {
      if (!newSourceQuery.trim()) return;
      await api.post<Source>(`/topics/${id}/sources`, {
        type: newSourceType,
        config: { query: newSourceQuery.trim(), country: "vn", lang: "vi" },
      });
      setNewSourceQuery("");
    }
    loadTopic();
  }

  async function toggleSource(source: Source) {
    await api.patch(`/topics/${id}/sources/${source.id}`, { is_active: !source.is_active });
    loadTopic();
  }

  async function updateSourcePriority(source: Source, priority: number) {
    if (!Number.isFinite(priority) || priority < 1 || priority === source.analysis_priority) return;
    await api.patch(`/topics/${id}/sources/${source.id}`, { analysis_priority: Math.round(priority) });
    loadTopic();
  }

  async function confirmDeleteSource() {
    if (!deleteSourceTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/topics/${id}/sources/${deleteSourceTarget.id}`);
      setDeleteSourceTarget(null);
      loadTopic();
    } finally {
      setDeleting(false);
    }
  }

  async function confirmDeleteTopic() {
    setDeleting(true);
    try {
      await api.delete(`/topics/${id}`);
      router.push("/topics");
    } finally {
      setDeleting(false);
    }
  }

  if (!topic) return <p className="text-sm text-[var(--color-muted)]">Đang tải...</p>;

  return (
    <div className="max-w-2xl">
      <Topbar title={`Chỉnh sửa: ${topic.name}`} />

      <form onSubmit={onSubmit} className="space-y-6 pt-6">
        <Card className="p-6">
          <CardHeader className="border-none p-0 pb-4">
            <CardTitle>Thông tin chung</CardTitle>
          </CardHeader>
          <CardBody className="space-y-4 p-0">
            <div>
              <Label htmlFor="name">Tên chủ đề</Label>
              <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="keywords">Từ khoá (cách nhau bằng dấu phẩy)</Label>
              <Input id="keywords" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="alertThreshold">Ngưỡng cảnh báo</Label>
              <Input
                id="alertThreshold"
                type="number"
                min={1}
                required
                value={alertThreshold}
                onChange={(e) => setAlertThreshold(Number(e.target.value))}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="notifyEnabled"
                type="checkbox"
                checked={notifyEnabled}
                onChange={(e) => setNotifyEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--color-line)] accent-[var(--color-brand-500)]"
              />
              <Label htmlFor="notifyEnabled" className="mb-0 normal-case tracking-normal">
                Bật thông báo khi vượt ngưỡng (tắt vẫn giữ nguyên dữ liệu đã thu thập)
              </Label>
            </div>
            {notifyEnabled && (
              <div>
                <Label htmlFor="notifyChannel">Kênh thông báo</Label>
                <select
                  id="notifyChannel"
                  value={notifyChannel}
                  onChange={(e) => setNotifyChannel(e.target.value as typeof notifyChannel)}
                  className={`${selectClass} w-full`}
                >
                  <option value="both">Email + Website</option>
                  <option value="email">Chỉ Email</option>
                  <option value="web">Chỉ trên Website</option>
                </select>
              </div>
            )}
            <div className="flex items-center gap-2">
              <input
                id="autoAssignEnabled"
                type="checkbox"
                checked={autoAssignEnabled}
                onChange={(e) => setAutoAssignEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--color-line)] accent-[var(--color-brand-500)]"
              />
              <Label htmlFor="autoAssignEnabled" className="mb-0 normal-case tracking-normal">
                Tự động phân việc theo phòng ban (dựa vào phòng ban đã gán cho từng nhân viên ở trang Thành viên)
              </Label>
            </div>
          </CardBody>
        </Card>

        <FieldError>{error}</FieldError>
        <div className="flex gap-3">
          <Button type="submit" loading={saving}>
            Lưu thay đổi
          </Button>
          <Button type="button" variant="secondary" onClick={() => router.push(`/topics/${id}`)}>
            Huỷ
          </Button>
        </div>
      </form>

      <Card className="mt-6 p-6">
        <CardHeader className="border-none p-0 pb-4">
          <CardTitle>Nguồn dữ liệu</CardTitle>
        </CardHeader>
        <CardBody className="space-y-3 p-0">
          {topic.sources.map((source) => {
            const configText =
              (source.config as { query?: string; seed_urls?: string[] }).query ||
              (source.config as { seed_urls?: string[] }).seed_urls?.join(", ") ||
              JSON.stringify(source.config);
            return (
            <div key={source.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--color-line)] px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--color-ink)]">{SOURCE_LABEL[source.type]}</p>
                {/* block (không phải span inline) + min-w-0 để truncate tính được chiều rộng thật mà
                    cắt chữ — thiếu 2 thứ này, chuỗi config JSON dài (vd cấu hình Facebook/Apify) tràn
                    thẳng ra ngoài card thay vì hiện "...". title= để vẫn xem được đầy đủ khi hover. */}
                <p className="min-w-0 truncate text-xs text-[var(--color-muted)]" title={configText}>
                  {configText}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <label
                  className="flex items-center gap-1 text-xs text-[var(--color-muted)]"
                  title="Trọng số ưu tiên phân tích — mặc định 1 (mọi nguồn ngang nhau, luân phiên đều). Đặt số lớn hơn để nguồn này được phân tích thường xuyên hơn các nguồn khác theo đúng tỷ lệ (không bao giờ khiến nguồn khác về 0 lượt)."
                >
                  Ưu tiên
                  <input
                    key={`${source.id}-${source.analysis_priority}`}
                    type="number"
                    min={1}
                    defaultValue={source.analysis_priority}
                    onBlur={(e) => updateSourcePriority(source, Number(e.target.value))}
                    className="h-8 w-14 rounded-md border border-[var(--color-line)] bg-white px-1.5 text-center text-xs text-[var(--color-ink)] outline-none focus:border-[var(--color-brand-500)]"
                  />
                </label>
                <span className={source.is_active ? "text-xs text-[var(--color-leaf)]" : "text-xs text-[var(--color-muted)]"}>
                  {source.is_active ? "Đang bật" : "Đã tắt"}
                </span>
                <Button type="button" variant="ghost" onClick={() => toggleSource(source)}>
                  {source.is_active ? "Tắt" : "Bật"}
                </Button>
                <button
                  type="button"
                  onClick={() => setDeleteSourceTarget(source)}
                  aria-label="Xoá nguồn"
                  className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-rose)]"
                >
                  <Trash size={15} />
                </button>
              </div>
            </div>
            );
          })}

          <div className="flex items-center gap-2 pt-2">
            <select value={newSourceType} onChange={(e) => setNewSourceType(e.target.value as SourceType)} className={selectClass}>
              {(Object.keys(SOURCE_LABEL) as SourceType[]).map((type) => (
                <option key={type} value={type}>
                  {SOURCE_LABEL[type]}
                </option>
              ))}
            </select>
            {newSourceType === "bank_website" || newSourceType === "facebook" ? (
              <Input
                value={newSourceUrl}
                onChange={(e) => {
                  const value = e.target.value;
                  setNewSourceUrl(value);
                  // Tự nhận diện Trang/Nhóm ngay khi gõ URL — tránh lỗi chọn sai loại (xem
                  // lib/facebookSource.ts).
                  if (newSourceType === "facebook") setNewSourceFacebookKind(detectFacebookKind(value));
                }}
                placeholder={
                  newSourceType === "facebook"
                    ? newSourceFacebookKind === "group"
                      ? "URL nhóm Facebook công khai (vd https://www.facebook.com/groups/...)"
                      : "URL trang Facebook công khai (vd https://www.facebook.com/TPBank)"
                    : "URL trang chủ thật (vd https://tpb.vn)"
                }
                className="flex-1"
              />
            ) : (
              <Input
                value={newSourceQuery}
                onChange={(e) => setNewSourceQuery(e.target.value)}
                placeholder={
                  newSourceType === "news_article"
                    ? "Từ khoá tìm kiếm (vd TPBank)"
                    : newSourceType === "tiktok"
                      ? "Tên hồ sơ TikTok công khai (vd tpbank hoặc https://www.tiktok.com/@tpbank)"
                      : "Tên ngân hàng/app"
                }
                className="flex-1"
              />
            )}
            <Button type="button" variant="secondary" onClick={addSource}>
              + Thêm
            </Button>
          </div>
          {newSourceType === "news_article" && (
            <Input
              value={newSourceActorId}
              onChange={(e) => setNewSourceActorId(e.target.value)}
              placeholder="Apify actor ID (vd: scrapesage/google-news-scraper)"
              className="w-full"
            />
          )}
          {newSourceType === "facebook" && (
            <div className="space-y-2">
              <div className="flex gap-1.5">
                {(["page", "group"] as FacebookKind[]).map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    onClick={() => {
                      setNewSourceFacebookKind(kind);
                      setNewSourceActorId("");
                    }}
                    aria-pressed={newSourceFacebookKind === kind}
                    className={`rounded-full border px-3 py-1 text-[11.5px] font-medium transition-colors ${
                      newSourceFacebookKind === kind
                        ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                        : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
                    }`}
                  >
                    {kind === "page" ? "Trang (Page)" : "Nhóm (Group)"}
                  </button>
                ))}
              </div>
              <Input
                value={newSourceActorId}
                onChange={(e) => setNewSourceActorId(e.target.value)}
                placeholder={
                  newSourceFacebookKind === "group"
                    ? "Apify actor ID cho nhóm (mặc định: apify/facebook-groups-scraper)"
                    : "Apify actor ID cho trang (mặc định: apify/facebook-posts-scraper)"
                }
                className="w-full"
              />
            </div>
          )}
          {newSourceType === "tiktok" && (
            <Input
              value={newSourceActorId}
              onChange={(e) => setNewSourceActorId(e.target.value)}
              placeholder={`Apify actor ID cho video (mặc định: ${TIKTOK_POST_ACTOR_ID})`}
              className="w-full"
            />
          )}
          {newSourceType === "bank_website" && (
            <p className="text-xs text-[var(--color-muted)]">
              Hệ thống sẽ tự tìm thông báo/chính sách/biểu phí/sản phẩm liên kết từ trang chủ này theo lịch —
              chỉ hoạt động nếu trang không chặn truy cập tự động (một số ngân hàng có xác minh bảo mật chặn
              hết request tự động, khi đó nguồn này sẽ không thu thập được).
            </p>
          )}
          {newSourceType === "facebook" && (
            <p className="text-xs text-[var(--color-muted)]">
              Lấy bài viết (kèm like/comment/share) và toàn bộ comment công khai của từng bài trên Trang/Nhóm này
              qua Apify (bên thứ ba, không tự động đăng nhập Facebook) — cần cấu hình APIFY_API_TOKEN ở server và
              chỉ áp dụng cho Trang/Nhóm CÔNG KHAI. Mặc định dùng actor chính thức của Apify tương ứng loại đã
              chọn ở trên (Trang và Nhóm là 2 actor khác nhau, chọn sai loại sẽ luôn trả 0 kết quả). Apify tính phí
              theo số bài viết + số comment lấy được (mỗi bài viết tốn thêm 1 lượt gọi actor comment).
            </p>
          )}
          {newSourceType === "news_article" && (
            <p className="text-xs text-[var(--color-muted)]">
              Không có actor tin tức chính thức ổn định — tìm actor phù hợp trên Apify Store (mục News) và kiểm
              tra lại trước khi dùng thật. Kết quả chỉ hiển thị để tham khảo, không tham gia phân tích AI.
            </p>
          )}
          {newSourceType === "tiktok" && (
            <p className="text-xs text-[var(--color-muted)]">
              Lấy video (kèm like/comment/share) và toàn bộ bình luận công khai của từng video trên hồ sơ này qua
              Apify — cần cấu hình APIFY_API_TOKEN ở server và chỉ áp dụng cho hồ sơ CÔNG KHAI. Không có actor
              chính thức do Apify duy trì — mặc định dùng actor cộng đồng uy tín nhất hiện có (Clockworks). Apify
              tính phí theo số video + số bình luận lấy được (mỗi video tốn thêm 1 lượt gọi actor bình luận).
            </p>
          )}
        </CardBody>
      </Card>

      <div className="mt-6 rounded-2xl border border-[var(--color-rose)]/25 bg-[var(--color-rose)]/[0.04] p-5">
        <p className="text-[13px] font-semibold text-[var(--color-rose)]">Khu vực nguy hiểm</p>
        <p className="mt-1 text-[12.5px] text-[var(--color-muted)]">
          Xoá chủ đề sẽ xoá toàn bộ dữ liệu và pain point liên quan, không thể khôi phục.
        </p>
        <Button variant="danger" className="mt-3" onClick={() => setDeleteTopicOpen(true)}>
          Xoá chủ đề này
        </Button>
      </div>

      <Dialog
        open={!!deleteSourceTarget}
        onClose={() => setDeleteSourceTarget(null)}
        title="Xoá nguồn dữ liệu?"
        description={
          deleteSourceTarget ? `Xoá nguồn "${SOURCE_LABEL[deleteSourceTarget.type]}"? Dữ liệu đã thu thập từ nguồn này vẫn giữ nguyên, chỉ dừng thu thập thêm.` : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteSourceTarget(null)}>
              Huỷ
            </Button>
            <Button variant="danger" loading={deleting} onClick={confirmDeleteSource}>
              Xoá nguồn
            </Button>
          </>
        }
      />

      <Dialog
        open={deleteTopicOpen}
        onClose={() => setDeleteTopicOpen(false)}
        title="Xoá chủ đề này?"
        description={`Xoá chủ đề "${topic.name}"? Toàn bộ dữ liệu và pain point liên quan sẽ bị xoá, không thể khôi phục.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteTopicOpen(false)}>
              Huỷ
            </Button>
            <Button variant="danger" loading={deleting} onClick={confirmDeleteTopic}>
              Xoá chủ đề
            </Button>
          </>
        }
      />
    </div>
  );
}
