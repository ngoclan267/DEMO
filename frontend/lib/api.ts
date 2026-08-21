const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  // detail thô từ backend — giữ nguyên object (không stringify) để nơi gọi đọc được field có cấu
  // trúc riêng nếu có, không chỉ đọc được message dạng chuỗi.
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  // sessionStorage (không phải localStorage): phiên đăng nhập chỉ tồn tại trong tab/cửa sổ hiện
  // tại — mở tab mới hoặc quay lại sau khi đóng trình duyệt luôn phải đăng nhập lại, phù hợp ứng
  // dụng có dữ liệu nhạy cảm ngân hàng thay vì giữ đăng nhập vô thời hạn như trước.
  return sessionStorage.getItem("access_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let message = res.statusText;
    let rawDetail: unknown;
    try {
      const body = await res.json();
      rawDetail = body?.detail;
      if (rawDetail) message = typeof rawDetail === "string" ? rawDetail : JSON.stringify(rawDetail);
    } catch {
      // body không phải JSON hợp lệ — giữ nguyên statusText
    }
    throw new ApiError(res.status, message, rawDetail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string) => request<T>(path, { method: "GET" }),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
};
