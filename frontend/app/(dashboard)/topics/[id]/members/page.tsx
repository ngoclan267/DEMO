"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { AssigneeRef, Topic } from "@/lib/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Label, FieldError } from "@/components/ui/Input";
import { Topbar } from "@/components/layout/Topbar";

/** Chữ cái đầu để làm avatar khi thành viên chưa có ảnh đại diện. */
function initialsOf(nameOrEmail: string): string {
  const trimmed = nameOrEmail.trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return trimmed.slice(0, 2).toUpperCase();
}

export default function TopicMembersPage() {
  const { id } = useParams<{ id: string }>();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [members, setMembers] = useState<AssigneeRef[] | null>(null);
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Giá trị đang gõ dở trong ô sửa phòng ban tại chỗ, theo userId — chỉ 1 dòng edit tại 1 thời điểm
  // không bắt buộc, nhưng dùng map theo id để nhiều dòng giữ trạng thái riêng nếu người dùng bấm
  // qua lại nhiều dòng trước khi lưu.
  const [departmentDrafts, setDepartmentDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount, standard pattern
    setLoadError(null);
    Promise.all([api.get<Topic>(`/topics/${id}`), api.get<AssigneeRef[]>(`/topics/${id}/members`)])
      .then(([topicRes, membersRes]) => {
        setTopic(topicRes);
        setMembers(membersRes);
      })
      .catch(() => setLoadError("Không tải được danh sách thành viên."));
  }, [id]);

  const isOwner = !!topic?.is_owner;
  // Chủ sở hữu luôn là người đầu tiên trong danh sách trả về (xem list_members ở backend).
  const ownerId = members?.[0]?.id;

  // Gợi ý phòng ban đã dùng trong chủ đề này — tránh gõ lệch chữ (vd "CNTT" vs "IT") làm phân mảnh
  // định tuyến tự động (xem src/analysis/department_routing.py — khớp CHÍNH XÁC theo chuỗi).
  const departmentSuggestions = Array.from(
    new Set((members ?? []).map((m) => m.department).filter((d): d is string => !!d)),
  );

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.post(`/topics/${id}/members`, { email, department: department.trim() || null });
      setMembers(await api.get<AssigneeRef[]>(`/topics/${id}/members`));
      setEmail("");
      setDepartment("");
      toast.success("Đã thêm thành viên");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không thêm được thành viên");
    } finally {
      setSaving(false);
    }
  }

  async function onRemove(userId: string) {
    setError(null);
    try {
      await api.delete(`/topics/${id}/members/${userId}`);
      setMembers((prev) => (prev ? prev.filter((m) => m.id !== userId) : prev));
      toast.success("Đã xoá thành viên");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không xoá được thành viên");
    }
  }

  async function onSaveDepartment(userId: string) {
    const value = (departmentDrafts[userId] ?? "").trim();
    try {
      const updated = await api.patch<AssigneeRef>(`/topics/${id}/members/${userId}`, { department: value || null });
      setMembers((prev) => (prev ? prev.map((m) => (m.id === userId ? updated : m)) : prev));
      setDepartmentDrafts((prev) => {
        const next = { ...prev };
        delete next[userId];
        return next;
      });
      toast.success("Đã cập nhật phòng ban");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Không cập nhật được phòng ban");
    }
  }

  return (
    <div className="max-w-2xl">
      <Topbar title="Thành viên" subtitle={topic ? topic.name : undefined} />

      <div className="pt-6">
        <Link
          href={`/topics/${id}`}
          className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]"
        >
          ← Quay lại dashboard
        </Link>

        <Card className="mt-4 mb-6 overflow-hidden">
          <CardHeader>
            <CardTitle>Danh sách thành viên</CardTitle>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">
              Thành viên xem được dashboard và xử lý case, nhưng không sửa/xoá được chủ đề.
            </p>
          </CardHeader>
          <CardBody className="p-0">
            {loadError && <p className="p-5 text-sm text-[var(--color-rose)]">{loadError}</p>}

            {members === null && !loadError && <p className="p-5 text-sm text-[var(--color-muted)]">Đang tải...</p>}

            <ul className="divide-y divide-[var(--color-line)]">
              <AnimatePresence initial={false}>
                {members?.map((m, index) => {
                  const isTopicOwner = m.id === ownerId;
                  const displayName = m.full_name || m.email;
                  return (
                    <motion.li
                      key={m.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.25, delay: Math.min(index, 8) * 0.03 }}
                      className="flex items-center gap-3 px-5 py-3.5"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--color-brand-500)] text-[12px] font-semibold text-white">
                        {initialsOf(displayName)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-medium text-[var(--color-ink)]">{displayName}</p>
                        {m.full_name && <p className="truncate text-xs text-[var(--color-muted)]">{m.email}</p>}
                      </div>
                      {!isTopicOwner && isOwner && (
                        <>
                          <input
                            list="department-suggestions"
                            value={departmentDrafts[m.id] ?? m.department ?? ""}
                            onChange={(e) => setDepartmentDrafts((prev) => ({ ...prev, [m.id]: e.target.value }))}
                            onBlur={() => {
                              if ((departmentDrafts[m.id] ?? m.department ?? "") !== (m.department ?? "")) {
                                onSaveDepartment(m.id);
                              }
                            }}
                            placeholder="Phòng ban"
                            className="h-8 w-32 shrink-0 rounded-md border border-[var(--color-line)] bg-white px-2 text-xs text-[var(--color-ink)] outline-none focus:border-[var(--color-brand-500)]"
                          />
                        </>
                      )}
                      {isTopicOwner ? (
                        <span className="shrink-0 rounded-full bg-[var(--color-brand-50)] px-2.5 py-0.5 text-xs font-medium text-[var(--color-brand-700)]">
                          Chủ sở hữu
                        </span>
                      ) : (
                        isOwner && (
                          <button
                            onClick={() => onRemove(m.id)}
                            className="shrink-0 text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-rose)]"
                          >
                            Xoá
                          </button>
                        )
                      )}
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
            <datalist id="department-suggestions">
              {departmentSuggestions.map((d) => (
                <option key={d} value={d} />
              ))}
            </datalist>
          </CardBody>
        </Card>

        {isOwner && (
          <Card className="p-6">
            <CardHeader className="border-none p-0 pb-4">
              <CardTitle>Thêm nhân viên</CardTitle>
            </CardHeader>
            <CardBody className="p-0">
              <form onSubmit={onAdd} className="space-y-4">
                <div>
                  <Label htmlFor="email">Email nhân viên</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="dongnghiep@congty.com"
                  />
                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    Nếu email đã có tài khoản trên hệ thống, thêm luôn làm thành viên. Nếu chưa, hệ thống sẽ tự tạo
                    tài khoản mới và gửi email đặt mật khẩu.
                  </p>
                </div>
                <div>
                  <Label htmlFor="member-department">Phòng ban (không bắt buộc)</Label>
                  <Input
                    id="member-department"
                    list="department-suggestions"
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    placeholder="vd Phòng CNTT"
                  />
                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    Cần điền nếu chủ đề bật &quot;Tự động phân việc theo phòng ban&quot; — hệ thống dựa vào phòng ban của
                    từng nhân viên để gán pain point mới cho đúng người xử lý.
                  </p>
                </div>
                <FieldError>{error}</FieldError>
                <Button type="submit" loading={saving}>
                  Thêm thành viên
                </Button>
              </form>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
