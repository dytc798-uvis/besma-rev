/**
 * 사고일시 표시: ISO가 자정(로컬)이면 날짜만, 시간이 있으면 일시.
 * 원문(text)만 있는 경우도 동일 규칙; 자유 서술은 그대로 반환.
 */
export function formatAccidentMoment(
  accidentDatetime: string | null | undefined,
  accidentDatetimeText: string | null | undefined,
): string {
  const iso = (accidentDatetime ?? "").trim();
  const text = (accidentDatetimeText ?? "").trim();

  if (iso) {
    const d = new Date(iso);
    if (!Number.isNaN(d.getTime())) {
      if (isLocalMidnight(d)) {
        return d.toLocaleDateString("ko-KR", { year: "numeric", month: "numeric", day: "numeric" });
      }
      return d.toLocaleString("ko-KR");
    }
  }

  if (text) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
      const d = new Date(`${text}T00:00:00`);
      if (!Number.isNaN(d.getTime())) {
        return d.toLocaleDateString("ko-KR", { year: "numeric", month: "numeric", day: "numeric" });
      }
    }
    const d2 = new Date(text);
    if (!Number.isNaN(d2.getTime())) {
      if (isLocalMidnight(d2)) {
        return d2.toLocaleDateString("ko-KR", { year: "numeric", month: "numeric", day: "numeric" });
      }
      return d2.toLocaleString("ko-KR");
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
  const d = new Date(c);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("ko-KR", { year: "numeric", month: "numeric", day: "numeric" });
}

function isLocalMidnight(d: Date): boolean {
  return d.getHours() === 0 && d.getMinutes() === 0 && d.getSeconds() === 0 && d.getMilliseconds() === 0;
}
