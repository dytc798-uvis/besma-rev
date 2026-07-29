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
  { key: "site", login: "대우청라-박명식", password: "<REDACTED_FOR_MIGRATION>", path: "/site/functional-eval" },
  { key: "hq", login: "안전보건-정상익", password: "<REDACTED_FOR_MIGRATION>", path: "/hq-safe/functional-eval" },
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

async function sidebarMetrics(page) {
  return page.evaluate(() => {
    const sidebar = document.querySelector(".layout-sidebar");
    const rect = sidebar?.getBoundingClientRect();
    const menuBtn = document.querySelector(".sidebar-toggle-btn--mobile");
    return {
      sidebarLeft: rect?.left ?? null,
      sidebarWidth: rect?.width ?? null,
      menuBtnText: menuBtn?.textContent?.trim() ?? null,
      drawerOpen: document.querySelector(".layout-root")?.classList.contains("mobile-drawer-open") ?? false,
    };
  });
}

async function runAccount(browser, acc) {
  const ctx = await browser.newContext({ ...devices["iPhone 13"], locale: "ko-KR" });
  const page = await ctx.newPage();
  try {
    const token = await login(acc.login, acc.password);
    await page.goto(`${FE}/login`, { waitUntil: "domcontentloaded" });
    await page.evaluate((t) => localStorage.setItem("besma_token", t), token);
    await page.goto(`${FE}${acc.path}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(1500);

    const before = await sidebarMetrics(page);
    console.log(`${acc.key} collapsed`, JSON.stringify(before));
    await capture(page, `${acc.key}-menu-collapsed`);

    // 동의서 전체화면일 때는 헤더·메뉴 버튼이 숨겨지므로, 메뉴 UX만 검증하기 위해 오버레이를 잠시 숨김
    await page.evaluate(() => {
      document.querySelectorAll(".fe-sign-overlay, .fe-consent-loading").forEach((el) => {
        el.dataset.captureHidden = "1";
        el.style.display = "none";
      });
      const header = document.querySelector(".layout-header");
      if (header) header.style.display = "";
    });
    await page.waitForTimeout(200);

    const menuBtn = page.locator(".sidebar-toggle-btn--mobile").first();
    if (await menuBtn.count()) {
      await menuBtn.click({ force: true });
    } else {
      // 현장: 동의서 중에는 헤더가 v-if로 없음 → 드로어만 직접 열어 펼침 UX 캡처
      await page.evaluate(() => {
        document.querySelector(".layout-root")?.classList.add("mobile-drawer-open");
      });
    }
    await page.waitForTimeout(400);
    const opened = await sidebarMetrics(page);
    console.log(`${acc.key} expanded`, JSON.stringify(opened));
    await capture(page, `${acc.key}-menu-expanded`);
  } catch (err) {
    console.error(acc.key, err?.message || err);
    throw err;
  } finally {
    await ctx.close();
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  for (const acc of ACCOUNTS) {
    await runAccount(browser, acc);
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
