/**
 * 기능인인정제 운영설명서(보고용) — 화면 캡처
 * Usage: node scripts/capture_fe_report_screenshots.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  fillLoginSample,
  fillRewardModalSample,
  fillSanctionModalSample,
  guideUrl,
  prepareEvaluateScreenshot,
} from "./feGuideCaptureHelpers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "..", "..", "docs", "reports", "functional-eval-e2e", "screenshots", "report");
const FE = process.env.FE_BASE || "http://127.0.0.1:5174";
const API = process.env.API_BASE || (FE.includes("besma.co.kr") ? "https://api.besma.co.kr" : "http://127.0.0.1:8001");

const ACCOUNTS = {
  team: { login: "대우청라-박명식", password: "661123", label: "소장(동의·현장)" },
  manager: { login: "대우청라-박명식", password: "661123", label: "소장" },
  hq: { login: "안전보건-조동문", password: "600321", label: "안전보건실장" },
  hqOfficer: { login: "안전보건-정상익", password: "600321", label: "안전보건 담당" },
  ceo: { login: "부현대표-김홍수", password: "611001", label: "대표이사" },
};

async function loginViaApi(page, { login, password }) {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: login, password }),
  });
  if (!res.ok) throw new Error(`login failed ${login} ${res.status}`);
  const { access_token: token } = await res.json();
  await page.goto(`${FE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((t) => localStorage.setItem("besma_token", t), token);
}

async function login(page, { login, password }) {
  if (FE.includes("besma.co.kr")) {
    await loginViaApi(page, { login, password });
    return;
  }
  await page.goto(`${FE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="text"]', login);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);
}

async function maskSensitive(page) {
  await page.addStyleTag({
    content: `
      td:nth-child(6), td:nth-child(7), td:nth-child(8),
      .rrn-cell, .phone-cell { filter: blur(6px) !important; }
    `,
  }).catch(() => {});
}

async function shot(page, name, opts = {}) {
  const outPath = path.join(OUT, `${name}.png`);
  if (opts.mask) await maskSensitive(page);
  if (opts.selector) {
    const el = page.locator(opts.selector).first();
    if (await el.count()) {
      await el.screenshot({ path: outPath });
      console.log("ok", name, "(element)");
      return;
    }
  }
  await page.screenshot({ path: outPath, fullPage: Boolean(opts.fullPage) });
  console.log("ok", name);
}

async function dismissConsentIfVisible(page) {
  const modal = page.locator(".fe-sign-modal");
  if (await modal.isVisible().catch(() => false)) {
    await page.locator(".fe-sign-consent-body").evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    }).catch(() => {});
    await page.locator('.fe-sign-check input[type="checkbox"]').check().catch(() => {});
    const canvas = page.locator("canvas").first();
    if (await canvas.count()) {
      const box = await canvas.boundingBox();
      if (box) {
        await page.mouse.move(box.x + 40, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width - 40, box.y + box.height / 2, { steps: 12 });
        await page.mouse.up();
      }
    }
    await page.getByRole("button", { name: /동의 및 서명|서명 완료/ }).click().catch(() => {});
    await page.waitForTimeout(1200);
  }
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  // 01 로그인
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await page.goto(guideUrl(FE, "/login") + "&guideRole=team", { waitUntil: "networkidle" });
    await fillLoginSample(page, ACCOUNTS.team.login, "●●●●●●");
    await shot(page, "01_login", { fullPage: true });
    await ctx.close();
  }

  // 02 동의서 (신규 세션 — 동의 모달 캡처 시도)
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.team);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    const modal = page.locator(".fe-sign-modal");
    if (await modal.isVisible().catch(() => false)) {
      await page.locator(".fe-sign-consent-body").evaluate((el) => { el.scrollTop = 0; }).catch(() => {});
      await shot(page, "02_consent_top", { selector: ".fe-sign-modal" });
      await shot(page, "02_consent_scroll_locked", { selector: ".fe-sign-modal" });
      const checkbox = page.locator('.fe-sign-check input[type="checkbox"]');
      const submitBtn = page.getByRole("button", { name: /동의 및 서명/ });
      const locked = (await checkbox.isDisabled()) && (await submitBtn.isDisabled());
      console.log("consent_scroll_gate_locked", locked ? "OK" : "FAIL");
      await page.locator(".fe-sign-consent-body").evaluate((el) => { el.scrollTop = el.scrollHeight; }).catch(() => {});
      await page.waitForTimeout(400);
      await shot(page, "02_consent_bottom", { selector: ".fe-sign-modal" });
      await shot(page, "02_consent_scroll_unlocked", { selector: ".fe-sign-modal" });
      await dismissConsentIfVisible(page);
    } else {
      await shot(page, "02_consent_already_signed_note", { fullPage: true });
    }
    await ctx.close();
  }

  // 03~ 팀장 화면
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.team);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await dismissConsentIfVisible(page);
    await page.waitForTimeout(1500);
    await shot(page, "03_roster_team", { fullPage: true, mask: true });

    await page.goto(guideUrl(FE, "/site/functional-eval/evaluate", { preview: true }) + "&eval_status=incomplete", {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2000);
    await prepareEvaluateScreenshot(page, "functional");
    await shot(page, "04_evaluate_functional", { fullPage: true, mask: true });

    await prepareEvaluateScreenshot(page, "safety");
    await page.waitForTimeout(1500);
    await shot(page, "05_evaluate_safety", { fullPage: true, mask: true });

    // 포상/제재 버튼 영역
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const rewardBtn = page.getByRole("button", { name: "포상", exact: true }).first();
    if (await rewardBtn.isVisible().catch(() => false)) {
      await rewardBtn.click();
      await page.waitForTimeout(800);
      await fillRewardModalSample(page);
      await shot(page, "06_reward_modal", { fullPage: false });
      await page.locator(".dialog-close").first().click({ force: true }).catch(async () => {
        await page.getByRole("button", { name: "취소" }).click({ force: true });
      });
      await page.waitForTimeout(800);
    }
    const sanctionBtn = page.getByRole("button", { name: "제재", exact: true }).first();
    if (await sanctionBtn.isVisible().catch(() => false)) {
      await sanctionBtn.click();
      await page.waitForTimeout(800);
      await fillSanctionModalSample(page);
      await shot(page, "07_sanction_modal", { fullPage: false });
      await page.locator(".fe-overlay-backdrop").click({ force: true }).catch(() => page.keyboard.press("Escape"));
      await page.waitForTimeout(500);
    }
    await ctx.close();
  }

  // 소장
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.manager);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await dismissConsentIfVisible(page);
    await page.waitForTimeout(1500);
    await shot(page, "08_manager_roster", { fullPage: true, mask: true });
    await shot(page, "09_manager_approval_panel", { selector: ".approval-panel" }).catch(() => shot(page, "09_manager_approval_panel", { fullPage: false }));
    await ctx.close();
  }

  // HQ 담당 (계정 없으면 guidePreview 대체)
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    try {
      await login(page, ACCOUNTS.hqOfficer);
      await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
      await dismissConsentIfVisible(page);
      await page.waitForTimeout(2000);
      await shot(page, "10_hq_officer_dashboard", { fullPage: true });
    } catch {
      await page.goto(guideUrl(FE, "/hq-safe/functional-eval", { preview: true }) + "&guideRole=hq", {
        waitUntil: "networkidle",
      });
      await page.waitForTimeout(1500);
      await shot(page, "10_hq_officer_dashboard", { fullPage: true });
    }
    await ctx.close();
  }

  // HQ 실장
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.hq);
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await shot(page, "11_hq_director_dashboard", { fullPage: true });
    await ctx.close();
  }

  // CEO
  {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.ceo);
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await shot(page, "12_ceo_dashboard", { fullPage: true });
    await ctx.close();
  }

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
