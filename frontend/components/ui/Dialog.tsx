"use client";

import { useEffect, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import clsx from "clsx";
import { X } from "@phosphor-icons/react/dist/ssr";

const SIZE_CLASS = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-2xl",
};

const EASE = [0.16, 1, 0.3, 1] as const;

export function Dialog({
  open,
  onClose,
  title,
  description,
  size = "md",
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  size?: keyof typeof SIZE_CLASS;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <motion.button
            type="button"
            aria-label="Đóng"
            onClick={onClose}
            className="absolute inset-0 bg-[var(--color-ink)]/45 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            className={clsx(
              "relative flex max-h-[min(85vh,760px)] w-full flex-col rounded-[16px] border border-[var(--color-line)] bg-white shadow-[0_24px_60px_rgba(11,18,32,0.18)]",
              SIZE_CLASS[size],
            )}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25, ease: EASE }}
          >
            <div className="flex shrink-0 items-start justify-between gap-4 p-6 pb-0">
              <div>
                <h2 id="dialog-title" className="display-xl text-[20px] font-semibold text-[var(--color-ink)]">
                  {title}
                </h2>
                {description && <p className="mt-1.5 text-[13.5px] text-[var(--color-muted)]">{description}</p>}
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Đóng"
                className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-md text-[var(--color-muted)] transition-colors hover:bg-[var(--color-cream-2)] hover:text-[var(--color-ink)]"
              >
                <X size={14} />
              </button>
            </div>

            {children && <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-6 pb-6">{children}</div>}
            {footer && <div className="flex shrink-0 justify-end gap-2 border-t border-[var(--color-line)] p-6">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
