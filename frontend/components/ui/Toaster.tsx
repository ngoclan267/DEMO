"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      richColors
      theme="light"
      toastOptions={{
        className: "text-[13.5px]",
        style: {
          background: "var(--color-cream)",
          border: "1px solid var(--color-line)",
          color: "var(--color-ink)",
          borderRadius: "16px",
        },
      }}
    />
  );
}
