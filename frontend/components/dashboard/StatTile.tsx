import Link from "next/link";
import { Card, CardBody } from "@/components/ui/Card";

type Tone = "neutral" | "brand" | "danger";

interface StatTileProps {
  label: string;
  value: string | number;
  hint?: string;
  href?: string;
  tone?: Tone;
}

const TONE_ACCENT: Record<Tone, string> = {
  neutral: "bg-[var(--color-line)]",
  brand: "bg-[var(--color-brand-500)]",
  danger: "bg-[var(--color-sentiment-negative)]",
};

const TONE_VALUE: Record<Tone, string> = {
  neutral: "text-[var(--color-ink)]",
  brand: "text-[var(--color-brand-700)]",
  danger: "text-[var(--color-sentiment-negative)]",
};

export function StatTile({ label, value, hint, href, tone = "neutral" }: StatTileProps) {
  const body = (
    <CardBody className="relative overflow-hidden pl-6">
      <span className={`absolute inset-y-0 left-0 w-1 ${TONE_ACCENT[tone]}`} aria-hidden />
      <p className="text-[11px] font-medium tracking-[0.1em] text-[var(--color-muted)] uppercase">{label}</p>
      <p className={`display-xl mt-1.5 text-[30px] font-semibold tabular-nums ${TONE_VALUE[tone]}`}>{value}</p>
      <p className="mt-1 min-h-4 text-[12px] text-[var(--color-muted)]">{hint}</p>
    </CardBody>
  );

  if (href) {
    return (
      <Link href={href} className="group block">
        <Card className="h-full transition hover:-translate-y-[1px] hover:shadow-[0_18px_50px_rgba(11,18,32,0.08)]">
          {body}
        </Card>
      </Link>
    );
  }

  return <Card className="h-full">{body}</Card>;
}
