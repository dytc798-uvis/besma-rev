import { chromium } from "playwright";

const base = process.env.BESMA_UI_BASE || "http://127.0.0.1:5173";
const out = "D:/JSI/outbox";
const browser = await chromium.launch({ headless: true });
const results = [];

async function mockApi(page) {
  await page.addInitScript(() => localStorage.setItem("besma_token", "ui-smoke-token"));
  const handler = async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/auth/me") body = { id: 10, name: "현장 점검자", login_id: "site10", role: "SITE", ui_type: "SITE", site_id: 1, person_id: null, department: "안전", must_change_password: false };
    else if (path === "/heat-stress/records") body = { items: [], count: 0 };
    else if (path === "/documents/badges/site") body = { incomplete_count: 0 };
    else if (path === "/communications/unread-count") body = { unread_count: 0 };
    else if (path === "/sites/1") body = { id: 1, site_name: "테스트 현장" };
    else if (path === "/notices/latest") body = { items: [] };
    else if (path === "/documents/comments/peer-count") body = { count: 0 };
    else if (path === "/dynamic-menus/sidebar") body = { items: [] };
    else if (path === "/dynamic-menus/menu-order/SITE") body = { primary: [], secondary: [] };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  };
  await page.route("http://127.0.0.1:8001/**", handler);
  await page.route("https://api.besma.co.kr/**", handler);
}

for (const profile of [
  { name: "desktop", viewport: { width: 1440, height: 1000 }, expectedCards: 5 },
  { name: "mobile", viewport: { width: 390, height: 844 }, expectedCards: 3 },
]) {
  const page = await browser.newPage({ viewport: profile.viewport });
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => pageErrors.push(String(e)));
  await mockApi(page);
  await page.goto(`${base}/site/home`, { waitUntil: "networkidle" });
  const cards = await page.locator(".home-card").count();
  await page.screenshot({ path: `${out}/026_체감온도_홈_${profile.name}.png`, fullPage: true });
  await page.goto(`${base}/site/heat-stress`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "체감온도 기록", exact: true }).waitFor();
  const apparent = await page.locator(".temperature-result strong").innerText();
  await page.screenshot({ path: `${out}/026_체감온도_입력_${profile.name}.png`, fullPage: true });
  results.push({ profile: profile.name, cards, expectedCards: profile.expectedCards, apparent, consoleErrors, pageErrors });
  await page.close();
}
await browser.close();
if (results.some((r) => r.cards !== r.expectedCards || r.consoleErrors.length || r.pageErrors.length)) {
  console.error(JSON.stringify(results, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(results, null, 2));
