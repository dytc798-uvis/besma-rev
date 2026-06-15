import type { AxiosResponseHeaders, RawAxiosResponseHeaders } from "axios";

export function resolveFilenameFromHeader(headerValue: string | undefined, fallback: string): string {
  if (!headerValue) return fallback;
  const matchUtf = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (matchUtf?.[1]) {
    try {
      return decodeURIComponent(matchUtf[1]);
    } catch {
      return fallback;
    }
  }
  const matchPlain = headerValue.match(/filename="?([^";]+)"?/i);
  return matchPlain?.[1] ?? fallback;
}

function contentDispositionFromHeaders(
  headers: RawAxiosResponseHeaders | AxiosResponseHeaders | undefined,
): string | undefined {
  if (!headers) return undefined;
  const raw = headers["content-disposition"] ?? headers["Content-Disposition"];
  return typeof raw === "string" ? raw : undefined;
}

/** blob 응답을 지정 파일명으로 저장 (window.open 대신 사용) */
export function downloadBlobAsFile(
  blob: Blob,
  fallbackFilename: string,
  headers?: RawAxiosResponseHeaders | AxiosResponseHeaders,
) {
  const filename = resolveFilenameFromHeader(contentDispositionFromHeaders(headers), fallbackFilename);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
