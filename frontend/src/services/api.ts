import axios from "axios";
import { useAuthStore } from "@/stores/auth";
import { isPublicSignPath } from "@/utils/publicSignRoute";
import { isStaleAuthError, stampAuthToken } from "@/utils/authRequestStamp";

declare module "axios" {
  interface AxiosRequestConfig {
    /** 로그인 직후 /auth/me 실패 등에서 전역 401 리다이렉트를 막는다 */
    skipAuthRedirect?: boolean;
  }
}

function resolveApiBaseUrl() {
  const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (envBase) {
    if (/^https?:\/\/(www\.)?besma\.co\.kr/i.test(envBase) && !/api\.besma\.co\.kr/i.test(envBase)) {
      return "https://api.besma.co.kr";
    }
    return envBase;
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (
      host === "besma.co.kr" ||
      host === "www.besma.co.kr" ||
      host.endsWith(".besma.co.kr") ||
      host.endsWith(".vercel.app")
    ) {
      return `${window.location.protocol}//api.besma.co.kr`;
    }
    return `${window.location.protocol}//${host}:8001`;
  }
  return "http://127.0.0.1:8001";
}

export const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const auth = useAuthStore();
  const token = auth.token || localStorage.getItem("besma_token");
  stampAuthToken(config, token);
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes("/auth/login")) {
      const auth = useAuthStore();
      if (isStaleAuthError(error.config, auth.token)) {
        return Promise.reject(error);
      }
      auth.logout();
      const skipRedirect = error.config?.skipAuthRedirect === true;
      const onLoginPage =
        typeof window !== "undefined" && window.location.pathname.startsWith("/login");
      const onPublicSignPage =
        typeof window !== "undefined" && isPublicSignPath(window.location.pathname);
      if (!skipRedirect && !onLoginPage && !onPublicSignPage) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
