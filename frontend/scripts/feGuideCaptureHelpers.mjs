/**
 * 설명서 캡처 공통 — 빈 입력란을 샘플로 채운 뒤 스크린샷
 */

export function guideUrl(base, path, { preview = true, scene = null } = {}) {
  const sep = path.includes("?") ? "&" : "?";
  let url = `${base}${path}`;
  const params = [];
  if (preview) params.push("guidePreview=1");
  if (scene) params.push(`guideScene=${encodeURIComponent(scene)}`);
  if (params.length) url += `${sep}${params.join("&")}`;
  return url;
}

export async function reloadAfterConsent(page) {
  const modal = page.locator(".fe-sign-modal, .fe-sign-overlay");
  if (!(await modal.first().isVisible().catch(() => false))) return;
  await page.locator('.fe-sign-check input[type="checkbox"]').check().catch(() => {});
  await drawSampleSignature(page);
  await page.getByRole("button", { name: /동의 및 서명|서명 완료/ }).click().catch(() => {});
  await page.waitForTimeout(1200);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
}

export async function fillLoginSample(page, loginId, password) {
  await page.fill('input[type="text"]', loginId);
  await page.fill('input[type="password"]', password);
}

export async function drawSampleSignature(page) {
  const canvas = page.locator("canvas").first();
  if (!(await canvas.count())) return;
  const box = await canvas.boundingBox();
  if (!box) return;
  await page.mouse.move(box.x + 30, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 30, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
}

export async function dismissConsent(page) {
  const modal = page.locator(".fe-sign-modal");
  if (!(await modal.isVisible().catch(() => false))) return;
  await page.locator('.fe-sign-check input[type="checkbox"]').check().catch(() => {});
  await drawSampleSignature(page);
  await page.getByRole("button", { name: /동의 및 서명|서명 완료/ }).click().catch(() => {});
  await page.waitForTimeout(1000);
}

/** 평가 화면 — guidePreview=1 로 샘플 등급 표시 후 캡처 */
export async function prepareEvaluateScreenshot(page, evalType = "functional") {
  await page.waitForTimeout(1200);
  const railItem = page.locator(".rail-item, .roster-item").first();
  if (await railItem.count()) {
    await railItem.click().catch(() => {});
    await page.waitForTimeout(800);
  }
  if (evalType === "safety") {
    await page.getByRole("button", { name: /2-2|안전/ }).first().click().catch(() => {});
    await page.waitForTimeout(600);
  }
}

export async function fillRewardModalSample(page) {
  const note = page.locator('.reward-form textarea, textarea[placeholder*="메모"], textarea').first();
  if (await note.count()) {
    await note.fill("고객사 포상 — 설명서 샘플 (실제 제출 아님)");
  }
}

export async function fillSanctionModalSample(page) {
  const select = page.locator('select, [role="combobox"]').first();
  if (await select.count()) {
    await select.selectOption({ index: 1 }).catch(() => {});
  }
  const note = page.locator('textarea').first();
  if (await note.count()) {
    await note.fill("제재 근거 — 설명서 샘플 (실제 등록 아님)");
  }
  await drawSampleSignature(page);
}

/** 캡처 직전 강조 오버레이 (빨간 원 + 주변 흐림) */
export async function applyCaptureHighlight(page, highlight) {
  if (!highlight) return;
  await page.evaluate(({ cx, cy, r }) => {
    const old = document.getElementById("guide-capture-highlight");
    old?.remove();
    const wrap = document.createElement("div");
    wrap.id = "guide-capture-highlight";
    wrap.style.cssText =
      "position:fixed;inset:0;z-index:99999;pointer-events:none;" +
      `-webkit-mask-image:radial-gradient(circle at ${cx}% ${cy}%, transparent 0, transparent ${r}%, #000 calc(${r}% + 1px));` +
      `mask-image:radial-gradient(circle at ${cx}% ${cy}%, transparent 0, transparent ${r}%, #000 calc(${r}% + 1px));` +
      "background:rgba(15,23,42,0.52);";
    const ring = document.createElement("div");
    ring.id = "guide-capture-highlight-ring";
    ring.style.cssText =
      `position:fixed;left:calc(${cx}% - ${r}%);top:calc(${cy}% - ${r}%);` +
      `width:calc(${r * 2}%);height:calc(${r * 2}%);` +
      "border:3px solid #ef4444;border-radius:50%;box-shadow:0 0 0 2px rgba(255,255,255,0.9);pointer-events:none;z-index:100000;";
    document.body.appendChild(wrap);
    document.body.appendChild(ring);
  }, highlight);
}

export async function clearCaptureHighlight(page) {
  await page.evaluate(() => {
    document.getElementById("guide-capture-highlight")?.remove();
    document.getElementById("guide-capture-highlight-ring")?.remove();
  });
}

export async function shotWithHighlight(page, name, outDir, opts = {}) {
  const out = `${outDir}/${name}.png`;
  if (opts.highlight) await applyCaptureHighlight(page, opts.highlight);
  try {
    if (opts.selector) {
      await page.locator(opts.selector).first().screenshot({ path: out });
    } else {
      await page.screenshot({ path: out, fullPage: Boolean(opts.fullPage) });
    }
    console.log("ok", name);
  } finally {
    await clearCaptureHighlight(page);
  }
}

/** 포상 업로드 창 캡처 (모바일) */
export async function captureRewardUploadModal(page, outDir, shotFn) {
  const rewardBtn = page.locator('button.stitch-btn-secondary, button').filter({ hasText: /^포상$/ }).first();
  if (!(await rewardBtn.count())) {
    console.warn("skip reward_upload_modal (포상 button not found)");
    return;
  }
  await rewardBtn.scrollIntoViewIfNeeded();
  await rewardBtn.click({ force: true });
  await page.waitForTimeout(900);
  const dialog = page.locator('.fe-dialog:has(h2:has-text("포상"))').first();
  if (!(await dialog.count())) {
    console.warn("skip reward_upload_modal (dialog not found)");
    await page.keyboard.press("Escape").catch(() => {});
    return;
  }
  await shotFn(page, "reward_upload_modal", { selector: ".fe-dialog:has(h2:has-text('포상'))", highlight: { cx: 50, cy: 58, r: 24 } });
  await page.keyboard.press("Escape").catch(() => {});
  await page.locator(".fe-overlay-backdrop").click({ force: true }).catch(() => {});
  await page.waitForTimeout(400);
}

/** HQ 실장/대표 승인 패널 펼친 뒤 캡처 */
export async function expandHqApprovalSection(page, titlePattern) {
  const section = page.locator(".approval-collapse").filter({ hasText: titlePattern }).first();
  if (!(await section.count())) return null;
  const toggle = section.locator(".approval-collapse__toggle");
  const expanded = await toggle.getAttribute("aria-expanded");
  if (expanded !== "true") {
    await toggle.click();
    await page.waitForTimeout(600);
  }
  return section;
}
