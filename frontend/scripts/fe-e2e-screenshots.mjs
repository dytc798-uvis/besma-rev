/**
 * 기능인제 E2E 단계별 UI 캡처
 * Usage: node scripts/fe-e2e-screenshots.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "..", "..", "docs", "reports", "functional-eval-e2e", "screenshots");
const FE = process.env.FE_BASE || "http://127.0.0.1:5174";

const PHASE = process.argv[2] || "all";

const SHOTS = [
  { phase: "pre", file: "01_team_leader_roster", login: "대우청라-김팀장", password: "<REDACTED_FOR_MIGRATION>", url: "/site/functional-eval", wait: 2500 },
  { phase: "pre", file: "02_manager_roster_pending", login: "대우청라-박명식", password: "<REDACTED_FOR_MIGRATION>", url: "/site/functional-eval", wait: 2500 },
  { phase: "post", file: "03_hq_approvals", login: "안전보건-조동문", password: "<REDACTED_FOR_MIGRATION>", url: "/hq-safe/functional-eval", wait: 3000 },
  { phase: "post", file: "04_ceo_approvals", login: "부현대표-김홍수", password: "<REDACTED_FOR_MIGRATION>", url: "/hq-safe/functional-eval", wait: 3000 },
  { phase: "post", file: "05_manager_final", login: "대우청라-박명식", password: "<REDACTED_FOR_MIGRATION>", url: "/site/functional-eval", wait: 2500 },
];

const ACTIVE = SHOTS.filter((s) => PHASE === "all" || s.phase === PHASE);

async function login(page, loginId, password) {
  await page.goto(`${FE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="text"]', loginId);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1200);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  for (const item of ACTIVE) {
    const context = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await context.newPage();
    try {
      await login(page, item.login, item.password);
      await page.goto(`${FE}${item.url}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(item.wait);
      const outPath = path.join(OUT, `${item.file}.png`);
      await page.screenshot({ path: outPath, fullPage: true });
      console.log("ok", item.file);
    } catch (e) {
      console.error("fail", item.file, e.message);
    } finally {
      await context.close();
    }
  }

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
