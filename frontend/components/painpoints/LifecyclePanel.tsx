"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { AssigneeRef, LifecycleStatus, PainPointEvent, PainPointSummary } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Label } from "@/components/ui/Input";
import { LIFECYCLE_OPTIONS, LifecycleBadge } from "@/components/ui/Badges";
import { SlaBadge } from "@/components/painpoints/SlaBadge";

/** Gợi ý phòng ban — để ở frontend (không phải enum DB) vì cơ cấu phòng ban hay thay đổi. */
const DEPARTMENTS = ["Phòng CNTT", "Chăm sóc khách hàng", "Vận hành", "Sản phẩm", "Quản lý rủi ro", "Truyền thông"];

const SLA_BY_SEVERITY: Record<string, string> = {
  high: "24 giờ (nghiêm trọng)",
  medium: "72 giờ (trung bình)",
  low: "7 ngày (nhẹ)",
};

const selectClass =
  "w-full rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-[14px] text-[var(--color-ink)] outline-none transition focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-500)]/20";

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

/** ISO -> chuỗi cho <input type="datetime-local"> (giờ ĐỊA PHƯƠNG, không có hậu tố timezone). */
function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const localMs = d.getTime() - d.getTimezoneOffset() * 60000;
  return new Date(localMs).toISOString().slice(0, 16);
}

export function LifecyclePanel({
  painPoint,
  topicId,
  siblings,
  onUpdated,
}: {
  painPoint: PainPointSummary;
  topicId: string;
  siblings: PainPointSummary[];
  onUpdated: (updated: PainPointSummary) => void;
}) {
  const [status, setStatus] = useState<LifecycleStatus>(painPoint.lifecycle_status);
  const [assignee, setAssignee] = useState(painPoint.assigned_user?.id ?? "");
  const [department, setDepartment] = useState(painPoint.department ?? "");
  const [duplicateOf, setDuplicateOf] = useState(painPoint.duplicate_of_id ?? "");
  const [dueAtOverride, setDueAtOverride] = useState(painPoint.due_at_overridden);
  const [dueAtValue, setDueAtValue] = useState(() => toLocalInputValue(painPoint.due_at));
  const [note, setNote] = useState("");
  const [members, setMembers] = useState<AssigneeRef[]>([]);
  const [events, setEvents] = useState<PainPointEvent[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<AssigneeRef[]>(`/topics/${topicId}/members`).then(setMembers).catch(() => {});
  }, [topicId]);

  useEffect(() => {
    api
      .get<PainPointEvent[]>(`/pain-points/${painPoint.id}/events`)
      .then(setEvents)
      .catch(() => {});
  }, [painPoint.id]);

  async function onSave() {
    setError(null);
    if (status === "duplicate" && !duplicateOf) {
      setError("Chọn pain point gốc mà case này bị trùng.");
      return;
    }
    if (dueAtOverride && !dueAtValue) {
      setError("Chọn hạn xử lý hoặc bỏ tuỳ chỉnh để dùng hạn tự động.");
      return;
    }
    setSaving(true);
    try {
      const updated = await api.patch<PainPointSummary>(`/pain-points/${painPoint.id}/lifecycle`, {
        lifecycle_status: status,
        assigned_user_id: assignee || null,
        department: department || null,
        duplicate_of_id: status === "duplicate" ? duplicateOf : null,
        note: note || null,
        due_at_override: dueAtOverride,
        due_at: dueAtOverride ? new Date(dueAtValue).toISOString() : undefined,
      });
      onUpdated(updated);
      setNote("");
      setEvents(await api.get<PainPointEvent[]>(`/pain-points/${painPoint.id}/events`));
      toast.success("Đã lưu thay đổi");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Xử lý</CardTitle>
          <div className="flex items-center gap-2">
            <LifecycleBadge status={painPoint.lifecycle_status} />
            <SlaBadge
              dueAt={painPoint.due_at}
              isBreached={painPoint.is_breached}
              lifecycleStatus={painPoint.lifecycle_status}
            />
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="lifecycle">Trạng thái</Label>
            <select
              id="lifecycle"
              className={selectClass}
              value={status}
              onChange={(e) => setStatus(e.target.value as LifecycleStatus)}
            >
              {LIFECYCLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="assignee">Người phụ trách</Label>
            <select
              id="assignee"
              className={selectClass}
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
            >
              <option value="">— Chưa giao —</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.full_name || m.email}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="department">Phòng ban</Label>
            <select
              id="department"
              className={selectClass}
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              <option value="">— Chưa chọn —</option>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
              {department && !DEPARTMENTS.includes(department) && <option value={department}>{department}</option>}
            </select>
          </div>
        </div>

        {status === "duplicate" && (
          <div>
            <Label htmlFor="duplicateOf">Trùng với pain point</Label>
            <select
              id="duplicateOf"
              className={selectClass}
              value={duplicateOf}
              onChange={(e) => setDuplicateOf(e.target.value)}
            >
              <option value="">— Chọn pain point gốc —</option>
              {siblings
                .filter((s) => s.id !== painPoint.id)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title} ({s.post_count} phản hồi)
                  </option>
                ))}
            </select>
          </div>
        )}

        <div className="rounded-2xl border border-[var(--color-line)] p-3.5">
          <label className="flex items-center gap-2 text-sm font-medium text-[var(--color-ink-2)]">
            <input
              type="checkbox"
              checked={dueAtOverride}
              onChange={(e) => setDueAtOverride(e.target.checked)}
              className="h-4 w-4 rounded border-[var(--color-line)] accent-[var(--color-brand-500)]"
            />
            Tuỳ chỉnh hạn xử lý
          </label>
          {dueAtOverride ? (
            <input
              type="datetime-local"
              className={`${selectClass} mt-2`}
              value={dueAtValue}
              onChange={(e) => setDueAtValue(e.target.value)}
            />
          ) : (
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              Hạn xử lý theo mức nghiêm trọng: <strong className="text-[var(--color-ink-2)]">{SLA_BY_SEVERITY[painPoint.severity_level]}</strong>
              {painPoint.due_at && <> — hạn chót {formatDateTime(painPoint.due_at)}</>}
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="note">Ghi chú xử lý</Label>
          <textarea
            id="note"
            rows={2}
            className={selectClass}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Vd: đã chuyển đội backend, dự kiến vá trong bản 3.4.7"
          />
        </div>

        <div className="flex justify-end">
          <Button onClick={onSave} loading={saving}>
            Lưu thay đổi
          </Button>
        </div>
        {error && <p className="text-sm text-[var(--color-rose)]">{error}</p>}

        {events.length > 0 && (
          <div className="border-t border-[var(--color-line)] pt-3">
            <h4 className="mb-2 text-xs font-semibold tracking-wide text-[var(--color-muted)] uppercase">Lịch sử xử lý</h4>
            <ul className="space-y-1.5">
              {events.map((e) => (
                <li key={e.id} className="flex flex-wrap gap-x-2 text-xs text-[var(--color-muted)]">
                  <span className="text-[var(--color-muted)]">{formatDateTime(e.created_at)}</span>
                  <span className="font-medium text-[var(--color-ink-2)]">{e.user?.full_name || e.user?.email || "—"}</span>
                  <span>
                    {e.from_status} → {e.to_status}
                  </span>
                  {e.note && <span className="text-[var(--color-muted)]">· {e.note}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
