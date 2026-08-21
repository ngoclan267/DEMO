import type { PainPointSummary } from "./types";

/** Cùng thứ tự với _pain_point_order_by() trong src/api/routes_dashboard.py: pain point được đánh
 * dấu ưu tiên (is_priority) luôn đứng đầu, rồi tới severity_avg giảm dần (NULL xuống cuối),
 * post_count là tiêu chí phân định cuối cùng. Dùng để re-sort ngay trên client sau khi toggle
 * is_priority (xem components/painpoints/PriorityToggle.tsx), tránh phải gọi lại API chỉ để thấy
 * đúng thứ tự mới — và để sắp xếp danh sách GỘP nhiều topic (vd trang /pain-points) vốn backend
 * chỉ sắp đúng thứ tự TRONG TỪNG topic, không sắp được xuyên suốt nhiều lần gọi API khác nhau. */
export function sortPainPoints<T extends PainPointSummary>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    if (a.is_priority !== b.is_priority) return a.is_priority ? -1 : 1;
    const severityDiff = (b.severity_avg ?? -Infinity) - (a.severity_avg ?? -Infinity);
    if (severityDiff !== 0) return severityDiff;
    return b.post_count - a.post_count;
  });
}
