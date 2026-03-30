const PREVIEWABLE_EXTENSIONS = new Set([
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "bmp",
  "svg",
]);

export function extractExtension(fileName: string | null | undefined): string {
  if (!fileName) return "";
  const normalized = fileName.trim().toLowerCase();
  const dotIndex = normalized.lastIndexOf(".");
  if (dotIndex < 0 || dotIndex === normalized.length - 1) return "";
  return normalized.slice(dotIndex + 1);
}

export function canPreviewInBrowser(fileName: string | null | undefined): boolean {
  return PREVIEWABLE_EXTENSIONS.has(extractExtension(fileName));
}

export function isPdfFile(fileName: string | null | undefined): boolean {
  return extractExtension(fileName) === "pdf";
}

export function isImageFile(fileName: string | null | undefined): boolean {
  const ext = extractExtension(fileName);
  return ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(ext);
}
