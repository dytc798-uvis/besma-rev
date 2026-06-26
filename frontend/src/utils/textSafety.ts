const BROKEN_TEXT_RE = /\?{2,}|\uFFFD|[\u937e\uc8c2\u73e5\ub85c\ub9c8\uc139\uc12c\uc4f0]/;
const BUNDLE_RELOAD_KEY = "besma_bundle_reload_guard_v1";

export function looksBrokenText(value: unknown): boolean {
  if (typeof value !== "string") return false;
  return BROKEN_TEXT_RE.test(value);
}

export function safeKo(primary: string, fallback: string): string {
  return looksBrokenText(primary) ? fallback : primary;
}

function currentBundleName(): string | null {
  if (typeof document === "undefined") return null;
  const scripts = Array.from(document.scripts);
  for (const script of scripts) {
    const src = script.getAttribute("src") || "";
    const match = src.match(/\/assets\/index-[^/]+\.js(?:\?|$)/);
    if (match) return match[0].replace(/^\//, "").replace(/\?.*$/, "");
  }
  return null;
}

function latestBundleNameFromHtml(html: string): string | null {
  const match = html.match(/assets\/index-[^\"' >]+\.js/);
  return match?.[0] ?? null;
}

function reloadOnceForBundle(latestBundle: string): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  let last = 0;
  try {
    last = Number(sessionStorage.getItem(BUNDLE_RELOAD_KEY) || "0");
  } catch {
    last = 0;
  }
  if (Number.isFinite(last) && now - last < 30000) return;
  try {
    sessionStorage.setItem(BUNDLE_RELOAD_KEY, String(now));
  } catch {
    // ignore
  }
  const url = new URL(window.location.href);
  url.searchParams.set("v", latestBundle.replace(/[^a-zA-Z0-9_-]/g, "").slice(-24) || String(now));
  window.location.replace(url.toString());
}

export async function checkAndReloadIfStaleBundle(): Promise<void> {
  if (typeof window === "undefined" || typeof fetch === "undefined") return;
  if (!window.location.hostname.endsWith("besma.co.kr")) return;
  const current = currentBundleName();
  if (!current) return;
  try {
    const res = await fetch(`/?__besma_bundle_check=${Date.now()}`, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { "Cache-Control": "no-cache" },
    });
    const html = await res.text();
    const latest = latestBundleNameFromHtml(html);
    if (latest && latest !== current) reloadOnceForBundle(latest);
  } catch {
    // Network failures must not block field operation.
  }
}

export function installBundleFreshnessGuard(): void {
  if (typeof window === "undefined") return;
  const run = () => void checkAndReloadIfStaleBundle();
  window.setTimeout(run, 1500);
  window.addEventListener("focus", run);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) run();
  });
  window.setInterval(run, 30 * 60 * 1000);
}
