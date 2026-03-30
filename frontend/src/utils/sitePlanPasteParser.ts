export interface ParsedPlanItem {
  work_name: string;
  work_description: string;
  team_label: string;
  workers_text: string;
}

export interface ParsedPlanResult {
  work_date: string | null;
  site_name: string | null;
  manager: string | null;
  items: ParsedPlanItem[];
  raw_lines: string[];
}

const HEADER_KEYWORDS = new Set([
  "구분", "팀명", "작업내용", "작업자", "현장명", "담당자",
  "출역일", "작업일", "일자", "금일", "명일", "비고",
]);

const NOISE_PATTERNS = [
  /^금\s*$/,
  /^일\s*$/,
  /^명\s*$/,
  /^작업일보\s*$/,
  /^\d+\s*$/,
  /^[\t\s]*$/,
];

function isNoise(line: string): boolean {
  const t = line.trim();
  if (!t) return true;
  if (t.length <= 1 && !/[가-힣a-zA-Z0-9]/.test(t)) return true;
  if (NOISE_PATTERNS.some((p) => p.test(t))) return true;
  if (HEADER_KEYWORDS.has(t)) return true;
  return false;
}

function isWorkerLine(line: string): boolean {
  return /외\s*\d+\s*명/.test(line) || /^\s*[가-힣]{2,4}\s+외\s*\d/.test(line);
}

function isHeaderRow(line: string): boolean {
  const cols = line.split("\t").map((c) => c.trim());
  const headerHits = cols.filter((c) => HEADER_KEYWORDS.has(c));
  return headerHits.length >= 2;
}

function extractDate(text: string): string | null {
  const m1 = text.match(/(\d{4})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})\s*일?/);
  if (m1) {
    return `${m1[1]}-${m1[2].padStart(2, "0")}-${m1[3].padStart(2, "0")}`;
  }
  const m2 = text.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (m2) return m2[0];
  return null;
}

function extractManager(text: string): string | null {
  const m = text.match(/담당자[\s\t:：]*([가-힣a-zA-Z]{2,10})/);
  return m ? m[1].trim() : null;
}

function extractSiteName(text: string): string | null {
  const lines = text.split("\n");
  for (const line of lines) {
    const t = line.trim();
    if (/^\[.*\].*공사/.test(t) || (/공동주택|신축공사|아파트/.test(t) && t.length > 10)) {
      return t;
    }
  }
  const m = text.match(/현장명[\s\t:：]+\n\s*(.+)/);
  if (m && m[1].trim().length > 4) return m[1].trim();
  return null;
}

export function parsePastedText(raw: string): ParsedPlanResult {
  const rawLines = raw.split("\n");
  const work_date = extractDate(raw);
  const manager = extractManager(raw);
  const site_name = extractSiteName(raw);

  const items: ParsedPlanItem[] = [];
  let currentSection = "금일";
  let i = 0;

  while (i < rawLines.length) {
    const line = rawLines[i];
    const trimmed = line.trim();

    if (/^금\s*일?\s*$/.test(trimmed) || /금\s*일/.test(trimmed) && trimmed.length <= 4) {
      currentSection = "금일";
      i++;
      continue;
    }
    if (/^명\s*일?\s*$/.test(trimmed) || /명\s*일/.test(trimmed) && trimmed.length <= 4) {
      currentSection = "명일";
      i++;
      continue;
    }

    if (isNoise(trimmed) || isHeaderRow(line)) {
      i++;
      continue;
    }

    if (/출역일|작업일|일자|담당자|현장명/.test(trimmed)) {
      i++;
      continue;
    }

    if (/\[.*\].*공사|현장|신축/.test(trimmed)) {
      i++;
      continue;
    }

    const tabs = line.split("\t").map((c) => c.trim()).filter(Boolean);

    if (tabs.length >= 2) {
      const workContent = tabs.find(
        (t) =>
          t.length >= 4 &&
          !isWorkerLine(t) &&
          !HEADER_KEYWORDS.has(t) &&
          !/^(금|일|명)\s*$/.test(t),
      );
      const workerCol = tabs.find((t) => isWorkerLine(t));

      if (workContent) {
        items.push({
          work_name: workContent,
          work_description: workContent,
          team_label: currentSection === "명일" ? "명일" : "",
          workers_text: workerCol ?? "",
        });
        i++;
        continue;
      }
    }

    if (
      trimmed.length >= 4 &&
      !isWorkerLine(trimmed) &&
      /[가-힣]/.test(trimmed)
    ) {
      let workers = "";
      if (i + 1 < rawLines.length && isWorkerLine(rawLines[i + 1].trim())) {
        workers = rawLines[i + 1].trim();
        i++;
      }
      items.push({
        work_name: trimmed,
        work_description: trimmed,
        team_label: currentSection === "명일" ? "명일" : "",
        workers_text: workers,
      });
      i++;
      continue;
    }

    i++;
  }

  const seen = new Set<string>();
  const dedupedItems = items.filter((item) => {
    if (item.team_label === "명일") return false;
    const key = item.work_name;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return {
    work_date,
    site_name,
    manager,
    items: dedupedItems,
    raw_lines: rawLines,
  };
}
