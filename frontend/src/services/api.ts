import axios from "axios";
import { useAuthStore } from "@/stores/auth";
import { isPublicSignPath } from "@/utils/publicSignRoute";

declare module "axios" {
  interface AxiosRequestConfig {
    /** 로그인 직후 /auth/me 실패 등에서 전역 401 리다이렉트를 막는다 */
    skipAuthRedirect?: boolean;
  }
}

function resolveApiBaseUrl() {
  const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (envBase) {
    // 잘못된 운영값(프론트 도메인) 입력 시 /auth/login 이 405가 날 수 있어 자동 보정
    if (/^https?:\/\/(www\.)?besma\.co\.kr/i.test(envBase) && !/api\.besma\.co\.kr/i.test(envBase)) {
      return "https://api.besma.co.kr";
    }
    return envBase;
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    // 운영 도메인에서 API는 api.besma.co.kr를 우선 사용한다.
    // 서브도메인·Vercel 프리뷰 등도 동일 백엔드를 쓴다(CORS allow_origin_regex와 맞춤).
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
  // 운영 환경에서 외부 연동(기상 등) 지연이 길어질 수 있어 상한을 둔다.
  // 개별 요청에서 timeout을 덮어쓸 수 있다.
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const auth = useAuthStore();
  const token = auth.token || localStorage.getItem("besma_token");
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

