import { formatDateKst, formatDateTimeKst, isInstantKstMidnight, toDate } from "@/utils/datetime";

/**
 * 사고일시 표시: ISO가 KST 자정이면 날짜만, 시간이 있으면 일시.
 * 원문(text)만 있는 경우도 동일 규칙; 자유 서술은 그대로 반환.
 */
export function formatAccidentMoment(
  accidentDatetime: string | null | undefined,
  accidentDatetimeText: string | null | undefined,
): string {
  const iso = (accidentDatetime ?? "").trim();
  const text = (accidentDatetimeText ?? "").trim();

  if (iso) {
    const d = toDate(iso);
    if (d) {
      if (isInstantKstMidnight(iso)) {
        return formatDateKst(iso, "—");
      }
      return formatDateTimeKst(iso, "—");
    }
  }

  if (text) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
      return formatDateKst(text, text);
    }
    const d2 = toDate(text);
    if (d2) {
      if (isInstantKstMidnight(text)) {
        return formatDateKst(text, text);
      }
      return formatDateTimeKst(text, text);
    }
    return text;
  }

  return "—";
}

/** 목록: 사고일시가 비어 있으면 등록일의 날짜만 */
export function formatAccidentDateForListRow(
  accidentDatetime: string | null | undefined,
  accidentDatetimeText: string | null | undefined,
  createdAt: string | null | undefined,
): string {
  const iso = (accidentDatetime ?? "").trim();
  const text = (accidentDatetimeText ?? "").trim();
  if (iso || text) return formatAccidentMoment(accidentDatetime, accidentDatetimeText);
  const c = (createdAt ?? "").trim();
  if (!c) return "—";
  return formatDateKst(c, "—");
}
