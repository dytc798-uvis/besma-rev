import axios from "axios";

const suspiciousLoginNotice = "의심 정황이 판단되면, 임시 차단하고 자세한 사항은 안전보건실 정상익 차장에게 문의하세요.";

export function formatLoginError(err: unknown): string {
  if (err instanceof Error && err.message === "LOGIN_SUPERSEDED") {
    return "다른 로그인 시도와 겹쳐 취소되었습니다. 다시 시도해 주세요.";
  }
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const url = String(err.config?.url ?? "");

    if (status === 401 && url.includes("/auth/login")) {
      return "로그인 ID 또는 비밀번호가 올바르지 않습니다.";
    }
    if (status === 401 && url.includes("/auth/me")) {
      return "로그인은 되었으나 사용자 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
    }
    if ((status === 403 || status === 429) && url.includes("/auth/login")) {
      return suspiciousLoginNotice;
    }
    if (status === 403 && url.includes("/auth/me")) {
      return `${suspiciousLoginNotice} 현재 세션은 다시 로그인 후 계속 시도해 주세요.`;
    }
    if (status === 405) {
      return "API 형식 설정이 올바르지 않습니다. 네트워크 설정을 확인하고 다시 시도해 주세요.";
    }
    if (!err.response) {
      if (err.code === "ECONNABORTED" || err.message?.includes("timeout")) {
        return "요청이 지연되고 있습니다. 잠시 후 네트워크 환경을 확인해 주세요.";
      }
      return "요청을 보내지 못했습니다. 네트워크/API(api.besma.co.kr) 접근 여부를 확인해 주세요.";
    }
  }
  return "로그인에 실패했습니다.";
}
