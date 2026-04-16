/**
 * 모바일에서 일일 문서(TBM·일일안전회의 등) 업로드 전 사진을 기기에 임시 보관합니다.
 * (localStorage, 키: 현장+작업일+문서코드)
 */

export type DailyDraftPhoto = {
  id: string;
  dataUrl: string;
  name: string;
  createdAt: number;
};

const PREFIX = "besma.draft.photos.v1";

function key(siteId: number, workDate: string, documentTypeCode: string) {
  return `${PREFIX}:${siteId}:${workDate}:${documentTypeCode}`;
}

function loadRaw(siteId: number, workDate: string, documentTypeCode: string): DailyDraftPhoto[] {
  try {
    const raw = localStorage.getItem(key(siteId, workDate, documentTypeCode));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (row): row is DailyDraftPhoto =>
        !!row &&
        typeof row === "object" &&
        typeof (row as DailyDraftPhoto).id === "string" &&
        typeof (row as DailyDraftPhoto).dataUrl === "string",
    );
  } catch {
    return [];
  }
}

function saveRaw(siteId: number, workDate: string, documentTypeCode: string, items: DailyDraftPhoto[]) {
  localStorage.setItem(key(siteId, workDate, documentTypeCode), JSON.stringify(items));
}

export function listDraftPhotos(siteId: number, workDate: string, documentTypeCode: string): DailyDraftPhoto[] {
  return loadRaw(siteId, workDate, documentTypeCode);
}

export function clearDraftPhotos(siteId: number, workDate: string, documentTypeCode: string) {
  localStorage.removeItem(key(siteId, workDate, documentTypeCode));
}

export async function addDraftPhotosFromFiles(
  siteId: number,
  workDate: string,
  documentTypeCode: string,
  files: FileList | File[],
): Promise<void> {
  const list = Array.from(files);
  if (!list.length) return;
  const existing = loadRaw(siteId, workDate, documentTypeCode);
  for (const file of list) {
    if (!file.type.startsWith("image/")) continue;
    const dataUrl = await fileToDataUrl(file);
    existing.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      dataUrl,
      name: file.name || "photo.jpg",
      createdAt: Date.now(),
    });
  }
  saveRaw(siteId, workDate, documentTypeCode, existing);
}

export function removeDraftPhoto(siteId: number, workDate: string, documentTypeCode: string, id: string) {
  const existing = loadRaw(siteId, workDate, documentTypeCode).filter((p) => p.id !== id);
  saveRaw(siteId, workDate, documentTypeCode, existing);
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("read_failed"));
    reader.readAsDataURL(file);
  });
}

export function dataUrlToBlob(dataUrl: string): Blob {
  const [header, b64] = dataUrl.split(",");
  if (!b64) throw new Error("invalid_data_url");
  const mime = /data:([^;]+);/.exec(header)?.[1] || "image/jpeg";
  const binary = atob(b64);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    arr[i] = binary.charCodeAt(i);
  }
  return new Blob([arr], { type: mime });
}
