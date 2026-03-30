/** 공개 데모: 설정 시 문서취합·미결재 API에 site_code로 전달. 홈 모니터링은 기본 접기. */
export const DEMO_PILOT_SITE_CODE =
  (import.meta.env.VITE_DEMO_PILOT_SITE_CODE as string | undefined)?.trim() || "";

export const isDemoPilotSiteScopeEnabled = DEMO_PILOT_SITE_CODE.length > 0;
