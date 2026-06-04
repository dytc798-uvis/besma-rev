/** 지게차 작업계획서 — 고정값 기본·장비 필드 placeholder 예시 */

export function todayParts() {
  const d = new Date();
  return {
    year: `${d.getFullYear()}년`,
    month: `${d.getMonth() + 1}월`,
    day: `${d.getDate()}일`,
    iso: d.toISOString().slice(0, 10),
  };
}

export const FORKLIFT_EQUIPMENT_PLACEHOLDERS = {
  equipment_model: "50DN-9VB",
  registration_no: "004다6990",
  manufacture_year: "2024년",
  rated_capacity: "5ton",
  registered_company: "민성중기",
  length_mm: "4510",
  width_mm: "1740",
  height_mm: "3025",
  max_lifting_kg: "11480",
} as const;

export function createForkliftWorkPlanDefaults(siteName?: string) {
  const t = todayParts();
  return {
    site_name: siteName || "푸르지오스타셀라49현장",
    company_name: "(주)부현전기",
    document_date_year: t.year,
    document_date_month: t.month,
    document_date_day: t.day,
    work_name: "자재 하역작업",
    period_start_year: t.year,
    period_start_month: t.month,
    period_start_day: t.day,
    period_end_year: t.year,
    period_end_month: t.month,
    period_end_day: t.day,
    work_location: "지상1층",
    safety_meeting_company: "업체명",
    participants: "2",
    equipment_type: "카운터밸런스형",
    supervisor_name: "",
    supervisor_phone: "",
    supervisor_license_type: "",
    supervisor_license_no: "",
    signal_name: "",
    signal_phone: "",
    signal_license_type: "",
    signal_license_no: "",
    commander_name: "",
    commander_role: "",
    equipment_model: "",
    registration_no: "",
    manufacture_year: "",
    rated_capacity: "",
    registered_company: "",
    length_mm: "",
    width_mm: "",
    height_mm: "",
    max_lifting_kg: "",
    work_location_plan: "",
    work_content_plan: "",
  };
}
