export interface EvalAssessmentBrief {
  is_complete?: boolean;
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
