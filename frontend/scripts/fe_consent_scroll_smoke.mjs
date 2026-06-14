/**
 * 동의서 스크롤 게이트 E2E 스모크
 * Usage: FE_BASE=https://www.besma.co.kr node scripts/fe_consent_scroll_smoke.mjs
 */
import { chromium } from "playwright";

const FE = process.env.FE_BASE || "http://127.0.0.1:5174";
const LOGIN = process.env.FE_SMOKE_LOGIN || "대우청라-김팀장";
const PASSWORD = process.env.FE_SMOKE_PASSWORD || "750101";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
  const results = [];

  await page.goto(`${FE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="text"]', LOGIN);
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);

  await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  const modal = page.locator(".fe-sign-modal");
  const modalVisible = await modal.isVisible().catch(() => false);
  results.push(["동의서 모달 표시", modalVisible ? "통과" : "미확인(이미 동의)"]);

  if (modalVisible) {
    await page.locator(".fe-sign-consent-body").evaluate((el) => { el.scrollTop = 0; });
    const checkbox = page.locator('.fe-sign-check input[type="checkbox"]');
    const submitBtn = page.getByRole("button", { name: /동의 및 서명/ });
    const canvas = page.locator("canvas").first();
    const locked =
      (await checkbox.isDisabled()) &&
      (await submitBtn.isDisabled()) &&
      !(await canvas.evaluate((el) => getComputedStyle(el).pointerEvents !== "none").catch(() => false));
    results.push(["스크롤 전 비활성화", locked ? "통과" : "실패"]);

    await page.locator(".fe-sign-consent-body").evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await page.waitForTimeout(500);
    const unlocked = !(await checkbox.isDisabled()) && !(await submitBtn.isDisabled());
    results.push(["스크롤 후 활성화", unlocked ? "통과" : "실패"]);

    const hint = await page.locator(".fe-sign-scroll-hint").textContent();
    results.push(["스크롤 완료 안내", hint?.includes("모두 확인") ? "통과" : "실패"]);
  }

  await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  results.push(["HQ 화면 진입", page.url().includes("functional-eval") ? "통과" : "실패"]);

  console.log(JSON.stringify({ fe: FE, login: LOGIN, results }, null, 2));
  await browser.close();

  const failed = results.some(([, r]) => r === "실패");
  process.exit(failed ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
