import { api } from "@/services/api";

export type ForkliftWorkPlanInput = {
  site_name?: string;
  company_name?: string;
  document_date_year?: string;
  document_date_month?: string;
  document_date_day?: string;
  work_name: string;
  period_start_year?: string;
  period_start_month?: string;
  period_start_day?: string;
  period_end_year?: string;
  period_end_month?: string;
  period_end_day?: string;
  work_location?: string;
  safety_meeting_company?: string;
  participants?: string;
  supervisor_name?: string;
  supervisor_phone?: string;
  supervisor_license_type?: string;
  supervisor_license_no?: string;
  signal_name?: string;
  signal_phone?: string;
  signal_license_type?: string;
  signal_license_no?: string;
  commander_name?: string;
  commander_role?: string;
  equipment_type?: string;
  equipment_model?: string;
  registration_no?: string;
  manufacture_year?: string;
  rated_capacity?: string;
  registered_company?: string;
  length_mm?: number | string | null;
  width_mm?: number | string | null;
  height_mm?: number | string | null;
  max_lifting_kg?: number | string | null;
  work_location_plan?: string;
  work_content_plan?: string;
};

export type ForkliftEquipmentSpec = {
  model: string;
  equipment_type: string;
  rated_capacity: string;
  manufacture_year: string;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
  max_lifting_kg: number | null;
  source: string;
  confidence: string;
};

export type ForkliftWorkPlanGenerateResponse = {
  filename: string;
  saved_path: string;
  download_url: string;
  sheet_name: string;
};

export async function lookupForkliftSpecs(model: string, allowWeb = true) {
  const res = await api.get<ForkliftEquipmentSpec>("/work-plans/forklift/lookup-specs", {
    params: { model, allow_web: allowWeb },
  });
  return res.data;
}

export async function generateForkliftWorkPlan(payload: ForkliftWorkPlanInput) {
  const res = await api.post<ForkliftWorkPlanGenerateResponse>("/work-plans/forklift/generate", payload);
  return res.data;
}

export async function downloadForkliftWorkPlanFile(filename: string) {
  const res = await api.get(`/work-plans/forklift/download/${encodeURIComponent(filename)}`, {
    responseType: "blob",
  });
  const blob = new Blob([res.data], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
