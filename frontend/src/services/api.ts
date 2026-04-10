import axios from "axios";
import { useAuthStore } from "@/stores/auth";

function resolveApiBaseUrl() {
  const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (envBase) {
    // 잘못된 운영값(besma.co.kr) 입력 시 로그인 API가 405가 날 수 있어 자동 보정
    if (/^https?:\/\/(www\.)?besma\.co\.kr\/?$/i.test(envBase)) {
      return "https://api.besma.co.kr";
    }
    return envBase;
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    // 운영 도메인에서 API는 api.besma.co.kr를 우선 사용한다.
    if (host === "besma.co.kr" || host === "www.besma.co.kr") {
      return `${window.location.protocol}//api.besma.co.kr`;
    }
    return `${window.location.protocol}//${host}:8001`;
  }
  return "http://127.0.0.1:8001";
}

export const api = axios.create({
  baseURL: resolveApiBaseUrl(),
});

api.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes("/auth/login")) {
      const auth = useAuthStore();
      auth.logout();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

