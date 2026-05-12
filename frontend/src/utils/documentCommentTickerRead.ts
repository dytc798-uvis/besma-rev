const STORAGE_KEY = "besma_doc_comment_ticker_ack_v1";

type AckMap = Record<string, string>;

function parseMap(): AckMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as AckMap;
  } catch {
    return {};
  }
}

function writeMap(map: AckMap) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

/** 마지막으로 "확인"한 시각(ISO). 없으면 서버가 초기 윈도우(예: 14일)로 집계한다. */
export function getDocCommentTickerAfterIso(loginId: string | null | undefined): string | undefined {
  if (!loginId) return undefined;
  const v = parseMap()[loginId.trim()];
  if (typeof v !== "string" || !v.trim()) return undefined;
  return v.trim();
}

/**
 * 문서취합 화면 방문·티커 클릭 시 호출: 이 시각 이후에 등록된 타인 코멘트만 티커에 잡힌다.
 */
export function markDocCommentTickerAck(loginId: string | null | undefined): void {
  if (!loginId) return;
  const key = loginId.trim();
  if (!key) return;
  const map = parseMap();
  map[key] = new Date().toISOString();
  writeMap(map);
  window.dispatchEvent(new CustomEvent("besma-doc-comment-ticker-ack"));
}
