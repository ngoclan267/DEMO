import { type ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-[var(--color-brand-500)] text-white hover:bg-[var(--color-brand-600)] focus-visible:outline-[var(--color-brand-500)]",
  secondary:
    "bg-white text-[var(--color-ink)] border border-[var(--color-line)] hover:bg-[var(--color-cream-2)] focus-visible:outline-[var(--color-brand-500)]",
  danger: "bg-[var(--color-rose)] text-white hover:opacity-90 focus-visible:outline-[var(--color-rose)]",
  ghost:
    "bg-transparent text-[var(--color-muted)] hover:bg-[var(--color-cream-2)] hover:text-[var(--color-ink)] focus-visible:outline-[var(--color-brand-500)]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", loading, disabled, className, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex h-11 min-h-11 items-center justify-center gap-2 overflow-hidden rounded-md px-5 text-[14px] font-semibold transition-colors",
        "active:translate-y-[1px]",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        VARIANT_CLASSES[variant],
        className,
      )}
      {...props}
    >
      {loading ? "Đang xử lý..." : children}
    </button>
  );
});
