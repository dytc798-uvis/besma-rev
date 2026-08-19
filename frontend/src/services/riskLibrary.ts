import { api } from "@/services/api";

export interface RiskLibraryItem {
  risk_revision_id: number;
  risk_item_id: number;
  unit_work: string | null;
  work_category: string;
  trade_type: string;
  process: string;
  risk_factor: string;
  counterplan: string;
  risk_f: number;
  risk_s: number;
  risk_r: number;
  display_f: number | null;
  display_s: number | null;
  display_r: number | null;
  risk_grade: "상" | "중" | "하" | "";
  evaluation_method: string;
  improvement_owner_name: string | null;
  improvement_verifier_name: string | null;
  note: string | null;
  source_file: string | null;
  source_sheet: string | null;
  source_row: number | null;
  source_page_or_section: string | null;
  score: number;
  matched_tokens: string[];
  matched_fields: string[];
}

export type RiskSearchMode = "quick" | "nlp_beta";

export interface RiskLibraryContractorOption {
  contractor_key: string;
  contractor_name: string;
  evaluation_method: string;
}

export interface RiskAssessmentDesignation {
  site_id: number | null;
  site_name: string | null;
  inspector_name: string | null;
  verifier_name: string | null;
  appointed_on: string | null;
  note: string | null;
  can_edit: boolean;
}

export interface RiskLibrarySearchResponse {
  mode: RiskSearchMode;
  normalized_query: string;
  tokens: string[];
  total: number;
  limit: number;
  offset: number;
  contractor_key: string | null;
  contractor_name: string | null;
  evaluation_method: string;
  can_print: boolean;
  contractor_options: RiskLibraryContractorOption[];
  designation: RiskAssessmentDesignation | null;
  results: RiskLibraryItem[];
}

export interface RiskLibraryQuery {
  query?: string;
  mode?: RiskSearchMode;
  unit_work?: string;
  risk_type?: string;
  contractor?: string;
  site_id?: number;
  limit?: number;
  offset?: number;
}

export async function fetchRiskLibrary(
  query: RiskLibraryQuery,
): Promise<RiskLibrarySearchResponse> {
  const res = await api.get<RiskLibrarySearchResponse>("/search/risk-library", { params: query });
  return res.data;
}

export async function saveRiskAssessmentDesignation(payload: {
  inspector_name: string | null;
  verifier_name: string | null;
  appointed_on: string | null;
  note: string | null;
}): Promise<RiskAssessmentDesignation> {
  const res = await api.put<RiskAssessmentDesignation>("/search/risk-assessment/designation", payload);
  return res.data;
}

export async function saveRiskLibrarySiteAssignment(
  riskItemId: number,
  payload: {
    improvement_owner_name: string | null;
    improvement_verifier_name: string | null;
  },
): Promise<{
  site_id: number;
  risk_item_id: number;
  improvement_owner_name: string | null;
  improvement_verifier_name: string | null;
}> {
  const res = await api.put(`/search/risk-library/${riskItemId}/site-assignment`, payload);
  return res.data;
}
