import type { InternalAxiosRequestConfig } from "axios";

/** 요청 시점 토큰 — 401 응답이 새 로그인을 지우지 않도록 비교용 */
export function stampAuthToken(config: InternalAxiosRequestConfig, token: string | null) {
  config.besmaAuthToken = token;
}

export function isStaleAuthError(
  config: InternalAxiosRequestConfig | undefined,
  currentToken: string | null,
): boolean {
  const used = config?.besmaAuthToken;
  if (!used) return false;
  return used !== (currentToken ?? null);
}

declare module "axios" {
  interface InternalAxiosRequestConfig {
    besmaAuthToken?: string | null;
    skipAuthRedirect?: boolean;
  }
}
