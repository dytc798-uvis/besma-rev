/** 현장(SITE) 계정 기본 홈: 모바일은 일지·사진 탭, 데스크톱은 작업계획·TBM 탭. */
export function siteMobileOrDesktopHomeName(): "site-mobile-daily-capture" | "site-mobile-ops" {
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches) {
    return "site-mobile-daily-capture";
  }
  return "site-mobile-ops";
}
