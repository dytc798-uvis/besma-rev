import axios from "axios";
import { api } from "@/services/api";

export interface RiskDbHqKpis {
  pending_requests: number;
  pending_approval: number;
  rejected: number;
  approved: number;
  reward_candidates: number;
}

export interface RiskDbSiteKpis {
  unreceived: number;
  in_progress: number;
  action_completed: number;
  db_request_needed: number;
  db_requested: number;
}

export interface RiskDbOverviewPayload {
  hq: {
    combined: RiskDbHqKpis;
    worker_voice: RiskDbHqKpis;
    nonconformity: RiskDbHqKpis;
  };
  site: {
    combined: RiskDbSiteKpis;
    worker_voice: RiskDbSiteKpis;
    nonconformity: RiskDbSiteKpis;
  };
}

/**
 * 운영에 아직 `/dashboard/risk-db-overview`가 없을 때(404)에도 대시보드 전체가 실패하지 않도록 한다.
 * 그 외 오류도 null로 내려 기존 `.catch(() => null)` 동작과 맞춘다.
 */
export async function fetchRiskDbOverviewOptional(): Promise<RiskDbOverviewPayload | null> {
  try {
    const res = await api.get<RiskDbOverviewPayload>("/dashboard/risk-db-overview");
    return res.data;
  } catch (err: unknown) {
    if (import.meta.env.DEV && axios.isAxiosError(err) && err.response?.status === 404) {
      console.info("[BESMA] GET /dashboard/risk-db-overview → 404 (구 API). 백엔드 배포 후 집계가 표시됩니다.");
    }
    return null;
  }
}
