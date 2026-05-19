/** 문서취합에서는 참조·제출 요약 — 행 단위 편집·소통은 전용 대장 화면(백엔드 `ledger_managed`와 동일 코드 집합). */

export const LEDGER_MANAGED_DOCUMENT_TYPE_CODES = ["AUTO_WORKER_OPINION_LOG", "NONCONFORMITY_ACTION_REPORT"] as const;

const LEDGER_SET = new Set<string>(LEDGER_MANAGED_DOCUMENT_TYPE_CODES);

export const LEDGER_MANAGED_UX_MESSAGE =
  "이 문서는 문서 취합에서 제출·이력을 확인하고, 행 단위 처리·소통은 대장 화면에서 진행합니다.";

export function isLedgerManagedDocumentType(code: string | null | undefined): boolean {
  return LEDGER_SET.has((code || "").trim());
}

export type SiteLedgerRouteName = "site-worker-voice" | "site-nonconformities";
export type HqLedgerRouteName = "hq-safe-worker-voice" | "hq-safe-nonconformities";

export function siteLedgerRouteForDocumentType(code: string | null | undefined): SiteLedgerRouteName | null {
  const c = (code || "").trim();
  if (c === "AUTO_WORKER_OPINION_LOG") return "site-worker-voice";
  if (c === "NONCONFORMITY_ACTION_REPORT") return "site-nonconformities";
  return null;
}

export function hqLedgerRouteForDocumentType(code: string | null | undefined): HqLedgerRouteName | null {
  const c = (code || "").trim();
  if (c === "AUTO_WORKER_OPINION_LOG") return "hq-safe-worker-voice";
  if (c === "NONCONFORMITY_ACTION_REPORT") return "hq-safe-nonconformities";
  return null;
}
