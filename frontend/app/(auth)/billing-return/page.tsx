"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

type PollState = "checking" | "success" | "failed" | "invalid";

const POLL_INTERVAL_MS = 2000;
const MAX_POLLS = 10;

function BillingReturnContent() {
  const searchParams = useSearchParams();
  const txnRef = searchParams.get("txn_ref") || "";
  const code = searchParams.get("code") || "";
  const [state, setState] = useState<PollState>(txnRef && code !== "invalid_signature" ? "checking" : "invalid");
  const pollCount = useRef(0);

  // Poll trạng thái giao dịch thay vì tin ngay vào query param "code" từ VNPay redirect — trạng
  // thái CHÍNH THỨC được chốt ở IPN (server-to-server, xem routes_billing.py::vnpay_ipn), có thể
  // đến sau vài giây so với lúc trình duyệt được redirect về đây.
  useEffect(() => {
    if (state !== "checking") return;
    let cancelled = false;

    async function poll() {
      try {
        const res = await api.get<{ status: string }>(`/billing/status?txn_ref=${encodeURIComponent(txnRef)}`);
        if (cancelled) return;
        if (res.status === "success") {
          setState("success");
          return;
        }
        if (res.status === "failed") {
          setState("failed");
          return;
        }
      } catch {
        // giao dịch chưa kịp tạo hoặc lỗi mạng thoáng qua — thử lại ở lượt poll tiếp theo
      }
      pollCount.current += 1;
      if (pollCount.current >= MAX_POLLS) {
        if (!cancelled) setState("failed");
        return;
      }
      if (!cancelled) setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [state, txnRef]);

  if (state === "checking") {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-muted)]">Đang xác nhận thanh toán...</p>
        </CardBody>
      </Card>
    );
  }

  if (state === "success") {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[var(--color-leaf)]">Thanh toán thành công — tài khoản đã được nâng cấp.</p>
          <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
            Đăng nhập lại
          </Link>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <p className="text-sm text-[var(--color-rose)]">
          Thanh toán không thành công hoặc chưa được xác nhận. Vui lòng thử lại.
        </p>
        <Link href="/login" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
          Quay lại đăng nhập
        </Link>
      </CardBody>
    </Card>
  );
}

export default function BillingReturnPage() {
  return (
    <Suspense fallback={null}>
      <BillingReturnContent />
    </Suspense>
  );
}
