/**
 * HQ_SAFE 사이드바: 주요업무 / 부가 메뉴 그룹 + API `menu-order` 결과를 그룹별로 분할해 `order` 스타일에 사용.
 * 라우트 경로·키 문자열은 기존 HQSafeLayout과 동일해야 한다.
 */

/** 주요업무 기본 순서: 기능인제 → 강조 메뉴 → 안전교육 → 사고 → 신규현장 배포(맨 아래) */
export const HQ_SIDEBAR_PRIMARY_KEYS = [
  "functional-eval",
  "notices",
  "safety-policy-goals",
  "risk-library",
  "document-explorer",
  "documents",
  "approvals-history",
  "safety-education",
  "accidents",
  "new-site-deployment",
] as const;

/** 현장 SITE `menu-link-primary`와 동일 정책: 주요 업무 강조 */
export const HQ_SIDEBAR_EMPHASIS_KEYS = [
  "notices",
  "safety-policy-goals",
  "risk-library",
  "document-explorer",
  "documents",
  "approvals-history",
] as const;

export const HQ_SIDEBAR_SECONDARY_KEYS = [
  "site-search",
  "opinions",
  "user-guide",
  "settings",
  "sites",
  "users",
  "pdf-signing",
  "system-backup",
] as const;

const PRIMARY_SET = new Set<string>(HQ_SIDEBAR_PRIMARY_KEYS);
const SECONDARY_SET = new Set<string>(HQ_SIDEBAR_SECONDARY_KEYS);
const EMPHASIS_SET = new Set<string>(HQ_SIDEBAR_EMPHASIS_KEYS);

export function isHqSidebarPrimaryKey(key: string): boolean {
  return PRIMARY_SET.has(key) || key.startsWith("dynamic:");
}

export function isHqSidebarSecondaryKey(key: string): boolean {
  return SECONDARY_SET.has(key);
}

export function isHqSidebarEmphasisKey(key: string): boolean {
  return EMPHASIS_SET.has(key);
}

export function buildHqMenuOrderMaps(
  orderedKeysFromApi: string[] | null | undefined,
  dynamicKeys: string[],
): { primary: Record<string, number>; secondary: Record<string, number> } {
  const ordered = Array.isArray(orderedKeysFromApi) ? orderedKeysFromApi.filter(Boolean) : [];
  const primaryFallback = [...HQ_SIDEBAR_PRIMARY_KEYS, ...dynamicKeys];
  const secondaryFallback = [...HQ_SIDEBAR_SECONDARY_KEYS];

  const primaryOrdered: string[] = [];
  const secondaryOrdered: string[] = [];
  for (const k of ordered) {
    if (isHqSidebarPrimaryKey(k)) primaryOrdered.push(k);
    else if (isHqSidebarSecondaryKey(k)) secondaryOrdered.push(k);
  }

  const primaryMerged = [...primaryOrdered, ...primaryFallback.filter((k) => !primaryOrdered.includes(k))];
  const secondaryMerged = [...secondaryOrdered, ...secondaryFallback.filter((k) => !secondaryOrdered.includes(k))];

  return {
    primary: Object.fromEntries(primaryMerged.map((k, i) => [k, i + 1])),
    secondary: Object.fromEntries(secondaryMerged.map((k, i) => [k, i + 1])),
  };
}
