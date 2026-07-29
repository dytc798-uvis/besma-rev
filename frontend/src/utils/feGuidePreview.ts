/** 설명서 캡처용 — DB 저장 없이 입력란·등급을 샘플로 표시 (?guidePreview=1) */

export function isFeGuidePreview(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return new URLSearchParams(window.location.search).get("guidePreview") === "1";
  } catch {
    return false;
  }
}

export function getFeGuideScene(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return new URLSearchParams(window.location.search).get("guideScene");
  } catch {
    return null;
  }
}

export interface FeGuideGradeCriterion {
  id: string;
  grades: Array<{ key: string; label: string }>;
}

export function buildSampleScoresForCriteria(criteria: FeGuideGradeCriterion[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of criteria) {
    const byLabel = c.grades.find((g) => g.label.includes("보통"));
    const mid = c.grades[Math.floor((c.grades.length - 1) / 2)];
    const key = byLabel?.key ?? mid?.key;
    if (key) out[c.id] = key;
  }
  return out;
}

export const FE_GUIDE_SAMPLE_LOGIN = {
  team: { loginId: "대우청라-김팀장", password: "<REDACTED_FOR_MIGRATION>" },
  manager: { loginId: "대우청라-박명식", password: "<REDACTED_FOR_MIGRATION>" },
  hq: { loginId: "안전보건-조동문", password: "<REDACTED_FOR_MIGRATION>" },
  ceo: { loginId: "부현대표-김홍수", password: "<REDACTED_FOR_MIGRATION>" },
} as const;
