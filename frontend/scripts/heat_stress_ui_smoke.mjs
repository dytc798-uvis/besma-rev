import { chromium } from "playwright";

const base = process.env.BESMA_UI_BASE || "http://127.0.0.1:5173";
const out = "D:/JSI/outbox";
const browser = await chromium.launch({ headless: true });
const results = [];

async function mockApi(page, persona = "SITE") {
  await page.addInitScript(() => localStorage.setItem("besma_token", "ui-smoke-token"));
  await page.route("http://127.0.0.1:8001/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/auth/me") body = persona === "HQ_SAFE"
      ? { id: 20, name: "본사 안전관리자", login_id: "hq20", role: "HQ_SAFE", ui_type: "HQ_SAFE", site_id: null, person_id: null, department: "안전", must_change_password: false }
      : { id: 10, name: "현장 점검자", login_id: "site10", role: "SITE", ui_type: "SITE", site_id: 1, person_id: null, department: "안전", must_change_password: false };
    else if (path === "/heat-stress/records") body = { items: [{
      id: 101,
      site_id: 1,
      site_name: "테스트 현장",
      measured_at: "2026-08-04T09:00:00",
      work_location: "지상 3층 외부",
      work_process: "배관 설치",
      recorder_name: "현장 점검자",
      air_temperature_c: 33,
      relative_humidity_pct: 70,
      apparent_temperature_c: 34.3,
      risk_level: "CAUTION",
      risk_label: "주의",
      status: "CONFIRM_PENDING",
      action_compliance: "RECORDED",
      actual_action_labels: ["물 제공", "휴식 실시"],
    }], count: 1 };
    else if (path === "/weather/location-overview") body = {
      location_name: "테스트 현장",
      location_source: "SITE",
      location_attribution: "테스트 좌표",
      source_label: "기상청 단기예보",
      source: "KMA_TEST",
      kma_notice: "기상청 참고자료입니다.",
      current: {
        weather_label: "맑음",
        temperature_c: 33,
        relative_humidity_pct: 70,
        apparent_temperature_c: 34.3,
        precipitation_mm: 0,
        wind_speed_kmh: 4,
      },
      forecast_days: [],
    };
    else if (path === "/heat-stress/hq-summary") body = {
      total_record_count: 1,
      missing_site_count: 0,
      at_or_above_31_count: 1,
      at_or_above_33_count: 1,
      action_required_count: 0,
      confirm_pending_count: 1,
    };
    else if (path === "/documents/badges/site") body = { incomplete_count: 0 };
    else if (path === "/communications/unread-count") body = { unread_count: 0 };
    else if (path === "/sites/1") body = { id: 1, site_name: "테스트 현장" };
    else if (path === "/notices/latest") body = { items: [] };
    else if (path === "/documents/comments/peer-count") body = { count: 0 };
    else if (path === "/dynamic-menus/sidebar") body = { items: [] };
    else if (path === "/dynamic-menus/menu-order/SITE") body = { primary: [], secondary: [] };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
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
  const siteLedgerButtonVisible = await page.getByRole("button", { name: "체감온도관리대장", exact: true }).isVisible();
  await page.getByRole("button", { name: "추가 측정 기록", exact: true }).click();
  const apparent = await page.locator(".temperature-result strong").innerText();
  const persistedLocation = await page.locator("label").filter({ hasText: "작업장소" }).locator("input").inputValue();
  await page.screenshot({ path: `${out}/026_체감온도_입력_${profile.name}.png`, fullPage: true });
  results.push({ kind: "site", profile: profile.name, cards, expectedCards: profile.expectedCards, apparent, persistedLocation, siteLedgerButtonVisible, consoleErrors, pageErrors });
  await page.close();
}

const hqPage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const hqConsoleErrors = [];
const hqPageErrors = [];
hqPage.on("console", (m) => m.type() === "error" && hqConsoleErrors.push(m.text()));
hqPage.on("pageerror", (e) => hqPageErrors.push(String(e)));
await mockApi(hqPage, "HQ_SAFE");
await hqPage.goto(`${base}/hq-safe/heat-stress`, { waitUntil: "networkidle" });
await hqPage.getByRole("heading", { name: "체감온도 기록 현황", exact: true }).waitFor();
const ledgerButtonVisible = await hqPage.getByRole("button", { name: "체감온도관리대장", exact: true }).isVisible();
const groupedSiteHeading = (await hqPage.locator(".site-group").first().innerText()).includes("테스트 현장");
await hqPage.screenshot({ path: `${out}/026_체감온도_관리대장_버튼_hq.png`, fullPage: true });
results.push({ kind: "hq", profile: "hq-desktop", ledgerButtonVisible, groupedSiteHeading, consoleErrors: hqConsoleErrors, pageErrors: hqPageErrors });
await hqPage.close();

await browser.close();
if (results.some((r) => (r.kind === "site" && (r.cards !== r.expectedCards || r.persistedLocation !== "지상 3층 외부" || !r.siteLedgerButtonVisible)) || (r.kind === "hq" && (!r.ledgerButtonVisible || !r.groupedSiteHeading)) || r.consoleErrors.length || r.pageErrors.length)) {
  console.error(JSON.stringify(results, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(results, null, 2));
