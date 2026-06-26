export interface ParsedTbmSourceItem {
  teamName: string;
  workerName: string;
  workDescription: string;
}

export interface ParsedTbmResult {
  sourceDate: string | null;
  nextDate: string | null;
  siteName: string;
  managerName: string;
  items: ParsedTbmSourceItem[];
  rawLines: string[];
}

const SECTION_GONGIL = "금일";
const SECTION_MYEONGIL = "명일";

function normalize(text: string) {
  return text.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function normalizeDatePart(value: string) {
  const s = value.trim();
  return s.length === 1 ? `0${s}` : s;
}

function parseDate(value: string): string | null {
  const korean = value.match(/(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일/);
  if (korean) return `${korean[1]}-${normalizeDatePart(korean[2])}-${normalizeDatePart(korean[3])}`;

  const ymd = value.match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (ymd) return `${ymd[1]}-${normalizeDatePart(ymd[2])}-${normalizeDatePart(ymd[3])}`;

  const compact = value.match(/(\d{4})[./](\d{1,2})[./](\d{1,2})/);
  if (compact) return `${compact[1]}-${normalizeDatePart(compact[2])}-${normalizeDatePart(compact[3])}`;

  return null;
}

function addOneDay(date: string | null): string | null {
  if (!date) return null;
  const m = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const next = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  next.setDate(next.getDate() + 1);
  return `${next.getFullYear()}-${normalizeDatePart(String(next.getMonth() + 1))}-${normalizeDatePart(
    String(next.getDate()),
  )}`;
}

function extractDate(raw: string): string | null {
  const labels = ["출역일", "작성일", "작업일자", "근무일자"];
  for (const label of labels) {
    const pattern = new RegExp(`${label}\\s*[:：]?\\s*([^\\n\\r]+)`, "g");
    const match = pattern.exec(raw);
    if (match && match[1]) {
      const parsed = parseDate(match[1]);
      if (parsed) return parsed;
    }
  }
  return parseDate(raw);
}

function extractSiteName(raw: string): string {
  const siteMatch = raw.match(/현장명\s*[:：]?\s*([^\r\n]+)/);
  if (siteMatch?.[1]) {
    return normalize(siteMatch[1]).slice(0, 180);
  }

  const bracketed = raw.match(/(\[[^\]]+\]\s*\[[^\]]+\]\s*[^\r\n]+)/);
  if (bracketed?.[1]) return normalize(bracketed[1]).slice(0, 180);

  const keywordMatch = raw.match(/([^\r\n]*오피스텔[^\r\n]*)/);
  return keywordMatch ? normalize(keywordMatch[1]).slice(0, 180) : "";
}

function extractManagerName(raw: string): string {
  const managerMatch = raw.match(/담당자\s*[:：]?\s*([^\r\n]+)/);
  return managerMatch?.[1] ? normalize(managerMatch[1]).slice(0, 80) : "";
}

function parseHtmlRows(raw: string): string[][] {
  if (!raw.includes("<table")) return [];
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(raw, "text/html");
    const rows = Array.from(doc.querySelectorAll("table tr"));
    return rows
      .map((row) =>
        Array.from(row.querySelectorAll("td, th"))
          .map((cell) => normalize(cell.textContent || ""))
          .filter((cell) => cell.length > 0),
      )
      .filter((row) => row.length > 0);
  } catch {
    return [];
  }
}

function parseTextRows(raw: string): string[][] {
  return raw
    .split(/\r?\n/)
    .map((line) => {
      const trimmed = normalize(line);
      if (trimmed.includes("\t")) return trimmed.split("\t").map((v) => normalize(v)).filter(Boolean);
      return trimmed ? [trimmed] : [];
    })
    .filter((row) => row.length > 0);
}

function looksLikeHeader(value: string) {
  return [
    "팀명",
    "작업자",
    "금일",
    "명일",
    "현장명",
    "담당자",
    "일자",
    "날짜",
    "출역일",
  ].some((keyword) => value.includes(keyword));
}

function looksLikeSectionMarker(value: string) {
  return value === SECTION_GONGIL || value === SECTION_MYEONGIL || /^(금일|명일)\s*작업/.test(value);
}

function isWorkerLike(value: string) {
  if (!value || value.length > 80) return false;
  if (/(팀|현장|작업장|금일|명일|안전|위험|통로|점검|차단)/.test(value)) return false;
  return /[가-힣]{2,}(?:\s*,\s*[가-힣]{2,})*/.test(value) || /\b\d{1,2}\s*명\b/.test(value);
}

function isTeamLike(value: string) {
  return /\b팀\b/.test(value) || /[0-9]+\s*조/.test(value) || /^A|B|C|D|E|1|2|3|4/.test(value);
}

function pickWorkDescription(cells: string[]) {
  const candidates = cells.filter((cell) => cell && !looksLikeHeader(cell) && cell.length >= 2);
  for (const candidate of candidates) {
    if (!isWorkerLike(candidate) && !isTeamLike(candidate) && candidate.length >= 3) {
      return candidate;
    }
  }
  return candidates.find((c) => c.length >= 3) || "";
}

function pickWorker(cells: string[]) {
  const worker = cells.find((cell) => isWorkerLike(cell));
  return worker ?? "";
}

function pickTeam(cells: string[]) {
  const team = cells.find((cell) => isTeamLike(cell));
  if (team) return team;

  const fallback = cells.find((cell) => cell.length >= 2 && cell.length <= 18 && /[가-힣a-zA-Z0-9]/.test(cell));
  return fallback ?? "";
}

function parseRows(rawRows: string[][]): ParsedTbmSourceItem[] {
  let section: "금일" | "명일" = SECTION_GONGIL as "금일" | "명일";
  const items: ParsedTbmSourceItem[] = [];

  for (const row of rawRows) {
    const safeRow = row.map((value) => normalize(value)).filter(Boolean);
    if (safeRow.length === 0) continue;

    if (safeRow.some((cell) => looksLikeSectionMarker(cell))) {
      section = safeRow.some((cell) => cell.startsWith(SECTION_MYEONGIL)) ? SECTION_MYEONGIL : SECTION_GONGIL;
      continue;
    }

    if (safeRow.every((cell) => looksLikeSectionMarker(cell))) continue;
    if (safeRow.some(looksLikeHeader)) continue;
    if (safeRow.every((cell) => /^\d+$/.test(cell))) continue;
    if (section !== SECTION_MYEONGIL) continue;

    const workDescription = pickWorkDescription(safeRow);
    if (!workDescription) continue;

    if (/^(금일|명일)\s+작업내용/.test(workDescription)) continue;

    const workerName = pickWorker(safeRow);
    const teamName = pickTeam(safeRow);
    items.push({
      teamName: teamName,
      workerName,
      workDescription,
    });
  }

  return items;
}

export function parseErpWorklogForNextDayTbm(rawInput: string): ParsedTbmResult {
  const raw = normalize(rawInput);
  const rawLines = raw.split(/\r?\n/).map((line) => line.trim()).filter((line) => line.length > 0);
  const sourceDate = extractDate(raw);
  const nextDate = addOneDay(sourceDate);
  const siteName = extractSiteName(raw);
  const managerName = extractManagerName(raw);

  const tableRows = parseHtmlRows(raw);
  const rows = tableRows.length > 0 ? parseRows(tableRows) : parseRows(parseTextRows(raw));
  const deduped = rows.filter((item) => item.workDescription && item.workDescription.length > 0);

  return {
    sourceDate,
    nextDate,
    siteName,
    managerName,
    items: deduped,
    rawLines,
  };
}
