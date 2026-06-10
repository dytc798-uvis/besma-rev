import type { AccidentListItem, AccidentWorklistResponse } from "@/services/accidents";

export const ACCIDENT_LIST_RECENT_LIMIT = 20;

const LIST_ITEMS_PREFIX = "besma_accidents_list_items_";
const LIST_SYNC_PREFIX = "besma_accidents_list_sync_";
const WORKLIST_CACHE_KEY = "besma_accidents_worklist_v1";
const WORKLIST_SYNC_KEY = "besma_accidents_worklist_sync_v1";
const LOOKUPS_CACHE_KEY = "besma_accidents_lookups_v1";

function listScope(showAll: boolean) {
  return showAll ? "all" : "queue";
}

export function readAccidentListCache(showAll: boolean): AccidentListItem[] | null {
  try {
    const raw = localStorage.getItem(`${LIST_ITEMS_PREFIX}${listScope(showAll)}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AccidentListItem[];
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function readAccidentListSyncTime(showAll: boolean): string | null {
  return localStorage.getItem(`${LIST_SYNC_PREFIX}${listScope(showAll)}`);
}

export function writeAccidentListCache(showAll: boolean, items: AccidentListItem[], serverTime: string) {
  localStorage.setItem(`${LIST_ITEMS_PREFIX}${listScope(showAll)}`, JSON.stringify(items));
  localStorage.setItem(`${LIST_SYNC_PREFIX}${listScope(showAll)}`, serverTime);
}

export function sortAccidentListItemsNewestFirst(items: AccidentListItem[]): AccidentListItem[] {
  return [...items].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
}

export function trimAccidentListItems(items: AccidentListItem[], showAll: boolean): AccidentListItem[] {
  const sorted = sortAccidentListItemsNewestFirst(items);
  if (showAll) return sorted.slice(0, 500);
  return sorted.slice(0, ACCIDENT_LIST_RECENT_LIMIT);
}

export function mergeAccidentListItems(
  existing: AccidentListItem[],
  upserts: AccidentListItem[],
  showAll: boolean,
): AccidentListItem[] {
  const byId = new Map(existing.map((item) => [item.id, item]));
  for (const item of upserts) {
    if (!showAll && item.parse_status === "success") {
      byId.delete(item.id);
      continue;
    }
    byId.set(item.id, item);
  }
  return trimAccidentListItems(Array.from(byId.values()), showAll);
}

export function filterAccidentListItems(items: AccidentListItem[], showAll: boolean): AccidentListItem[] {
  if (showAll) return items;
  return items.filter((item) => item.parse_status !== "success");
}

export function latestAccidentSyncTime(items: AccidentListItem[]): string | null {
  if (!items.length) return null;
  return items.reduce((latest, item) => (item.updated_at > latest ? item.updated_at : latest), items[0].updated_at);
}

export function readWorklistCache(): AccidentWorklistResponse | null {
  try {
    const raw = localStorage.getItem(WORKLIST_CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AccidentWorklistResponse;
  } catch {
    return null;
  }
}

export function writeWorklistCache(payload: AccidentWorklistResponse, serverTime: string) {
  localStorage.setItem(WORKLIST_CACHE_KEY, JSON.stringify(payload));
  localStorage.setItem(WORKLIST_SYNC_KEY, serverTime);
}

export function readWorklistSyncTime(): string | null {
  return localStorage.getItem(WORKLIST_SYNC_KEY);
}

export function readLookupsCache<T>(): T | null {
  try {
    const raw = sessionStorage.getItem(LOOKUPS_CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function writeLookupsCache<T>(payload: T) {
  sessionStorage.setItem(LOOKUPS_CACHE_KEY, JSON.stringify(payload));
}
