import axios from "axios";

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
    if (status === 405) {
      return "API 주소 설정 오류입니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.";
    }
    if (!err.response) {
      if (err.code === "ECONNABORTED" || err.message?.includes("timeout")) {
        return "서버 응답이 지연되고 있습니다. 네트워크를 확인한 뒤 다시 시도해 주세요.";
      }
      return "서버에 연결할 수 없습니다. 네트워크와 api.besma.co.kr 접속을 확인해 주세요.";
    }
  }
  return "로그인에 실패했습니다.";
}
