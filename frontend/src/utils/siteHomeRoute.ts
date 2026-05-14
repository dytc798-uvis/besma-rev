/** 현장(SITE) 계정 기본 홈: 모바일은 일지·사진(문서 제출) 탭, 데스크톱은 문서 취합(내 현장 문서). */
export function siteMobileOrDesktopHomeName(): "site-mobile-daily-capture" | "site-documents" {
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches) {
    return "site-mobile-daily-capture";
  }
  return "site-documents";
}
