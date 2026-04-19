import { api } from "@/services/api";

export interface AccidentAttachmentItem {
  id: number;
  file_name: string;
  stored_path: string;
  content_type: string | null;
  file_size: number | null;
  created_at: string;
}

export interface AccidentListItem {
  id: number;
  accident_id: string;
  display_code: string;
  parse_status: string;
  site_name: string | null;
  site_standard_name: string | null;
  injured_person_name: string | null;
  accident_datetime_text: string | null;
  accident_datetime: string | null;
  status: string;
  management_category: string;
  is_complete: boolean;
  has_attachments: boolean;
  nas_folder_path: string | null;
  created_at: string;
}

export interface AccidentDetail extends AccidentListItem {
  report_type: string;
  source_type: string;
  message_raw: string;
  reporter_name: string | null;
  accident_place: string | null;
  work_content: string | null;
  accident_circumstance: string | null;
  accident_reason: string | null;
  injured_part: string | null;
  diagnosis_name: string | null;
  action_taken: string | null;
  initial_report_template: string | null;
  nas_folder_key: string | null;
  notes: string | null;
  parse_note: string | null;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
  updated_at: string;
  attachments: AccidentAttachmentItem[];
}

export interface AccidentInitialReportOutput {
  accident_id: number;
  accident_code: string;
  display_code: string;
  parse_status: string;
  composed_line: string;
  fields: Record<string, unknown>;
  message_raw: string;
}

export interface AccidentLookups {
  statuses: string[];
  management_categories: string[];
  site_names: string[];
}

export interface AccidentUpdatePayload {
  site_standard_name: string;
  reporter_name: string | null;
  status: string;
  management_category: string;
  accident_datetime_text: string | null;
  accident_datetime: string | null;
  accident_place: string | null;
  work_content: string | null;
  injured_person_name: string | null;
  accident_circumstance: string | null;
  accident_reason: string | null;
  injured_part: string | null;
  diagnosis_name: string | null;
  action_taken: string | null;
  notes: string | null;
  initial_report_template: string | null;
}

export interface AccidentCreatePayload extends AccidentUpdatePayload {
  input_mode: "auto" | "manual";
  template_name?: string | null;
  message_raw: string | null;
  parse_status_override?: string | null;
  parse_note_override?: string | null;
}

export interface AccidentWorklistSection {
  count: number;
  items: AccidentListItem[];
}

export interface AccidentWorklistResponse {
  unverified: AccidentWorklistSection;
  parse_review: AccidentWorklistSection;
  missing_attachments: AccidentWorklistSection;
  recent: AccidentWorklistSection;
}

export interface AccidentParsePreviewResponse {
  parse_status: string;
  parse_note: string | null;
  composed_line: string;
  fields: Record<string, unknown>;
  message_raw: string;
}

export interface AccidentMasterExcelSyncResult {
  target_path: string;
  backup_path: string | null;
  exported_count: number;
  excluded_count: number;
  backup_created: boolean;
}

export async function fetchAccidentLookups() {
  const res = await api.get<AccidentLookups>("/accidents/lookups");
  return res.data;
}

export async function fetchAccidents(params: {
  queues?: string[];
  show_all?: boolean;
}) {
  const res = await api.get<AccidentListItem[]>("/accidents", { params });
  return res.data ?? [];
}

export async function fetchAccidentDetail(id: number) {
  const res = await api.get<AccidentDetail>(`/accidents/${id}`);
  return res.data;
}

export async function fetchAccidentInitialReport(id: number) {
  const res = await api.get<AccidentInitialReportOutput>(`/accidents/${id}/initial-report`);
  return res.data;
}

export async function fetchAccidentWorklist() {
  const res = await api.get<AccidentWorklistResponse>("/accidents/worklist");
  return res.data;
}

export async function fetchAccidentParsePreview(payload: { message_raw: string }) {
  const res = await api.post<AccidentParsePreviewResponse>("/accidents/initial-report/parse-preview", payload);
  return res.data;
}

export async function syncAccidentsToMasterExcel() {
  const res = await api.post<AccidentMasterExcelSyncResult>("/accidents/export-to-master-excel");
  return res.data;
}

/** 백엔드 검증 후 탐색기 실행용 .bat 파일을 내려받는다(Windows에서 더블클릭). */
export async function downloadAccidentNasFolderLauncher(accidentPk: number): Promise<void> {
  const res = await api.get(`/accidents/${accidentPk}/nas-folder-launcher`, { responseType: "blob" });
  const blob = new Blob([res.data], { type: "application/octet-stream" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `open_accident_${accidentPk}_nas.bat`;
  a.rel = "noopener";
  a.click();
  window.URL.revokeObjectURL(url);
}
