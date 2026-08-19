import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const appUrl = process.env.RISK_CAPTURE_URL || "https://www.besma.co.kr/site/risk-library";
const outputDir = path.resolve(
  process.env.RISK_CAPTURE_OUT || "D:/JSI/.tmp/risk-rev07-web-visual",
);
const phase = process.env.RISK_CAPTURE_PHASE || "before";

const sampleRows = [
  {
    trade: "전기공사",
    process: "가설전기(전선·충전부·분전반)",
    hazard: "건물 인입구 연결작업 중 충전부에 접촉되어 감전",
    counterplan: "작업 전 해당 전로를 차단하고 검전 후 작업한다. 활선작업 시 절연용 보호구를 지급하고 착용상태를 확인한다.",
    f: 3,
    s: 5,
    r: 15,
    grade: "중대",
    note: null,
  },
  {
    trade: "전기공사",
    process: "이동식 사다리 작업",
    hazard: "A형 사다리가 넘어지면서 작업자가 추락",
    counterplan: "이동식 사다리는 2인 1조로 사용하고 아웃트리거를 체결한다. 작업 전 바닥 상태와 사다리 고정상태를 확인한다.",
    f: 3,
    s: 4,
    r: 12,
    grade: "상당",
    note: null,
  },
  {
    trade: "전기공사",
    process: "고소작업대",
    hazard: "(사고사례) 고소작업대에서 트레이 설치 중 손가락이 트레이 사이에 협착",
    counterplan: "TBM에서 협착 위험구간과 안전한 손 위치를 반복 교육하고 협착방지장갑 착용상태를 확인한다.",
    f: 4,
    s: 4,
    r: 16,
    grade: "허용불가",
    note: "25년10월 사고",
  },
  {
    trade: "전기공사",
    process: "케이블 포설",
    hazard: "케이블 드럼이 경사면에서 이동하여 작업자와 충돌하거나 손·발이 협착",
    counterplan: "드럼 받침대와 구름방지 쐐기를 설치하고 신호수를 배치한다. 포설구간 출입을 통제하고 작업 전 장비상태를 점검한다.",
    f: 4,
    s: 5,
    r: 20,
    grade: "허용불가",
    note: null,
  },
  {
    trade: "소방공사",
    process: "배관 인양·설치",
    hazard: "체인블록으로 배관 인양 중 결속부 이탈로 배관이 낙하",
    counterplan: "정격하중에 맞는 인양기구를 사용하고 결속상태를 이중 확인한다. 인양물 하부 출입을 금지하고 유도자를 배치한다.",
    f: 3,
    s: 5,
    r: 15,
    grade: "중대",
    note: null,
  },
  {
    trade: "정보통신공사",
    process: "천장 내부 배선",
    hazard: "천장 달대볼트와 날카로운 철물에 손이 베이거나 머리가 부딪힘",
    counterplan: "절단면을 제거하거나 보호캡을 설치하고 안전모·절단방지장갑을 착용한다. 작업 전 이동통로를 확보한다.",
    f: 2,
    s: 3,
    r: 6,
    grade: "미미",
    note: null,
  },
  {
    trade: "기계설비공사",
    process: "중량물 운반",
    hazard: "무리한 작업자세로 중량물을 운반하여 허리와 어깨에 근골격계 부담 발생",
    counterplan: "중량과 이동거리를 확인해 운반장비를 사용하고 2인 이상 공동작업을 실시한다. 작업 전 스트레칭을 실시한다.",
    f: 2,
    s: 3,
    r: 6,
    grade: "미미",
    note: null,
  },
  {
    trade: "전기공사",
    process: "고소작업대 하차",
    hazard: "(사고사례) 고소작업대 하차 중 바닥의 콘크리트 잔재를 밟아 발목을 접질림",
    counterplan: "하차 전 바닥상태를 확인하고 작업구간을 정리정돈한다. 수시 위험성평가 결과를 TBM에서 공유한다.",
    f: 4,
    s: 4,
    r: 16,
    grade: "허용불가",
    note: "24년06월 사고",
  },
].map((row, index) => ({
  risk_revision_id: index + 1,
  risk_item_id: index + 101,
  unit_work: row.trade,
  work_category: row.trade,
  trade_type: row.trade,
  process: row.process,
  risk_factor: row.hazard,
  counterplan: row.counterplan,
  risk_f: row.f,
  risk_s: row.s,
  risk_r: row.r,
  display_f: row.f,
  display_s: row.s,
  display_r: row.r,
  risk_grade: row.grade,
  evaluation_method: "회사 4×5",
  improvement_owner_name: "김현장",
  improvement_verifier_name: "이안전",
  note: row.note,
  source_file: null,
  source_sheet: null,
  source_row: null,
  source_page_or_section: null,
  score: 0,
  matched_tokens: [],
  matched_fields: [],
}));

