const MOBILE_OPS_SITE_LOGINS = new Set(["site01", "site02", "site03", "site04", "site05"]);

export function isMobileOpsSiteLogin(loginId?: string | null): boolean {
  return MOBILE_OPS_SITE_LOGINS.has((loginId || "").trim().toLowerCase());
}

/** 모든 SITE 계정의 로그인 첫 화면은 체감온도 기록이다. */
export function siteMobileOrDesktopHomeName(
  _loginId?: string | null,
): "site-heat-stress" {
  return "site-heat-stress";
}
