const STORAGE_KEY = "besma_notice_ticker_read_v1";
const MAX_IDS_PER_USER = 400;

type ReadMap = Record<string, number[]>;

function parseMap(): ReadMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as ReadMap;
  } catch {
    return {};
  }
}

function writeMap(map: ReadMap) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* storage full or disabled */
  }
}

/** SITE 티커에서 제외할 공지 id (공지 상세를 한 번이라도 연 경우) */
export function getTickerReadNoticeIds(loginId: string | null | undefined): Set<number> {
  if (!loginId) return new Set();
  const ids = parseMap()[loginId];
  if (!Array.isArray(ids)) return new Set();
  return new Set(ids.filter((n) => typeof n === "number" && Number.isFinite(n)));
}

/** 공지 본문을 연 것으로 간주해 티커 대상에서 제외. 별도 '확인' 버튼 없이 상세 조회 시만 호출 */
export function markNoticeSeenForTicker(loginId: string | null | undefined, noticeId: number): void {
  if (!loginId || !Number.isFinite(noticeId)) return;
  const map = parseMap();
  const prev = Array.isArray(map[loginId]) ? map[loginId] : [];
  const next = [...prev.filter((id) => id !== noticeId), noticeId];
  const trimmed = next.slice(-MAX_IDS_PER_USER);
  map[loginId] = trimmed;
  writeMap(map);
  window.dispatchEvent(new CustomEvent("besma-notice-ticker-read", { detail: { noticeId } }));
}
