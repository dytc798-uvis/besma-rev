/** 기능인제 — 동의·역할 캐시 (세션 내 재방문 속도). */

const CONSENT_OK_PREFIX = "fe_consent_ok:";
const NAV_ROLE_PREFIX = "fe_nav_role:";

export function consentCacheKey(loginId: string) {
  return `${CONSENT_OK_PREFIX}${loginId}`;
}

export function navRoleCacheKey(loginId: string) {
  return `${NAV_ROLE_PREFIX}${loginId}`;
}

export function readConsentCached(loginId: string): boolean {
  try {
    return sessionStorage.getItem(consentCacheKey(loginId)) === "1";
  } catch {
    return false;
  }
}

export function writeConsentCached(loginId: string, ok: boolean) {
  try {
    if (ok) sessionStorage.setItem(consentCacheKey(loginId), "1");
    else sessionStorage.removeItem(consentCacheKey(loginId));
  } catch {
    /* ignore */
  }
}

export type FeNavRoleCache = "MANAGER" | "TEAM_LEADER";

export function readNavRoleCached(loginId: string): FeNavRoleCache | null {
  try {
    const v = sessionStorage.getItem(navRoleCacheKey(loginId));
    return v === "MANAGER" || v === "TEAM_LEADER" ? v : null;
  } catch {
    return null;
  }
}

export function writeNavRoleCached(loginId: string, role: FeNavRoleCache | null) {
  try {
    if (role) sessionStorage.setItem(navRoleCacheKey(loginId), role);
    else sessionStorage.removeItem(navRoleCacheKey(loginId));
  } catch {
    /* ignore */
  }
}

export function clearFeSessionCache(loginId?: string | null) {
  if (!loginId) return;
  writeConsentCached(loginId, false);
  writeNavRoleCached(loginId, null);
}
