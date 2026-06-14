export interface EvalAssessmentBrief {
  is_complete?: boolean;
  grade_code?: string;
  grade_label?: string;
  scores?: Record<string, string>;
}

export interface EvalWorkerCompletion {
  functional_assessment?: EvalAssessmentBrief | null;
  safety_assessment?: EvalAssessmentBrief | null;
  sanction_status?: string;
}

/** 엑셀·백엔드와 동일 — D등급 없음, 구 DB D는 C로 표시 */
export function normalizeGradeCode(code: string | null | undefined): string {
  const text = (code || "").trim().toUpperCase();
  if (!text) return "";
  if (text === "D") return "C";
  return text;
}

/** 점수 비율 → 등급 라벨 (엑셀 IF >85 S, >70 A, >50 B, >0 C) */
export function scoreRatioToGradeLabel(ratio: number): string {
  const pct = ratio * 100;
  if (pct > 85) return "S등급";
  if (pct > 70) return "A등급";
  if (pct > 50) return "B등급";
  if (pct > 0) return "C등급";
  return "—";
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
  const code = normalizeGradeCode(assessment.grade_code);
  if (code) return code;
  return assessment.grade_label?.replace("등급", "") || "—";
}

export function gradeDisplayClass(assessment: EvalAssessmentBrief | null | undefined): string {
  if (!assessment?.is_complete) return "grade-pill grade-pill--pending";
  const code = normalizeGradeCode(assessment.grade_code);
  if (code === "S") return "grade-pill grade-pill--s";
  if (code === "A") return "grade-pill grade-pill--a";
  if (code === "B") return "grade-pill grade-pill--b";
  if (code === "C") return "grade-pill grade-pill--c";
  return "grade-pill";
}

export function hasLowGrade(w: EvalWorkerCompletion): boolean {
  const codes = [w.functional_assessment?.grade_code, w.safety_assessment?.grade_code]
    .filter(Boolean)
    .map((c) => normalizeGradeCode(c));
  return codes.some((c) => c === "C");
}

export function hasSanctionRecord(w: EvalWorkerCompletion): boolean {
  const status = (w.sanction_status || "").trim().toUpperCase();
  return Boolean(status && status !== "NONE");
}

export function sanctionStatusClass(status: string): string {
  const s = (status || "").toUpperCase();
  if (s.includes("EXPULSION") || s.includes("BAN")) return "danger";
  if (s.includes("WARNING") || s.includes("TRAINING")) return "warn";
  return "normal";
}

export interface SafetySanctionDisplay {
  safetyLabel: string;
  safetyClass: string;
  subLabel: string;
  subClass: string;
}

/** 현황표 안전·제재 통합 열 */
export function safetySanctionDisplay(
  w: EvalWorkerCompletion & { sanction_status?: string; sanction_status_label?: string },
): SafetySanctionDisplay {
  const safetyLabel = gradeDisplayLabel(w.safety_assessment);
  const safetyClass = gradeDisplayClass(w.safety_assessment);
  let subLabel = "";
  let subClass = "status-pill normal";

  if (isSafetyComplete(w)) {
    if (needsSanctionPrompt(w)) {
      subLabel = "제재 필요";
      subClass = "status-pill pending";
    } else if (hasSanctionRecord(w)) {
      subLabel = (w.sanction_status_label || "제재").trim();
      subClass = `status-pill ${sanctionStatusClass(w.sanction_status || "")}`;
    }
  }

  return { safetyLabel, safetyClass, subLabel, subClass };
}

/** 현황표 안전·제재 — 한 줄 텍스트 */
export function safetySanctionLine(
  w: EvalWorkerCompletion & { sanction_status?: string; sanction_status_label?: string },
): string {
  const { safetyLabel, subLabel } = safetySanctionDisplay(w);
  if (!subLabel || subLabel === "해당 없음") return safetyLabel;
  return `${safetyLabel} · ${subLabel}`;
}

/** 제재 이력 또는 C등급 — 평가 결과 강조 */
export function workerNeedsHighlight(w: EvalWorkerCompletion): boolean {
  return hasSanctionRecord(w);
}

export function workerRowHighlightClass(w: EvalWorkerCompletion): string {
  return workerNeedsHighlight(w) ? "row-highlight--alert" : "";
}

/** 안전(2-2) 평가표 — 항목 중 하나라도 우수(TOP) 미만 */
export function hasSafetyAssessmentIssue(w: EvalWorkerCompletion): boolean {
  const assessment = w.safety_assessment;
  if (!assessment?.is_complete || !assessment.scores) return false;
  return Object.values(assessment.scores).some((key) => Boolean(key) && key !== "TOP");
}

/** 안전(2-2) 평가표 — 「문제」(BOTTOM) 항목 존재 */
export function hasSafetyBottomIssue(w: EvalWorkerCompletion): boolean {
  const assessment = w.safety_assessment;
  if (!assessment?.is_complete || !assessment.scores) return false;
  return Object.values(assessment.scores).some((key) => key === "BOTTOM");
}

/** 안전 평가 저장 후 제재 입력 유도 — 「문제」(BOTTOM) 항목이 있을 때만 */
export function needsSanctionPrompt(w: EvalWorkerCompletion): boolean {
  return isSafetyComplete(w) && hasSafetyBottomIssue(w);
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

/** 평가 큐에서 다음 미완료 근로자 (이름순, afterId 다음부터 순환) */
export function findNextIncompleteWorker<T extends EvalWorkerCompletion & { id: number; name?: string }>(
  workers: T[],
  afterId: number | null,
): T | null {
  const list = [...workers].sort((a, b) => (a.name || "").localeCompare(b.name || "", "ko"));
  if (!list.length) return null;
  const start = afterId == null ? 0 : list.findIndex((w) => w.id === afterId) + 1;
  for (let i = start; i < list.length; i++) {
    if (isEvalIncomplete(list[i])) return list[i];
  }
  for (let i = 0; afterId != null && i < start; i++) {
    if (isEvalIncomplete(list[i])) return list[i];
  }
  return null;
}
