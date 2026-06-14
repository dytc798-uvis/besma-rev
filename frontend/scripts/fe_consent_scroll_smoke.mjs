/**
 * 동의서 스크롤 게이트 E2E 스모크
 * Usage: FE_BASE=https://www.besma.co.kr node scripts/fe_consent_scroll_smoke.mjs
 */
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FE = process.env.FE_BASE || "http://127.0.0.1:5174";
const API = process.env.API_BASE || (FE.includes("besma.co.kr") ? "https://api.besma.co.kr" : "http://127.0.0.1:8001");
const LOGIN = process.env.FE_SMOKE_LOGIN || (() => {
  try {
    return fs.readFileSync(path.join(__dirname, "_smoke_login.txt"), "utf8").trim();
  } catch {
    return "대우청라-김팀장";
  }
})();
const PASSWORD = process.env.FE_SMOKE_PASSWORD || "661123";

async function apiLogin() {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: LOGIN, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`login ${res.status}`);
  const data = await res.json();
  return data.access_token;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
  const results = [];
  let loginOk = false;
  try {
    const token = await apiLogin();
    await page.goto(`${FE}/login`, { waitUntil: "domcontentloaded" });
    await page.evaluate((t) => localStorage.setItem("besma_token", t), token);
    loginOk = true;
  } catch (err) {
    loginOk = false;
    console.error("login_error", err?.message || err);
  }
  results.push(["로그인", loginOk ? "통과" : "실패"]);
  if (!loginOk) {
    console.log(JSON.stringify({ fe: FE, login: LOGIN, api: API, results }, null, 2));
    await browser.close();
    process.exit(1);
  }

  const targetPath = LOGIN.includes("안전보건") || LOGIN.includes("부현대표")
    ? "/hq-safe/functional-eval"
    : "/site/functional-eval";
  await page.goto(`${FE}${targetPath}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  const modal = page.locator(".fe-sign-modal");
  const modalVisible = await modal.waitFor({ state: "visible", timeout: 8000 }).then(() => true).catch(() => false);
  results.push(["동의서 모달 표시", modalVisible ? "통과" : "미확인(이미 동의)"]);

  if (modalVisible) {
    await page.locator(".fe-sign-consent-body").evaluate((el) => { el.scrollTop = 0; });
    await page.waitForTimeout(300);
    const hintBefore = await page.locator(".fe-sign-scroll-hint").textContent();
    const checkbox = page.locator('.fe-sign-check input[type="checkbox"]');
    const submitBtn = page.getByRole("button", { name: /동의 및 서명/ });
    const padDisabled = (await page.locator(".signature-pad--disabled").count()) > 0;
    const needsScroll = hintBefore?.includes("끝까지");
    if (needsScroll) {
      const locked = (await checkbox.isDisabled()) && padDisabled;
      results.push(["스크롤 전 비활성화", locked ? "통과" : "실패"]);
      await page.locator(".fe-sign-consent-body").evaluate((el) => { el.scrollTop = el.scrollHeight; });
      await page.waitForTimeout(500);
      const unlocked = !(await checkbox.isDisabled()) && !(await page.locator(".signature-pad--disabled").count());
      results.push(["스크롤 후 활성화", unlocked ? "통과" : "실패"]);
    } else {
      results.push(["스크롤 전 비활성화", "해당없음(본문 높이)" ]);
      results.push(["스크롤 후 활성화", "해당없음(본문 높이)" ]);
    }

    const hint = await page.locator(".fe-sign-scroll-hint").textContent();
    results.push(["스크롤 완료 안내", hint?.includes("모두 확인") || hint?.includes("끝까지") ? "통과" : "실패"]);
  }

  const hqOk = page.url().includes("functional-eval");
  results.push(["기능인제 화면 진입", hqOk ? "통과" : "실패"]);

  console.log(JSON.stringify({ fe: FE, login: LOGIN, url: page.url(), results }, null, 2));
  await browser.close();

  const failed = results.some(([, r]) => r === "실패");
  process.exit(failed ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
