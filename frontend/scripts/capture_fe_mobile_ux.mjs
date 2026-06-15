/**
 * 기능인인정제 모바일 UX 캡처 (현장·HQ)
 * Usage: node scripts/capture_fe_mobile_ux.mjs
 */
import { chromium, devices } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/reports/functional-eval-e2e/screenshots/mobile-ux");
const FE = process.env.FE_BASE || "https://www.besma.co.kr";
const API = process.env.API_BASE || "https://api.besma.co.kr";

const ACCOUNTS = [
  { key: "site", login: "대우청라-박명식", password: "661123", path: "/site/functional-eval" },
  { key: "hq", login: "안전보건-정상익", password: "790808", path: "/hq-safe/functional-eval" },
];

async function login(login, password) {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: login, password }),
  });
  if (!res.ok) throw new Error(`login ${login} ${res.status}`);
  return (await res.json()).access_token;
}

async function capture(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  console.log("saved", file);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const iphone = devices["iPhone 13"];
  for (const acc of ACCOUNTS) {
    const ctx = await browser.newContext({ ...iphone, locale: "ko-KR" });
    const page = await ctx.newPage();
    try {
      const token = await login(acc.login, acc.password);
      await page.goto(`${FE}/login`, { waitUntil: "domcontentloaded" });
      await page.evaluate((t) => localStorage.setItem("besma_token", t), token);
      await page.goto(`${FE}${acc.path}`, { waitUntil: "networkidle", timeout: 30000 });
      await page.waitForTimeout(2500);
      await capture(page, `${acc.key}-top-before-scroll`);
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight * 0.35));
      await page.waitForTimeout(400);
      await capture(page, `${acc.key}-after-scroll`);
      const metrics = await page.evaluate(() => ({
        scrollY: window.scrollY,
        innerH: window.innerHeight,
        sidebarVisible: !!document.querySelector(".layout-sidebar")?.getBoundingClientRect().width,
        sidebarRect: document.querySelector(".layout-sidebar")?.getBoundingClientRect(),
        mainRect: document.querySelector(".layout-main, .fe-page")?.getBoundingClientRect(),
      }));
      console.log(acc.key, JSON.stringify(metrics, null, 2));
    } catch (err) {
      console.error(acc.key, err?.message || err);
    } finally {
      await ctx.close();
    }
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
