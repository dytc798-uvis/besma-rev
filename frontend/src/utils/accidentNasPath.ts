const ACCIDENT_NAS_ROOT = "Z:\\4. 안전보건관리실\\104 사고 조사 및 이력 (산재요양승인 내역)";

function extractSegments(path: string | null | undefined): string[] {
  const raw = String(path ?? "").trim();
  if (!raw) return [];
  const normalized = raw.replace(/[\\/]+$/, "");
  return normalized.split(/[\\/]+/).filter(Boolean);
}

function extractTailSegment(path: string | null | undefined): string | null {
  const parts = extractSegments(path);
  return parts.length > 0 ? parts[parts.length - 1] : null;
}

function extractYearSegment(path: string | null | undefined, accidentId?: string | null): string | null {
  const parts = extractSegments(path);
  const yearFromPath = parts.find((part) => /^\d{4}$/.test(part));
  if (yearFromPath) return yearFromPath;

  const idText = String(accidentId ?? "").trim();
  const yearFromId = idText.match(/^(\d{4})-/)?.[1] ?? null;
  return yearFromId;
}

export function toDisplayedAccidentNasPath(path: string | null | undefined, accidentId?: string | null): string {
  const raw = String(path ?? "").trim();
  if (raw.startsWith(ACCIDENT_NAS_ROOT)) return raw;

  const tail = extractTailSegment(raw) || String(accidentId ?? "").trim();
  const year = extractYearSegment(raw, accidentId);
  if (!tail && !year) return ACCIDENT_NAS_ROOT;
  if (!tail) return `${ACCIDENT_NAS_ROOT}\\${year}`;
  if (!year) return `${ACCIDENT_NAS_ROOT}\\${tail}`;
  return `${ACCIDENT_NAS_ROOT}\\${year}\\${tail}`;
}

export { ACCIDENT_NAS_ROOT };
