/** API `frequency` 값 정규화(정렬·그룹 키) */
export function normalizeRequirementFrequencyKey(frequency: string | null | undefined): string {
  const u = (frequency || "").trim().toUpperCase();
  if (!u) return "UNKNOWN";
  if (u === "ROLLING" || u === "ADHOC" || u === "EVENT") return "EPHEMERAL";
  return u;
}

const ORDER_KEYS = ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY", "YEARLY", "EPHEMERAL", "ONE_TIME"] as const;

/** 표·매트릭스에서 주기별로 묶을 때 정렬 순서 (작을수록 앞) */
export function requirementFrequencySortOrder(frequency: string | null | undefined): number {
  const key = normalizeRequirementFrequencyKey(frequency);
  const idx = (ORDER_KEYS as readonly string[]).indexOf(key);
  return idx === -1 ? 99 : idx;
}

/** UI 표기: 일간·주간·월간 … (문서취합 그룹 헤더·셀 공통) */
export function requirementFrequencyKoLabel(frequency: string | null | undefined): string {
  const key = normalizeRequirementFrequencyKey(frequency);
  const labels: Record<string, string> = {
    DAILY: "일간",
    WEEKLY: "주간",
    MONTHLY: "월간",
    QUARTERLY: "분기",
    HALF_YEARLY: "반기",
    YEARLY: "연간",
    EPHEMERAL: "수시",
    ONE_TIME: "1회",
    UNKNOWN: "기타",
  };
  const raw = (frequency || "").trim();
  return labels[key] ?? (raw || "—");
}
