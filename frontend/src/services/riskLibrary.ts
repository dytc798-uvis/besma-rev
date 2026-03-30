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

export interface RiskLibrarySearchResponse {
  mode: RiskSearchMode;
  normalized_query: string;
  tokens: string[];
  total: number;
  limit: number;
  offset: number;
  results: RiskLibraryItem[];
}

export interface RiskLibraryQuery {
  query?: string;
  mode?: RiskSearchMode;
  unit_work?: string;
  risk_type?: string;
  limit?: number;
  offset?: number;
}

export async function fetchRiskLibrary(
  query: RiskLibraryQuery,
): Promise<RiskLibrarySearchResponse> {
  const res = await api.get<RiskLibrarySearchResponse>("/search/risk-library", { params: query });
  return res.data;
}
