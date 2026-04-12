/** 백엔드 opinions.status 코드 → 화면 한글 라벨 (DECISION-051) */
const CODE_TO_LABEL: Record<string, string> = {
  RECEIVED: "검토전",
  REVIEWING: "검토중",
  ACTIONED: "조치완료",
  HOLD: "보류",
};

export function opinionStatusLabel(code: string | null | undefined): string {
  if (code == null || code === "") return "-";
  return CODE_TO_LABEL[code] ?? code;
}
