export interface EvalAssessmentBrief {
  is_complete?: boolean;
  grade_code?: string;
  grade_label?: string;
}

export interface EvalWorkerCompletion {
  functional_assessment?: EvalAssessmentBrief | null;
  safety_assessment?: EvalAssessmentBrief | null;
}

export function isFunctionalComplete(w: EvalWorkerCompletion): boolean {
  return Boolean(w.functional_assessment?.is_complete);
}

export function isSafetyComplete(w: EvalWorkerCompletion): boolean {
  return Boolean(w.safety_assessment?.is_complete);
}

export function isFullyComplete(w: EvalWorkerCompletion): boolean {
  return isFunctionalComplete(w) && isSafetyComplete(w);
}

/** 기능·안전 중 하나라도 미완료 */
export function isEvalIncomplete(w: EvalWorkerCompletion): boolean {
  return !isFullyComplete(w);
}

export function gradeDisplayLabel(assessment: EvalAssessmentBrief | null | undefined): string {
  if (!assessment?.is_complete) return "미평가";
  const code = assessment.grade_code?.trim();
  if (code) return code;
  return assessment.grade_label?.replace("등급", "") || "—";
}

export function gradeDisplayClass(assessment: EvalAssessmentBrief | null | undefined): string {
  if (!assessment?.is_complete) return "grade-pill grade-pill--pending";
  const code = assessment.grade_code || "";
  if (code === "S") return "grade-pill grade-pill--s";
  if (code === "A") return "grade-pill grade-pill--a";
  if (code === "B") return "grade-pill grade-pill--b";
  if (code === "C") return "grade-pill grade-pill--c";
  if (code === "D") return "grade-pill grade-pill--d";
  return "grade-pill";
}

/** 안전 평가 저장 후 제재 입력 유도 (C·D 등급 또는 만점 S 미달) */
export function needsSanctionPrompt(w: EvalWorkerCompletion): boolean {
  if (!isFullyComplete(w)) return false;
  const codes = [
    w.functional_assessment?.grade_code,
    w.safety_assessment?.grade_code,
  ].filter(Boolean) as string[];
  if (codes.some((c) => c === "C" || c === "D")) return true;
  return codes.some((c) => c !== "S");
}

export type CompletionBadge = "전체완료" | "기능완료" | "안전완료" | null;

export function completionBadge(w: EvalWorkerCompletion): CompletionBadge {
  const f = isFunctionalComplete(w);
  const s = isSafetyComplete(w);
  if (f && s) return "전체완료";
  if (f) return "기능완료";
  if (s) return "안전완료";
  return null;
}

export function completionBadgeClass(label: CompletionBadge): string {
  if (label === "전체완료") return "done-badge done-badge--full";
  if (label === "기능완료") return "done-badge done-badge--functional";
  if (label === "안전완료") return "done-badge done-badge--safety";
  return "";
}

export function countIncompleteWorkers(workers: EvalWorkerCompletion[]): number {
  return workers.filter(isEvalIncomplete).length;
}
