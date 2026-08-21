"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Envelope, Trash, UsersThree } from "@phosphor-icons/react/dist/ssr";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { NotifyChannel, SourceType, Topic } from "@/lib/types";
import { buildFacebookSourceConfig, detectFacebookKind, type FacebookKind } from "@/lib/facebookSource";
import { buildTikTokSourceConfig, TIKTOK_POST_ACTOR_ID } from "@/lib/tiktokSource";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Topbar } from "@/components/layout/Topbar";

type Plan = "trial" | "paid";

interface SourceRow {
  type: SourceType;
  query: string;
  // Dùng khi type === "news_article" HOẶC "facebook" (bỏ trống thì facebook tự dùng actor mặc
  // định theo facebookKind — xem lib/facebookSource.ts).
  actorId?: string;
  // Chỉ dùng khi type === "facebook" — Trang và Nhóm công khai dùng 2 actor Apify khác nhau.
  facebookKind?: FacebookKind;
}

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
// trên Apify Store nhưng KHÔNG đảm bảo input/output khớp 100% mọi lúc. Admin nên vào Apify Store
// (mục News) kiểm tra/đổi actor phù hợp trước khi dùng thật.
const DEFAULT_NEWS_ACTOR_ID = "scrapesage/google-news-scraper";

const selectClass =
  "h-12 rounded-xl border border-[var(--color-line)] bg-white px-3 text-[14px] text-[var(--color-ink)] outline-none transition focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-500)]/20";

interface CreatedEntry {
  topicName: string;
  ownerEmail: string;
  plan: Plan;
}

