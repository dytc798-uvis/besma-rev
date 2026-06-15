/**
 * A4 설명서용 화면 캡처 — UI 요소만 크롭 (오버레이·빨간 원 없음)
 */
import { chromium, devices } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  drawSampleSignature,
  fillLoginSample,
  guideUrl,
  prepareEvaluateScreenshot,
  reloadAfterConsent,
  scrollConsentToBottom,
  shotPage,
} from "./feGuideCaptureHelpers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "..", "..", "docs", "reports", "functional-eval-e2e", "screenshots", "a4-manual");
const FE = process.env.FE_BASE || "https://www.besma.co.kr";
const API =
  process.env.API_BASE ||
  (FE.includes("besma.co.kr") ? "https://api.besma.co.kr" : "http://127.0.0.1:8001");

const ACCOUNTS = {
  site: { login: "대우청라-박명식", password: "661123" },
  hqOfficer: { login: "안전보건-정상익", password: "790808" },
  hq: { login: "안전보건-조동문", password: "600321" },
  ceo: { login: "부현대표-김홍수", password: "611001" },
};

async function loginViaApi(page, { login, password }) {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
    body: new URLSearchParams({ username: login, password }),
  });
  if (!res.ok) throw new Error(`login failed ${login} ${res.status}`);
  const { access_token: token } = await res.json();
  await page.goto(`${FE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((t) => localStorage.setItem("besma_token", t), token);
}

async function login(page, creds) {
  if (FE.includes("besma.co.kr") || process.env.API_BASE) {
    await loginViaApi(page, creds);
    return;
  }
  await page.goto(`${FE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="text"]', creds.login);
  await page.fill('input[type="password"]', creds.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1200);
}

async function shot(page, name, opts = {}) {
  await shotPage(page, name, OUT, opts);
}

async function captureWorkerEvidence(page) {
  const rewardChip = page.locator('button.evidence-chip--reward[title*="김포상"]').first();
  if (await rewardChip.count()) {
    try {
      await rewardChip.scrollIntoViewIfNeeded();
      await rewardChip.click({ force: true });
      await page.waitForSelector(".evidence-modal", { timeout: 12000 });
      await page.waitForTimeout(800);
      await shot(page, "reward_evidence_kimposang", { selector: ".evidence-modal" });
    } catch (e) {
      console.warn("reward_evidence_kimposang failed", e.message);
    }
    await page.keyboard.press("Escape").catch(() => {});
    await page.locator(".evidence-modal-backdrop").click({ force: true }).catch(() => {});
    await page.waitForTimeout(400);
  } else {
    console.warn("skip reward_evidence_kimposang (chip not found)");
  }

  const sanctionChip = page.locator('button.evidence-chip--sanction[title*="김부실"]').first();
  if (await sanctionChip.count()) {
    try {
      await sanctionChip.scrollIntoViewIfNeeded();
      await sanctionChip.click({ force: true });
      await page.waitForSelector(".evidence-modal", { timeout: 12000 });
      await page.waitForTimeout(800);
      await shot(page, "sanction_evidence_kimbusil", { selector: ".evidence-modal" });
    } catch (e) {
      console.warn("sanction_evidence_kimbusil failed", e.message);
    }
    await page.keyboard.press("Escape").catch(() => {});
  } else {
    console.warn("skip sanction_evidence_kimbusil (chip not found)");
  }
}

async function captureConsentModal(page) {
  await page.goto(guideUrl(FE, "/site/functional-eval", { preview: true, scene: "consent" }), {
    waitUntil: "networkidle",
  });
  await page.waitForSelector(".fe-sign-modal", { timeout: 30000 });
  await scrollConsentToBottom(page);
  await page.locator('.fe-sign-check input[type="checkbox"]').check().catch(() => {});
  await drawSampleSignature(page);
  await shot(page, "consent_modal", { selector: ".fe-sign-modal" });
}

