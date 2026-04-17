const STORAGE_KEY = "besma_hq_communication_read_v1";
const MAX_ITEMS_PER_USER = 2000;

type ReadMap = Record<string, string[]>;

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

function writeMap(map: ReadMap): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export function getReadCommunicationKeys(loginId: string | null | undefined): Set<string> {
  if (!loginId) return new Set();
  const arr = parseMap()[loginId] ?? [];
  return new Set(arr.filter((v) => typeof v === "string" && v.trim().length > 0));
}

export function markCommunicationRead(loginId: string | null | undefined, itemKey: string): void {
  if (!loginId || !itemKey.trim()) return;
  const map = parseMap();
  const prev = Array.isArray(map[loginId]) ? map[loginId] : [];
  const next = [...prev.filter((k) => k !== itemKey), itemKey].slice(-MAX_ITEMS_PER_USER);
  map[loginId] = next;
  writeMap(map);
  window.dispatchEvent(new CustomEvent("besma-hq-communication-read", { detail: { itemKey } }));
}
