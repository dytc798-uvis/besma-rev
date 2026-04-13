/** 근로자의견·부적합 관리대장: 대시보드 KPI → 목록 `?filter=` 연동 (백엔드 집계와 동일 판정). */

export const LEDGER_DASHBOARD_FILTERS = [
  "unreceived",
  "in_progress",
  "action_completed",
  "db_needed",
  "db_requested",
  "db_pending",
  "db_requests",
  "rejected",
  "reward",
  "db_confirmed",
] as const;

export type LedgerDashboardFilter = (typeof LEDGER_DASHBOARD_FILTERS)[number];

export function isLedgerDashboardFilter(s: string): s is LedgerDashboardFilter {
  return (LEDGER_DASHBOARD_FILTERS as readonly string[]).includes(s);
}

export interface LedgerRowForFilter {
  receipt_decision?: string | null;
  risk_db_request_status?: string | null;
  risk_db_hq_status?: string | null;
  action_status?: string | null;
  ready_for_risk_db?: boolean;
  reward_candidate?: boolean;
  site_rejected?: boolean;
}

function actionBucket(v?: string | null): "in_progress" | "completed" | "other" {
  const x = (v || "not_started").toLowerCase().replace(/-/g, "_");
  if (["in_progress", "doing", "progress"].includes(x)) return "in_progress";
  if (["completed", "complete", "done", "closed", "shared", "share_done"].includes(x)) return "completed";
  return "other";
}

export function rowMatchesLedgerFilter(row: LedgerRowForFilter, f: LedgerDashboardFilter): boolean {
  const rec = (row.receipt_decision || "").toLowerCase();
  const req = (row.risk_db_request_status || "").toLowerCase();
  const hq = (row.risk_db_hq_status || "").toLowerCase();
  const act = actionBucket(row.action_status);
  const siteRej = !!(row.site_rejected ?? false);
  switch (f) {
    case "unreceived":
      return rec === "pending";
    case "in_progress":
      return act === "in_progress";
    case "action_completed":
      return act === "completed";
    case "db_needed":
      return rec === "accepted" && req === "pending" && !siteRej;
    case "db_requested":
      return req === "requested";
    case "db_pending":
      return req === "requested" && hq === "pending";
    case "db_requests":
      return req === "requested";
    case "rejected":
      return hq === "rejected";
    case "reward":
      return !!row.reward_candidate;
    case "db_confirmed":
      return !!row.ready_for_risk_db;
    default:
      return true;
  }
}

export function ledgerFilterDescription(f: LedgerDashboardFilter): string {
  const labels: Record<LedgerDashboardFilter, string> = {
    unreceived: "접수 대기",
    in_progress: "조치중",
    action_completed: "조치 완료",
    db_needed: "DB 등록 요청 필요",
    db_requested: "DB 등록 요청 완료",
    db_pending: "DB 등록 승인 대기",
    db_requests: "DB 등록 요청 건",
    rejected: "DB 반려 건",
    reward: "포상 후보",
    db_confirmed: "DB 승격 확정",
  };
  return labels[f];
}
