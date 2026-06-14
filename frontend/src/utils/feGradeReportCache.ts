const CACHE_KEY = "besma.feGradeReportCache";
const CACHE_TTL_MS = 5 * 60 * 1000;

export type FeGradeReportCachePayload = {
  gradeStats: Record<string, unknown>;
  period: Record<string, unknown> | null;
  savedAt: number;
};

export function saveFeGradeReportCache(
  gradeStats: Record<string, unknown>,
  period: Record<string, unknown> | null,
) {
  const payload: FeGradeReportCachePayload = { gradeStats, period, savedAt: Date.now() };
  sessionStorage.setItem(CACHE_KEY, JSON.stringify(payload));
}

export function loadFeGradeReportCache(): FeGradeReportCachePayload | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as FeGradeReportCachePayload;
    if (!parsed?.gradeStats || Date.now() - (parsed.savedAt ?? 0) > CACHE_TTL_MS) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}
