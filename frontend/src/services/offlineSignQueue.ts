export type PendingSignType = "start" | "end";

export interface PendingSignQueueItem {
  id: string;
  distribution_id: number;
  access_token: string | null;
  sign_type: PendingSignType;
  lat: number;
  lng: number;
  timestamp: string;
  signature_data: string;
  signature_mime: string;
  end_status?: "NORMAL" | "ISSUE";
}

const OFFLINE_SIGN_QUEUE_KEY = "besma_pending_sign_queue";

export function isOfflineSignQueueEnabled() {
  return import.meta.env.DEV;
}

export function getPendingSignQueue(): PendingSignQueueItem[] {
  try {
    const raw = localStorage.getItem(OFFLINE_SIGN_QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as PendingSignQueueItem[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((row) => typeof row?.id === "string");
  } catch {
    return [];
  }
}

function savePendingSignQueue(queue: PendingSignQueueItem[]) {
  localStorage.setItem(OFFLINE_SIGN_QUEUE_KEY, JSON.stringify(queue));
}

export function enqueuePendingSign(item: Omit<PendingSignQueueItem, "id">) {
  const queue = getPendingSignQueue();
  const next: PendingSignQueueItem = {
    ...item,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
  };
  queue.push(next);
  savePendingSignQueue(queue);
}

export function removePendingSignQueueItems(ids: string[]) {
  const idSet = new Set(ids);
  const queue = getPendingSignQueue().filter((item) => !idSet.has(item.id));
  savePendingSignQueue(queue);
}