async function safeStep(label, fn) {
  try {
    await fn();
  } catch (e) {
    console.warn(`skip ${label}:`, e.message);
  }
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const mobile = devices["iPhone 13"];

  // 로그인 — 폼(.card)만 (guidePreview 샘플 입력)
  for (const [key, acc] of Object.entries({
    team: { login: "대우청라-김팀장", mobile: true },
    manager: { login: "대우청라-박명식", mobile: false },
    hq: { login: "안전보건-조동문", mobile: false },
    ceo: { login: "부현대표-김홍수", mobile: false },
  })) {
    await safeStep(`login_${key}`, async () => {
      const ctx = await browser.newContext(
        acc.mobile ? { ...mobile, locale: "ko-KR" } : { viewport: { width: 900, height: 700 }, locale: "ko-KR" },
      );
      const page = await ctx.newPage();
      await page.goto(guideUrl(FE, "/login", { preview: true }) + `&guideRole=${key}`, { waitUntil: "networkidle" });
      await fillLoginSample(page, acc.login, "●●●●●●");
      await shot(page, `login_${key}`, { selector: ".card" });
      await ctx.close();
    });
  }

  // 동의서 (guideScene=consent — 배포 후 동작, 실패 시 기존 파일 유지)
  await safeStep("consent_modal", async () => {
    const ctx = await browser.newContext({ ...mobile, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.site);
    await captureConsentModal(page);
    await ctx.close();
  });

  // 모바일 평가 바텀시트
  await safeStep("team_evaluate_mobile", async () => {
    const ctx = await browser.newContext({ ...mobile, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.site);
    await page.goto(guideUrl(FE, "/site/functional-eval/evaluate", { preview: true }), { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await prepareEvaluateScreenshot(page, "functional");
    const selector = (await page.locator(".fe-sheet").count()) ? ".fe-sheet" : ".eval-panel";
    await shot(page, "team_evaluate_mobile", { selector });
    await ctx.close();
  });

  // 포상 업로드 · 근거
  await safeStep("reward_flow", async () => {
    const ctx = await browser.newContext({ ...mobile, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.site);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/site/functional-eval", { preview: true, scene: "reward-upload" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1200);
    if (await page.locator('.fe-dialog:has(h2:text-matches("포상"))').count()) {
      await shot(page, "reward_upload_modal", { selector: '.fe-dialog:has(h2:text-matches("포상"))' });
    }
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await captureWorkerEvidence(page);
    await ctx.close();
  });

  // 평가완료보고서 서명 모달
  await safeStep("team_signoff_modal", async () => {
    const ctx = await browser.newContext({ ...mobile, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.site);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/site/functional-eval", { preview: true, scene: "team-signoff" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2000);
    await scrollConsentToBottom(page).catch(() => {});
    await drawSampleSignature(page);
    await page.waitForSelector(".fe-sign-modal", { timeout: 20000 });
    await shot(page, "team_signoff_modal", { selector: ".fe-sign-modal" });
    await ctx.close();
  });

  // 소장
  await safeStep("manager_flow", async () => {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.site);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    const rosterSel = (await page.locator(".roster-table-wrap").count())
      ? ".roster-table-wrap"
      : ".roster-panel";
    await shot(page, "manager_roster", { selector: rosterSel });
    if (await page.locator(".approval-panel").count()) {
      await shot(page, "manager_approval", { selector: ".approval-panel" });
    }
    await ctx.close();
  });

  // 본사 검토
  await safeStep("hq_dashboard", async () => {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.hqOfficer);
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.waitForTimeout(1500);
    await shot(page, "hq_dashboard", { selector: ".hq-review-panel" });
    await ctx.close();
  });

  // 실장 승인
  await safeStep("hq_director_approval", async () => {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.hq);
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/hq-safe/functional-eval", { preview: true, scene: "director-approval" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2000);
    await shot(page, "hq_director_approval", { selector: '.approval-collapse:has-text("실장 최종승인")' });
    await ctx.close();
  });

  // 대표 승인
  await safeStep("ceo_approval", async () => {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, ACCOUNTS.ceo);
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/hq-safe/functional-eval", { preview: true, scene: "ceo-approval" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2000);
    await shot(page, "ceo_approval", { selector: '.approval-collapse:has-text("대표이사 최종 승인")' });
    await ctx.close();
  });

  await browser.close();
  console.log("Done →", OUT);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
