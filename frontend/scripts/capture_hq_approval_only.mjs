import { chromium } from "playwright";
import path from "node:path";

const OUT = path.resolve("d:/JSI/besma-rev/docs/reports/functional-eval-e2e/screenshots/a4-manual");
const FE = process.env.FE_BASE || "http://127.0.0.1:5174";

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
const page = await ctx.newPage();
await page.goto(`${FE}/login`, { waitUntil: "networkidle" });
await page.fill('input[type="text"]', "안전보건-조동문");
await page.fill('input[type="password"]', "600321");
await page.click('button[type="submit"]');
await page.waitForTimeout(1500);
await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
const consent = page.locator(".fe-sign-modal");
if (await consent.isVisible().catch(() => false)) {
  await page.locator('.fe-sign-check input[type="checkbox"]').check().catch(() => {});
  await page.getByRole("button", { name: /동의 및 서명|서명 완료/ }).click().catch(() => {});
  await page.waitForTimeout(1000);
}
await page.getByRole("button", { name: /승인·마감·운영/ }).click();
await page.waitForTimeout(1500);
await page.locator(".approval-queue-panel").first().screenshot({ path: path.join(OUT, "hq_approval.png") });
console.log("ok hq_approval");
await browser.close();
