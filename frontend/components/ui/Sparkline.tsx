/** Đường xu hướng nhỏ, thuần SVG (không dùng recharts — quá nặng cho 1 đường mảnh trong thẻ/card).
 * Chuẩn hoá `data` về khung viewBox 100x30, không trục/không nhãn, chỉ để gợi ý xu hướng. */
export function Sparkline({
  data,
  stroke = "var(--color-brand-500)",
  className = "h-8 w-full",
}: {
  data: number[];
  stroke?: string;
  className?: string;
}) {
  if (data.length < 2) {
    return <svg viewBox="0 0 100 30" className={className} preserveAspectRatio="none" aria-hidden />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = 100 / (data.length - 1);
  const points = data
    .map((value, i) => {
      const x = i * step;
      const y = 30 - ((value - min) / range) * 28 - 1; // 1px lề trên/dưới để nét không bị cắt
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 30" className={className} preserveAspectRatio="none" aria-hidden>
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
