import clsx from "clsx";

export function ToggleSwitch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        "relative h-6 w-11 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)]" : "border-[var(--color-line)] bg-white",
      )}
    >
      <span
        className={clsx(
          "absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-white shadow transition-all",
          checked ? "left-[22px]" : "left-[3px]",
        )}
      />
    </button>
  );
}
