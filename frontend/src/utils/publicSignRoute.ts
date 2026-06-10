/** 외부 PDF 서명 임시 페이지 — 로그인·loadMe·401 리다이렉트 제외 */
export function isPublicSignPath(pathname: string): boolean {
  const path = normalizePublicSignPath(pathname);
  if (path.startsWith("/sign/")) return true;
  return path === "/temp/sign1" || path === "/temp/sign2";
}

export function normalizePublicSignPath(pathname: string): string {
  let path = pathname.trim();
  try {
    path = decodeURIComponent(path);
  } catch {
    /* ignore */
  }
  return path.replace(/\\/g, "/").replace(/\/+/g, "/").replace(/\/$/, "") || "/";
}