const riskResponse = {
  mode: "quick",
  normalized_query: "",
  query_tokens: [],
  total: sampleRows.length,
  limit: 50,
  offset: 0,
  contractor_key: "대우건설",
  contractor_name: "대우건설",
  evaluation_method: "회사 4×5",
  can_print: true,
  contractor_options: [
    { contractor_key: "대우건설", contractor_name: "대우건설", evaluation_method: "회사 4×5" },
  ],
  designation: {
    site_id: 1,
    site_name: "BESMA 테스트 현장",
    inspector_name: "김현장",
    verifier_name: "이안전",
    appointed_on: "2026-08-19",
    note: "현장 위험성평가 담당",
    can_edit: true,
  },
  results: sampleRows,
};

await fs.mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1680, height: 1050 },
  locale: "ko-KR",
  colorScheme: "light",
  deviceScaleFactor: 1,
});
await context.addInitScript(() => {
  window.localStorage.setItem("besma_token", "visual-capture-token");
});
const page = await context.newPage();
const handleApiRequest = async (route) => {
  const request = route.request();
  const url = new URL(request.url());
  const json = (value) => route.fulfill({
    status: 200,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(value),
  });
  if (url.pathname === "/auth/me") {
    await json({
      id: 1,
      name: "현장 관리자",
      login_id: "visual-site",
      role: "SITE",
      must_change_password: false,
      needs_fe_consent: false,
      fe_consent_required: false,
      ui_type: "SITE",
      site_id: 1,
      person_id: null,
    });
    return;
  }
  if (url.pathname === "/search/risk-library") {
    await json(riskResponse);
    return;
  }
  if (url.pathname === "/search/risk-assessment/designation") {
    await json(riskResponse.designation);
    return;
  }
  if (url.pathname.includes("/site-assignment")) {
    await json({
      site_id: 1,
      risk_item_id: 101,
      improvement_owner_name: "김현장",
      improvement_verifier_name: "이안전",
    });
    return;
  }
  await json([]);
};
await page.route("https://api.besma.co.kr/**", handleApiRequest);
await page.route("http://127.0.0.1:8001/**", handleApiRequest);
await page.route("http://localhost:8001/**", handleApiRequest);

await page.goto(appUrl, { waitUntil: "networkidle" });
await page.locator(".risk-library-page").waitFor({ state: "visible" });
await page.screenshot({
  path: path.join(outputDir, `risk-library-desktop-${phase}.png`),
  fullPage: true,
});

await page.setViewportSize({ width: 430, height: 932 });
await page.waitForTimeout(250);
await page.screenshot({
  path: path.join(outputDir, `risk-library-mobile-${phase}.png`),
  fullPage: true,
});
await page.setViewportSize({ width: 1680, height: 1050 });
await page.waitForTimeout(250);

await page.evaluate(() => {
  window.print = () => {};
});
await page.getByRole("button", { name: "검색결과 인쇄" }).click();
await page.waitForTimeout(300);
await page.emulateMedia({ media: "print" });
await page.evaluate(() => {
  const pageRoot = document.querySelector(".risk-library-page");
  if (pageRoot) pageRoot.classList.add("visual-print-capture");
});
const printState = await page.locator(".print-sheet").evaluate((element) => ({
  display: getComputedStyle(element).display,
  visibility: getComputedStyle(element).visibility,
  page: getComputedStyle(element).page,
  rows: element.querySelectorAll("tbody tr").length,
  rect: element.getBoundingClientRect().toJSON(),
}));
if (
  printState.display === "none"
  || printState.visibility !== "visible"
  || printState.page !== "risk-library"
  || printState.rows !== sampleRows.length
) {
  throw new Error(`unexpected print state: ${JSON.stringify(printState)}`);
}
console.log(`print_state=visible rows=${printState.rows} page=${printState.page}`);
await page.screenshot({
  path: path.join(outputDir, `risk-library-print-${phase}.png`),
  fullPage: true,
});
await page.pdf({
  path: path.join(outputDir, `risk-library-print-${phase}.pdf`),
  preferCSSPageSize: true,
  printBackground: true,
  margin: { top: "10mm", right: "10mm", bottom: "10mm", left: "10mm" },
});

console.log(`captured=${outputDir}`);
await browser.close();
