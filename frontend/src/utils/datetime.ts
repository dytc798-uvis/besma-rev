function hasExplicitTimeZone(iso: string): boolean {
  const s = iso.trim();
  if (/[zZ]$/.test(s)) return true;
  return /[+-]\d{2}:\d{2}(:\d{2})?$/.test(s) || /[+-]\d{4}$/.test(s);
}

/** YYYY-MM-DD 만 있는 값 (UTC 자정으로 파싱) */
function isDateOnly(s: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(s.trim());
}

/**
 * 백엔드 naive UTC(또는 Z/오프셋 없는 ISO) 문자열을 Date 생성 시 UTC로 해석되게 보정한다.
 */
function normalizeInstantString(raw: string): string {
  const s = raw.trim();
  if (!s || isDateOnly(s)) return s;
  if (hasExplicitTimeZone(s)) return s.includes("T") ? s : s.replace(" ", "T");
  const t = s.includes("T") ? s : s.replace(" ", "T");
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(t) && !hasExplicitTimeZone(t)) {
    return t.endsWith("Z") ? t : `${t}Z`;
  }
  return s;
}

export function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const normalized = normalizeInstantString(String(value));
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDateTimeKst(value: string | Date | null | undefined, fallback = "—") {
  const parsed = toDate(value);
  if (!parsed) return fallback;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

export function formatDateKst(value: string | Date | null | undefined, fallback = "—") {
  const parsed = toDate(value);
  if (!parsed) return fallback;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parsed);
}

export function toKstDateKey(value: string | Date | null | undefined) {
  const parsed = toDate(value);
  if (!parsed) return "";
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parsed);
}

export function todayKst() {
  return toKstDateKey(new Date());
}

/** `<input type="month">` 초기값 등 — 한국 날짜 기준 YYYY-MM */
export function yearMonthKst(d: Date = new Date()) {
  return toKstDateKey(d).slice(0, 7);
}
