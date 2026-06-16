const SAMSUNG_RECOGNITION_SITE_LOGINS = new Set(["site01", "site02", "site03", "site04", "site05"]);

export function isSamsungRecognitionSiteLogin(loginId?: string | null): boolean {
  return SAMSUNG_RECOGNITION_SITE_LOGINS.has((loginId || "").trim().toLowerCase());
}

/** SITE account default route. Samsung recognition pilot accounts stay out of functional eval. */
export function siteMobileOrDesktopHomeName(
  loginId?: string | null,
): "site-mobile-ops" | "site-functional-eval" {
  if (isSamsungRecognitionSiteLogin(loginId)) {
    return "site-mobile-ops";
  }
  return "site-functional-eval";
}

