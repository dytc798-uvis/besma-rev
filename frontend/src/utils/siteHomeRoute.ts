const MOBILE_OPS_SITE_LOGINS = new Set(["site01", "site02", "site03", "site04", "site05"]);

export function isMobileOpsSiteLogin(loginId?: string | null): boolean {
  return MOBILE_OPS_SITE_LOGINS.has((loginId || "").trim().toLowerCase());
}

/** SITE account default route. */
export function siteMobileOrDesktopHomeName(
  loginId?: string | null,
): "site-mobile-ops" | "site-field-form-uploads" {
  if (isMobileOpsSiteLogin(loginId)) {
    return "site-mobile-ops";
  }
  return "site-field-form-uploads";
}