export default function AdminPage() {
  const { user } = useAuth();

  const [name, setName] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [alertThreshold, setAlertThreshold] = useState(10);
  const [notifyEnabled, setNotifyEnabled] = useState(true);
  const [notifyChannel, setNotifyChannel] = useState<NotifyChannel>("both");
  const [sources, setSources] = useState<SourceRow[]>([{ type: "google_play", query: "" }]);

  // Điền sẵn email/tên khi đến từ trang "Yêu cầu liên hệ" (?owner_email=...&owner_full_name=...)
  // — initial state tính THẲNG từ window.location (lazy initializer, chỉ chạy 1 lần lúc mount) thay
  // vì setState trong useEffect (gây cascading render) hay useSearchParams() của Next.js (trang này
  // đang prerender static, thêm useSearchParams sẽ làm build lỗi nếu không bọc Suspense).
  const [ownerEmail, setOwnerEmail] = useState(() =>
    typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get("owner_email") || "",
  );
  const [ownerFullName, setOwnerFullName] = useState(() =>
    typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get("owner_full_name") || "",
  );
  const [plan, setPlan] = useState<Plan>("trial");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [created, setCreated] = useState<CreatedEntry[]>([]);

  if (!user?.is_platform_admin) {
    return (
      <div>
        <Topbar title="Quản trị" />
        <Card className="mt-6 p-8 text-center">
          <p className="text-[14px] font-semibold text-[var(--color-ink)]">Không có quyền truy cập</p>
          <p className="mt-1.5 text-[13px] text-[var(--color-muted)]">Trang này chỉ dành cho tài khoản quản trị nền tảng.</p>
        </Card>
      </div>
    );
  }

  function updateSource(index: number, patch: Partial<SourceRow>) {
    setSources((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  function addSourceRow() {
    setSources((prev) => [...prev, { type: "google_play", query: "" }]);
  }

  function removeSourceRow(index: number) {
    setSources((prev) => prev.filter((_, i) => i !== index));
  }

  function resetTopicFields() {
    setName("");
    setKeywordsText("");
    setAlertThreshold(10);
    setNotifyEnabled(true);
    setNotifyChannel("both");
    setSources([{ type: "google_play", query: "" }]);
    setOwnerEmail("");
    setOwnerFullName("");
    setPlan("trial");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload = {
        name,
        keywords: keywordsText
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
        alert_threshold: alertThreshold,
        notify_enabled: notifyEnabled,
        notify_channel: notifyChannel,
        sources: sources
          .filter((s) => s.query.trim())
          .map((s) => {
            if (s.type === "bank_website") return { type: s.type, config: { seed_urls: [s.query.trim()] } };
            if (s.type === "facebook")
              return {
                type: s.type,
                config: buildFacebookSourceConfig(s.facebookKind || "page", s.query.trim(), s.actorId),
              };
            if (s.type === "news_article")
              return {
                type: s.type,
                config: {
                  actor_id: (s.actorId || DEFAULT_NEWS_ACTOR_ID).trim(),
                  run_input: { searchTerms: [s.query.trim()], maxItems: 100 },
                },
              };
            if (s.type === "tiktok") return { type: s.type, config: buildTikTokSourceConfig(s.query.trim(), s.actorId) };
            return { type: s.type, config: { query: s.query.trim(), country: "vn", lang: "vi" } };
          }),
        owner_email: ownerEmail,
        owner_full_name: ownerFullName || null,
        plan,
      };
      const topic = await api.post<Topic>("/topics/admin", payload);
      setCreated((prev) => [{ topicName: topic.name, ownerEmail, plan }, ...prev]);
      resetTopicFields();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được chủ đề");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Topbar
        title="Quản trị"
        subtitle="Tạo chủ đề (workspace) và tài khoản chủ sở hữu cho từng doanh nghiệp muốn dùng sản phẩm."
        cta={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/admin/contacts"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-[var(--color-line)] bg-white px-4 text-[13.5px] font-semibold text-[var(--color-ink)] transition-colors hover:bg-[var(--color-cream-2)]"
            >
              <Envelope size={16} />
              Yêu cầu liên hệ
            </Link>
            <Link
              href="/admin/users"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-[var(--color-line)] bg-white px-4 text-[13.5px] font-semibold text-[var(--color-ink)] transition-colors hover:bg-[var(--color-cream-2)]"
            >
              <UsersThree size={16} />
              Quản lý tài khoản
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 pt-6 lg:grid-cols-[2fr_1fr]">
        <form onSubmit={onSubmit} className="space-y-6">
          <Card className="p-6">
            <CardHeader className="border-none p-0 pb-4">
              <CardTitle>Doanh nghiệp mới</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4 p-0">
              <div>
                <Label htmlFor="name">Tên chủ đề</Label>
                <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="VD: MBV Bank" />
              </div>
              <div>
                <Label htmlFor="keywords">Từ khoá (cách nhau bằng dấu phẩy)</Label>
                <Input id="keywords" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} placeholder="MBV, MBV Bank" />
              </div>
              <div>
                <Label htmlFor="alertThreshold">Ngưỡng cảnh báo (số phản hồi trong 1 pain point)</Label>
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
                  Bật thông báo khi vượt ngưỡng
                </Label>
              </div>
              {notifyEnabled && (
                <div>
                  <Label htmlFor="notifyChannel">Kênh thông báo</Label>
                  <select
                    id="notifyChannel"
                    value={notifyChannel}
                    onChange={(e) => setNotifyChannel(e.target.value as NotifyChannel)}
                    className={`${selectClass} w-full`}
                  >
                    <option value="both">Email + Website</option>
                    <option value="email">Chỉ Email</option>
                    <option value="web">Chỉ trên Website</option>
                  </select>
                </div>
              )}
            </CardBody>
          </Card>

          <Card className="p-6">
            <CardHeader className="border-none p-0 pb-4">
              <CardTitle>Nguồn dữ liệu</CardTitle>
            </CardHeader>
            <CardBody className="space-y-3 p-0">
              {sources.map((source, index) => (
                <div key={index} className="rounded-xl border border-[var(--color-line)] p-2.5">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <select
                      value={source.type}
                      onChange={(e) => updateSource(index, { type: e.target.value as SourceType })}
                      className={`${selectClass} w-full sm:w-auto`}
                    >
                      {(Object.keys(SOURCE_LABEL) as SourceType[]).map((type) => (
                        <option key={type} value={type}>
                          {SOURCE_LABEL[type]}
                        </option>
                      ))}
                    </select>
                    <div className="flex flex-1 items-center gap-2">
                      <Input
                        value={source.query}
                        onChange={(e) => {
                          const value = e.target.value;
                          // Tự nhận diện Trang/Nhóm ngay khi gõ URL — tránh lỗi chọn sai loại (xem
                          // lib/facebookSource.ts).
                          updateSource(
                            index,
                            source.type === "facebook" ? { query: value, facebookKind: detectFacebookKind(value) } : { query: value },
                          );
                        }}
                        placeholder={
                          source.type === "bank_website"
                            ? "URL trang chủ thật"
                            : source.type === "facebook"
                              ? source.facebookKind === "group"
                                ? "URL nhóm Facebook công khai"
                                : "URL trang Facebook công khai"
                              : source.type === "news_article"
                                ? "Từ khoá tìm kiếm (tên ngân hàng)"
                                : source.type === "tiktok"
                                  ? "Tên hồ sơ TikTok công khai"
                                  : "Tên ngân hàng/app"
                        }
                        className="min-w-0 flex-1"
                      />
                      <button
                        type="button"
                        onClick={() => removeSourceRow(index)}
                        aria-label="Xoá nguồn"
                        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-rose)]"
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                  </div>
                  {source.type === "news_article" && (
                    <div className="mt-2">
                      <Input
                        value={source.actorId ?? DEFAULT_NEWS_ACTOR_ID}
                        onChange={(e) => updateSource(index, { actorId: e.target.value })}
                        placeholder="Apify actor ID (vd: scrapesage/google-news-scraper)"
                        className="w-full"
                      />
                      <p className="mt-1 text-[11px] text-[var(--color-muted)]">
                        Không có actor tin tức chính thức ổn định — tìm actor phù hợp trên Apify Store (mục News) và
                        kiểm tra lại trước khi dùng thật.
                      </p>
                    </div>
                  )}
                  {source.type === "facebook" && (
                    <div className="mt-2 space-y-2">
                      <div className="flex gap-1.5">
                        {(["page", "group"] as FacebookKind[]).map((kind) => (
                          <button
                            key={kind}
                            type="button"
                            onClick={() => updateSource(index, { facebookKind: kind, actorId: undefined })}
                            aria-pressed={(source.facebookKind || "page") === kind}
                            className={`rounded-full border px-3 py-1 text-[11.5px] font-medium transition-colors ${
                              (source.facebookKind || "page") === kind
                                ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)] text-white"
                                : "border-[var(--color-line)] bg-white text-[var(--color-ink-2)] hover:bg-[var(--color-cream-2)]"
                            }`}
                          >
                            {kind === "page" ? "Trang (Page)" : "Nhóm (Group)"}
                          </button>
                        ))}
                      </div>
                      <Input
                        value={source.actorId ?? ""}
                        onChange={(e) => updateSource(index, { actorId: e.target.value })}
                        placeholder={
                          source.facebookKind === "group"
                            ? "Apify actor ID cho nhóm (mặc định: apify/facebook-groups-scraper)"
                            : "Apify actor ID cho trang (mặc định: apify/facebook-posts-scraper)"
                        }
                        className="w-full"
                      />
                      <p className="text-[11px] text-[var(--color-muted)]">
                        Mặc định dùng actor chính thức của Apify tương ứng loại đã chọn — Trang và Nhóm dùng 2 actor
                        khác nhau. Comment của mỗi bài viết tự dùng actor mặc định
                        &ldquo;apify/facebook-comments-scraper&rdquo;, không cần chọn thêm.
                      </p>
                    </div>
                  )}
                  {source.type === "tiktok" && (
                    <div className="mt-2 space-y-2">
                      <Input
                        value={source.actorId ?? ""}
                        onChange={(e) => updateSource(index, { actorId: e.target.value })}
                        placeholder={`Apify actor ID cho video (mặc định: ${TIKTOK_POST_ACTOR_ID})`}
                        className="w-full"
                      />
                      <p className="text-[11px] text-[var(--color-muted)]">
                        Không có actor TikTok chính thức do Apify duy trì — mặc định dùng actor cộng đồng uy tín
                        nhất hiện có (Clockworks). Comment của mỗi video tự dùng actor mặc định
                        &ldquo;clockworks/tiktok-comments-scraper&rdquo;, không cần chọn thêm.
                      </p>
                    </div>
                  )}
                </div>
              ))}
              <Button type="button" variant="secondary" onClick={addSourceRow}>
                + Thêm nguồn
              </Button>
            </CardBody>
          </Card>

          <Card className="p-6">
            <CardHeader className="border-none p-0 pb-4">
              <CardTitle>Tài khoản chủ sở hữu</CardTitle>
              <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                Nếu email đã có tài khoản, hệ thống dùng lại tài khoản đó — không tạo trùng, không đổi trạng thái thanh
                toán hiện có. Tài khoản mới sẽ nhận email chứa link để tự đặt mật khẩu — admin không đặt/biết mật khẩu
                của doanh nghiệp.
              </p>
            </CardHeader>
            <CardBody className="space-y-4 p-0">
              <div>
                <Label htmlFor="ownerEmail">Email</Label>
                <Input
                  id="ownerEmail"
                  type="email"
                  required
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  placeholder="lienhe@doanhnghiep.com"
                />
              </div>
              <div>
                <Label htmlFor="ownerFullName">Họ tên người đại diện</Label>
                <Input id="ownerFullName" value={ownerFullName} onChange={(e) => setOwnerFullName(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="plan">Loại tài khoản</Label>
                <select id="plan" value={plan} onChange={(e) => setPlan(e.target.value as Plan)} className={`${selectClass} w-full`}>
                  <option value="trial">Dùng thử (mặc định) — hết hạn thì khoá đăng nhập, tự nâng cấp qua VNPay</option>
                  <option value="paid">Chính thức — đã thanh toán qua kênh khác, không giới hạn ngay từ đầu</option>
                </select>
              </div>
            </CardBody>
          </Card>

          <FieldError>{error}</FieldError>
          <Button type="submit" loading={loading}>
            Tạo chủ đề + tài khoản
          </Button>
        </form>

        <aside>
          <Card className="p-6">
            <CardHeader className="border-none p-0 pb-3">
              <CardTitle>Đã tạo trong phiên này</CardTitle>
            </CardHeader>
            <CardBody className="space-y-3 p-0">
              {created.length === 0 && <p className="text-[12.5px] text-[var(--color-muted)]">Chưa tạo chủ đề nào.</p>}
              {created.map((entry, i) => (
                <div key={i} className="rounded-xl border border-[var(--color-line)] p-3">
                  <p className="text-[13px] font-semibold text-[var(--color-ink)]">{entry.topicName}</p>
                  <p className="mt-1 font-mono text-[11.5px] text-[var(--color-muted)]">{entry.ownerEmail}</p>
                  <p className="mt-0.5 text-[11.5px] text-[var(--color-muted)]">
                    {entry.plan === "trial" ? "Dùng thử" : "Chính thức"} — email đặt mật khẩu đã được gửi
                  </p>
                </div>
              ))}
            </CardBody>
          </Card>
          <div className="mt-4 rounded-2xl border border-dashed border-[var(--color-line)] p-4 text-[12.5px] text-[var(--color-muted)]">
            Sau khi tạo, hệ thống tự thu thập phản hồi từ các nguồn đã chọn theo lịch chạy nền và phân tích bằng AI —
            giống mọi chủ đề khác, không cần thao tác thêm.
          </div>
        </aside>
      </div>
    </div>
  );
}
