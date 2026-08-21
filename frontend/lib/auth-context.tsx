"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import type { User } from "./types";
import { usePolling } from "./usePolling";

// Backend chạy nền (scheduler) liên tục phân tích thêm phản hồi — làm mới user mỗi 30s để các số
// phụ thuộc (vd trial_daily_responses_analyzed ở TrialQuotaBanner) tự "nhảy số" mà không cần tải
// lại trang. 30s đủ nhanh để cảm nhận được thay đổi, đủ thưa để không tốn quota API vô ích.
const USER_POLL_INTERVAL_MS = 30_000;

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  /** Xác thực email bằng token trong link, rồi đăng nhập luôn (backend trả access_token) — chỉ còn
   * dùng cho tài khoản tự đăng ký TỪ TRƯỚC (giữ tương thích ngược, xem routes_auth.py). Tài khoản
   * mới giờ luôn do platform admin/chủ sở hữu chủ đề tạo (is_verified=True ngay từ đầu), không còn
   * đi qua bước xác thực email này. */
  verifyEmail: (token: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  async function refreshUser() {
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
    } catch {
      setUser(null);
      if (typeof window !== "undefined") sessionStorage.removeItem("access_token");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (typeof window !== "undefined" && sessionStorage.getItem("access_token")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount, standard pattern
      refreshUser();
    } else {
      setLoading(false);
    }
  }, []);

  // enabled=!!user: chỉ chạy khi ĐANG đăng nhập — trang public (login/contact) không cần tự làm
  // mới, cũng tránh gọi refreshUser() lặp khi chưa có token (chỉ tổ báo lỗi 401 vô ích).
  usePolling(refreshUser, USER_POLL_INTERVAL_MS, !!user);

  /** `identifier`: email hoặc tên đăng nhập — backend chấp nhận cả hai (xem routes_auth.login). */
  async function login(identifier: string, password: string) {
    const res = await api.post<{ access_token: string }>("/auth/login", { identifier, password });
    sessionStorage.setItem("access_token", res.access_token);
    await refreshUser();
  }

  async function verifyEmail(token: string) {
    const res = await api.post<{ access_token: string }>("/auth/verify-email", { token });
    sessionStorage.setItem("access_token", res.access_token);
    await refreshUser();
  }

  function logout() {
    sessionStorage.removeItem("access_token");
    setUser(null);
    router.push("/login");
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, verifyEmail, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
