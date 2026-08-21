import { useEffect, useRef } from "react";

/** Gọi lại `callback` mỗi `intervalMs` — dùng để tự làm mới số liệu (vd đếm phản hồi đã phân tích)
 * khi backend chạy nền (scheduler) cập nhật dữ liệu, mà không cần người dùng tải lại trang.
 *
 * Dùng ref cho callback thay vì đưa thẳng vào dependency của interval effect — nếu không, callback
 * đổi tham chiếu mỗi lần re-render (rất phổ biến với closure đọc state) sẽ làm setInterval bị huỷ
 * và tạo lại liên tục, có thể khiến nó không bao giờ thực sự kịp bắn. `enabled=false` tạm dừng hẳn
 * (vd khi chưa đăng nhập) mà không cần unmount component gọi hook này. */
export function usePolling(callback: () => void, intervalMs: number, enabled = true) {
  const callbackRef = useRef(callback);
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => callbackRef.current(), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
}
