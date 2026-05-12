const LOOP_LABELS: Record<string, string> = {
  NONE: "—",
  IMPROVEMENT_REQUESTED: "개선요청",
  SITE_REUPLOADED: "재업로드",
  HQ_REVIEWING: "재검토",
  CLOSED_APPROVED: "완료",
};

export function feedbackLoopLabelKo(status: string | null | undefined): string {
  if (!status) return LOOP_LABELS.NONE;
  return LOOP_LABELS[status] ?? status;
}
