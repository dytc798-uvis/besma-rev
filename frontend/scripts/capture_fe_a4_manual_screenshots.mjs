/**
 * A4 설명서용 화면 캡처 (강조 오버레이 포함)
 */
import { chromium, devices } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  dismissConsent,
  drawSampleSignature,
  fillLoginSample,
  guideUrl,
  prepareEvaluateScreenshot,
  reloadAfterConsent,
  shotWithHighlight,
} from "./feGuideCaptureHelpers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "..", "..", "docs", "reports", "functional-eval-e2e", "screenshots", "a4-manual");
const FE = process.env.FE_BASE || "http://127.0.0.1:5174";

async function login(page, loginId, password) {
  await page.goto(`${FE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="text"]', loginId);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);
}

async function shot(page, name, opts = {}) {
  await shotWithHighlight(page, name, OUT, opts);
}

async function captureWorkerEvidence(page) {
  const rewardChip = page.locator('button.evidence-chip--reward[title*="김포상"]').first();
  if (await rewardChip.count()) {
    try {
      await rewardChip.scrollIntoViewIfNeeded();
      await rewardChip.click({ force: true });
      await page.waitForSelector(".evidence-modal", { timeout: 12000 });
      await page.waitForTimeout(1200);
      await shot(page, "reward_evidence_kimposang", {
        selector: ".evidence-modal",
        highlight: { cx: 50, cy: 42, r: 28 },
      });
    } catch (e) {
      console.warn("reward_evidence_kimposang failed", e.message);
    }
    await page.keyboard.press("Escape").catch(() => {});
    await page.locator(".evidence-modal-backdrop").click({ force: true }).catch(() => {});
    await page.waitForTimeout(600);
  } else {
    console.warn("skip reward_evidence_kimposang (chip not found)");
  }

  const sanctionChip = page.locator('button.evidence-chip--sanction[title*="김부실"]').first();
  if (await sanctionChip.count()) {
    try {
      await sanctionChip.scrollIntoViewIfNeeded();
      await sanctionChip.click({ force: true });
      await page.waitForSelector(".evidence-modal", { timeout: 12000 });
      await page.waitForTimeout(1200);
      await shot(page, "sanction_evidence_kimbusil", {
        selector: ".evidence-modal",
        highlight: { cx: 50, cy: 45, r: 26 },
      });
    } catch (e) {
      console.warn("sanction_evidence_kimbusil failed", e.message);
    }
    await page.keyboard.press("Escape").catch(() => {});
  } else {
    console.warn("skip sanction_evidence_kimbusil (chip not found)");
  }
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  for (const [key, acc] of Object.entries({
    team: { login: "대우청라-김팀장", password: "750101" },
    manager: { login: "대우청라-박명식", password: "661123" },
    hq: { login: "안전보건-조동문", password: "600321" },
    ceo: { login: "부현대표-김홍수", password: "611001" },
  })) {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 1754 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await page.goto(guideUrl(FE, "/login", { preview: true }) + `&guideRole=${key}`, { waitUntil: "networkidle" });
    await fillLoginSample(page, acc.login, "●●●●●●");
    await shot(page, `login_${key}`, { highlight: { cx: 50, cy: 72, r: 14 } });
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "대우청라-김팀장", "750101");
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    if (await page.locator(".fe-sign-modal").isVisible().catch(() => false)) {
      await page.locator('.fe-sign-check input[type="checkbox"]').check().catch(() => {});
      await drawSampleSignature(page);
      await shot(page, "consent_modal", { selector: ".fe-sign-modal", highlight: { cx: 50, cy: 88, r: 12 } });
      await dismissConsent(page);
    }
    await ctx.close();
  }

  {
    const mobile = devices["iPhone 13"];
    const ctx = await browser.newContext({ ...mobile, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "대우청라-김팀장", "750101");
    await page.goto(guideUrl(FE, "/site/functional-eval/evaluate", { preview: true }), { waitUntil: "networkidle" });
    await dismissConsent(page);
    await page.waitForTimeout(1500);
    await prepareEvaluateScreenshot(page, "functional");
    await shot(page, "team_evaluate_mobile", { fullPage: true, highlight: { cx: 50, cy: 48, r: 22 } });
    await ctx.close();
  }

  {
    const mobile = devices["iPhone 13"];
    const ctx = await browser.newContext({ ...mobile, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "대우청라-김팀장", "750101");
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/site/functional-eval", { preview: true, scene: "reward-upload" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1500);
    const rewardDialog = page.locator('.fe-dialog:has(h2:text-matches("포상"))');
    if (await rewardDialog.count()) {
      await shot(page, "reward_upload_modal", {
        selector: '.fe-dialog:has(h2:text-matches("포상"))',
        highlight: { cx: 50, cy: 58, r: 24 },
      });
    } else {
      console.warn("skip reward_upload_modal");
    }
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await captureWorkerEvidence(page);
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "대우청라-김팀장", "750101");
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await dismissConsent(page);
    await page.waitForTimeout(1000);
    const signBtn = page.getByRole("button", { name: "평가완료보고서 서명" });
    if (await signBtn.isVisible().catch(() => false)) {
      await signBtn.click();
      await page.waitForTimeout(800);
      await drawSampleSignature(page);
      await shot(page, "team_signoff_modal", { selector: ".fe-sign-modal", highlight: { cx: 50, cy: 86, r: 11 } });
    } else {
      console.warn("skip team_signoff_modal (button not visible)");
    }
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "대우청라-박명식", "661123");
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.waitForTimeout(1500);
    await shot(page, "manager_roster", { fullPage: true, highlight: { cx: 50, cy: 35, r: 20 } });
    await page.goto(guideUrl(FE, "/site/functional-eval", { preview: true, scene: "reward-upload" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1500);
    if (await page.locator('.fe-dialog:has(h2:text-matches("포상"))').count()) {
      await shot(page, "reward_upload_modal", {
        selector: '.fe-dialog:has(h2:text-matches("포상"))',
        highlight: { cx: 50, cy: 58, r: 24 },
      });
    }
    await captureWorkerEvidence(page);
    await page.goto(`${FE}/site/functional-eval`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await shot(page, "manager_approval", { selector: ".approval-panel", highlight: { cx: 50, cy: 78, r: 14 } }).catch(() => {});
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "안전보건-정상익", "790808");
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await dismissConsent(page);
    await page.waitForTimeout(2000);
    await page.locator(".hq-review-panel").scrollIntoViewIfNeeded().catch(() => {});
    await shot(page, "hq_dashboard", { selector: ".hq-review-panel", highlight: { cx: 50, cy: 28, r: 18 } });
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "안전보건-조동문", "600321");
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/hq-safe/functional-eval", { preview: true, scene: "director-approval" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2500);
    await page.locator(".hq-review-panel").scrollIntoViewIfNeeded().catch(() => {});
    const directorPanel = page.locator('.approval-collapse:has-text("실장 최종승인")');
    if (await directorPanel.count()) {
      await shot(page, "hq_director_approval", {
        selector: '.approval-collapse:has-text("실장 최종승인")',
        highlight: { cx: 72, cy: 38, r: 14 },
      });
    } else {
      console.warn("skip hq_director_approval");
    }
    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 1240, height: 900 }, locale: "ko-KR" });
    const page = await ctx.newPage();
    await login(page, "부현대표-김홍수", "611001");
    await page.goto(`${FE}/hq-safe/functional-eval`, { waitUntil: "networkidle" });
    await reloadAfterConsent(page);
    await page.goto(guideUrl(FE, "/hq-safe/functional-eval", { preview: true, scene: "ceo-approval" }), {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2500);
    await page.locator(".hq-review-panel").scrollIntoViewIfNeeded().catch(() => {});
    const ceoPanel = page.locator('.approval-collapse:has-text("대표이사 최종 승인")');
    if (await ceoPanel.count()) {
      await shot(page, "ceo_approval", {
        selector: '.approval-collapse:has-text("대표이사 최종 승인")',
        highlight: { cx: 68, cy: 32, r: 16 },
      });
    } else {
      console.warn("skip ceo_approval");
    }
    await ctx.close();
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
