/** 2-2 안전 평가 항목 → 제재 위반 코드 (DECISION-087 제재표) */
export const SAFETY_CRITERION_VIOLATION: Record<string, string> = {
  c1: "INST_TBM",
  c2: "INST_QR_ACTIVITY",
  c3: "INST_PPE",
  c4: "INST_TOOL",
  c5: "INST_WALKING",
  c6: "INST_SMOKING_AREA",
  c7: "INST_HOUSEKEEPING",
  c8: "INST_HOUSEKEEPING",
};

export const VIOLATION_SAFETY_CRITERIA: Record<string, string[]> = {
  INST_TBM: ["c1"],
  INST_QR_ACTIVITY: ["c2"],
  SUBCONTRACTOR_SAFETY_RULE: ["c2"],
  INST_PPE: ["c3"],
  INST_TOOL: ["c4"],
  INST_WALKING: ["c5"],
  INST_SMOKING_AREA: ["c6"],
  INST_HOUSEKEEPING: ["c7", "c8"],
};

export const DEFAULT_SAFETY_VIOLATION_CODE = "SUBCONTRACTOR_SAFETY_RULE";

export interface SafetyCriterionBrief {
  id: string;
  title: string;
}

export interface SafetySanctionPrefill {
  violationCode: string;
  note: string;
}

export function listSafetyBottomCriteria(
  scores: Record<string, string>,
  criteria: SafetyCriterionBrief[],
): SafetyCriterionBrief[] {
  const byId = Object.fromEntries(criteria.map((c) => [c.id, c]));
  return criteria
    .filter((c) => scores[c.id] === "BOTTOM")
    .map((c) => byId[c.id] || c);
}

export function buildSanctionPrefillFromSafetyScores(
  scores: Record<string, string>,
  criteria: SafetyCriterionBrief[],
): SafetySanctionPrefill | null {
  const problems = listSafetyBottomCriteria(scores, criteria);
  if (!problems.length) return null;
  const violationCode = SAFETY_CRITERION_VIOLATION[problems[0].id] || DEFAULT_SAFETY_VIOLATION_CODE;
  const note = problems.map((p) => `${p.title}: 문제`).join(", ");
  return { violationCode, note };
}

export function hasSafetyBottomScores(scores: Record<string, string> | undefined | null): boolean {
  if (!scores) return false;
  return Object.values(scores).some((key) => key === "BOTTOM");
}
