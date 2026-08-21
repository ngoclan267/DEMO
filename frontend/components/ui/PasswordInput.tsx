"use client";

import { useState, type InputHTMLAttributes } from "react";
import clsx from "clsx";
import { Eye, EyeSlash } from "@phosphor-icons/react/dist/ssr";
import { Input } from "@/components/ui/Input";

/** Ô nhập mật khẩu kèm nút con mắt để bật/tắt hiển thị mật khẩu đang gõ. */
export function PasswordInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} className={clsx("pr-11", className)} {...props} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        // tabIndex=-1: người dùng gõ xong mật khẩu nhấn Tab là sang ô tiếp theo, không bị dừng ở
        // nút con mắt. Vẫn bấm chuột được và vẫn có aria-label cho trình đọc màn hình.
        tabIndex={-1}
        aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]"
      >
        {visible ? <EyeSlash size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
