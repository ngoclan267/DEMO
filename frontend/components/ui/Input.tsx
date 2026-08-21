import { type InputHTMLAttributes, type LabelHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={clsx(
          "h-12 w-full rounded-xl border border-[var(--color-line)] bg-white px-4 text-[14px] text-[var(--color-ink)] placeholder:text-[var(--color-muted)]",
          "outline-none transition focus:border-[var(--color-brand-500)] focus:ring-2 focus:ring-[var(--color-brand-500)]/20",
          className,
        )}
        {...props}
      />
    );
  },
);

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={clsx("mb-1.5 block text-[12px] font-medium tracking-[0.08em] text-[var(--color-muted)] uppercase", className)}
      {...props}
    />
  );
}

export function FieldError({ children }: { children?: string | null }) {
  if (!children) return null;
  return <p className="mt-1 text-sm text-[var(--color-rose)]">{children}</p>;
}
