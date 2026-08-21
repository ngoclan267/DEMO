"use client";

import { useEffect, useState } from "react";
import { CheckCircle } from "@phosphor-icons/react/dist/ssr";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { BillingPlan } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Topbar } from "@/components/layout/Topbar";

function formatVnd(value: number): string {
  return `${value.toLocaleString("vi-VN")}đ`;
}

export default function UpgradePlanPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkingOutPlanId, setCheckingOutPlanId] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ plans: BillingPlan[] }>("/billing/plans")
      .then((res) => setPlans(res.plans))
      .catch(() => setError("Không tải được danh sách gói"));
  }, []);

  async function onChoosePlan(planId: string) {
    setError(null);
    setCheckingOutPlanId(planId);
    try {
      // Hiện chỉ 1 gói nên /billing/checkout không cần nhận planId — mọi gói tương lai vẫn
      // charge đúng subscription_price_vnd cho tới khi backend hỗ trợ nhiều mức giá thật sự.
      const { payment_url } = await api.post<{ payment_url: string }>("/billing/checkout");
      window.location.assign(payment_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được yêu cầu thanh toán");
      setCheckingOutPlanId(null);
    }
  }

  return (
    <div>
      <Topbar title="Nâng cấp tài khoản" subtitle="Chọn gói phù hợp để tiếp tục sử dụng không giới hạn." />

      <div className="pt-6">
        {user?.is_paid && (
          <Card className="mb-6 p-5">
            <CardBody className="p-0">
              <p className="text-[13.5px] text-[var(--color-ink)]">
                Tài khoản của bạn đã ở gói chính thức — không cần nâng cấp thêm.
              </p>
            </CardBody>
          </Card>
        )}

        {error && <p className="mb-4 text-sm text-[var(--color-rose)]">{error}</p>}
        {plans === null && !error && <p className="text-sm text-[var(--color-muted)]">Đang tải danh sách gói...</p>}

        {plans && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {plans.map((plan) => (
              <Card key={plan.id} className="flex flex-col p-6">
                <CardBody className="flex flex-1 flex-col p-0">
                  <p className="text-[15px] font-semibold text-[var(--color-ink)]">{plan.name}</p>
                  <p className="mt-2 text-[26px] font-semibold text-[var(--color-ink)]">
                    {formatVnd(plan.price_vnd)}
                    <span className="text-[13px] font-normal text-[var(--color-muted)]">/tháng</span>
                  </p>
                  <div className="mt-3 flex items-start gap-2 text-[13px] text-[var(--color-ink-2)]">
                    <CheckCircle size={16} weight="fill" className="mt-0.5 shrink-0 text-[var(--color-leaf)]" />
                    <span>{plan.description}</span>
                  </div>
                  <Button
                    className="mt-5 w-full"
                    disabled={user?.is_paid}
                    loading={checkingOutPlanId === plan.id}
                    onClick={() => onChoosePlan(plan.id)}
                  >
                    {user?.is_paid ? "Đang dùng gói này" : "Chọn gói này"}
                  </Button>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
