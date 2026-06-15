<template>
  <div class="guide-page" :class="{ 'guide-page--mobile': isMobileViewport }">
    <!-- 모바일: 동의서(1번)부터 텍스트 단계 안내 -->
    <section v-if="isMobileViewport" class="guide-mobile">
      <header class="guide-mobile-head">
        <h1>기능인인정제 설명</h1>
        <p v-if="mobileRoleLabel" class="guide-mobile-role">{{ mobileRoleLabel }} 안내</p>
      </header>

      <p v-if="loadError" class="guide-error" role="alert">{{ loadError }}</p>
      <p v-else-if="loading" class="guide-loading" role="status">안내 불러오는 중…</p>

      <template v-else>
        <p v-if="mobileIntro" class="guide-mobile-intro">{{ mobileIntro }}</p>

        <article
          v-for="step in mobileTextSteps"
          :key="step.title"
          class="guide-mobile-step"
        >
          <h2 class="guide-mobile-step-title">{{ step.title }}</h2>
          <ul class="guide-mobile-step-list">
            <li v-for="(line, lineIdx) in step.lines" :key="lineIdx">{{ line }}</li>
          </ul>
        </article>

        <div v-if="showPdfDownloads" class="pdf-panel pdf-panel--mobile">
          <h3>역할별 A4 PDF</h3>
          <ul class="pdf-list">
            <li v-for="pdf in pdfDownloads" :key="pdf.href">
              <a :href="pdf.href" target="_blank" rel="noopener noreferrer">{{ pdf.label }}</a>
            </li>
          </ul>
        </div>
      </template>
    </section>

    <!-- PC·태블릿: 기존 메뉴 + 슬라이드 -->
    <template v-else>
      <aside class="guide-menu">
        <h2>기능인인정제 설명</h2>
        <button
          v-for="section in sections"
          :key="section.title"
          class="menu-btn"
          :class="{ active: section.title === selectedTitle }"
          @click="selectedTitle = section.title"
        >
          {{ section.title }}
        </button>
      </aside>
      <section class="guide-content">
        <h1>{{ currentSection?.title || "기능인인정제 설명" }}</h1>

        <p v-if="loadError" class="guide-error" role="alert">{{ loadError }}</p>
        <p v-else-if="loading" class="guide-loading" role="status">안내 불러오는 중…</p>

        <template v-else>
          <div v-if="showPdfDownloads" class="pdf-panel">
            <h3>역할별 A4 PDF</h3>
            <ul class="pdf-list">
              <li v-for="pdf in pdfDownloads" :key="pdf.href">
                <a :href="pdf.href" target="_blank" rel="noopener noreferrer">{{ pdf.label }}</a>
              </li>
            </ul>
          </div>

          <div v-if="!roleSlides.length" class="content-box" v-html="renderedBody" />
          <div v-else class="content-box content-box--intro" v-html="renderedIntro" />

          <div v-if="roleSlides.length" class="guide-slides">
            <article v-for="(slide, idx) in roleSlides" :key="`${slide.title}-${idx}`" class="guide-slide">
              <h3 class="guide-slide-title">{{ stripMarkdownEmphasis(slide.title) }}</h3>
              <div class="guide-slide-body">
                <ul class="guide-slide-bullets">
                  <li v-for="(line, lineIdx) in slide.bullets" :key="lineIdx">{{ stripMarkdownEmphasis(line) }}</li>
                </ul>
                <div v-if="slide.images?.length" class="guide-slide-images" :class="`layout-${slide.layout || 'single'}`">
                  <figure
                    v-for="image in normalizeSlideImages(slide.images)"
                    :key="image.src"
                    class="guide-slide-figure"
                    :class="{ 'guide-slide-figure--phone': image.phoneFrame }"
                  >
                    <figcaption v-if="image.label" class="guide-slide-caption">{{ image.label }}</figcaption>
                    <div class="guide-shot-shell" :class="{ 'guide-phone-shell': image.phoneFrame }">
                      <img
                        v-if="!failedImageMap[image.src]"
                        :src="image.src"
                        :alt="image.label || slide.title"
                        class="guide-slide-image"
                        loading="lazy"
                        @error="markImageFailed(image.src)"
                      />
                      <div v-else class="shot-placeholder guide-slide-placeholder">
                        <strong>캡처 준비 중</strong>
                        <span>{{ image.src.split("/").pop() }}</span>
                      </div>
                    </div>
                  </figure>
                </div>
              </div>
            </article>
          </div>

          <div v-if="canManageGuideShots" class="upload-panel">
            <h3>화면 예시 업로드</h3>
            <div class="upload-row">
              <input v-model="uploadLabel" type="text" class="upload-input" placeholder="이미지 설명(선택)" />
              <input type="file" accept="image/*" @change="onUploadFileChange" />
              <button class="menu-btn" :disabled="!uploadFile || uploadLoading" @click="uploadShot">
                {{ uploadLoading ? "업로드 중..." : "이미지 업로드" }}
              </button>
            </div>
            <p class="upload-hint">업로드 시 서버에서 크기를 줄이고 JPEG로 변환해 저장합니다.</p>
            <p v-if="uploadMessage" class="upload-message">{{ uploadMessage }}</p>
          </div>

          <div v-if="currentShots.length" class="shot-wrap">
            <h3>화면 예시</h3>
            <div class="shot-grid">
              <article v-for="shot in currentShots" :key="shot.src" class="shot-card">
                <p class="shot-title">{{ shot.label }}</p>
                <img
                  v-if="!failedImageMap[shot.src]"
                  :src="shot.src"
                  :alt="shot.label"
                  class="shot-image"
                  @error="markImageFailed(shot.src)"
                />
                <div v-else class="shot-placeholder">
                  <strong>스크린샷 준비중</strong>
                </div>
              </article>
            </div>
          </div>
        </template>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { useFeSiteSessionStore } from "@/stores/feSiteSession";
import { useMobileViewport } from "@/composables/useMobileViewport";
import {
  FE_GUIDE_SLIDES,
  normalizeGuideImages,
  type FeGuideImage,
} from "@/config/feGuideSlides";

interface GuideSection {
  title: string;
  body: string;
}

interface MobileTextStep {
  title: string;
  lines: string[];
}

const GUIDE_PATH = "/FE_FUNCTIONAL_EVAL_GUIDE.md";

const pdfDownloads = [
  { href: "/fe-guide/기능인인정제_팀장용_운영설명서.pdf", label: "팀장용 운영설명서 (PDF)" },
  { href: "/fe-guide/기능인인정제_소장용_운영설명서.pdf", label: "소장용 운영설명서 (PDF)" },
  { href: "/fe-guide/기능인인정제_본사대표용_운영설명서.pdf", label: "본사·대표님용 운영설명서 (PDF)" },
];

const sections = ref<GuideSection[]>([]);
const selectedTitle = ref("");
const failedImageMap = ref<Record<string, boolean>>({});
const uploadedShotsMap = ref<Record<string, Array<{ src: string; label: string; guide: string }>>>({});
const uploadLabel = ref("");
const uploadFile = ref<File | null>(null);
const uploadLoading = ref(false);
const uploadMessage = ref("");
const loading = ref(true);
const loadError = ref("");
const auth = useAuthStore();
const feSiteSession = useFeSiteSessionStore();
const { isMobileViewport } = useMobileViewport();

const canManageGuideShots = computed(
  () => (auth.user?.login_id || "").trim().toLowerCase() === "hq01",
);

const currentSection = computed(() => sections.value.find((s) => s.title === selectedTitle.value) ?? sections.value[0]);

const roleSlides = computed(() => {
  const title = currentSection.value?.title || "";
  return FE_GUIDE_SLIDES[title] ?? [];
});

const showPdfDownloads = computed(() => currentSection.value?.title === "PDF 다운로드");

const currentShots = computed(() => {
  const title = currentSection.value?.title || "";
  return uploadedShotsMap.value[title] || [];
});

const mobileRoleLabel = computed(() => {
  const title = currentSection.value?.title || "";
  if (title.includes("팀장")) return "팀장";
  if (title.includes("소장")) return "소장";
  if (title.includes("본사")) return "본사·대표";
  return title;
});

const mobileIntro = computed(() => {
  const body = currentSection.value?.body || "";
  const intro = body.split(/^### /m)[0].trim();
  const firstLine = intro
    .split(/\r?\n/)
    .map((line) => stripMarkdownEmphasis(line.trim()))
    .find((line) => line && !line.startsWith("#"));
  return firstLine || "";
});

const mobileTextSteps = computed((): MobileTextStep[] => {
  const body = currentSection.value?.body || "";
  const blocks = body.split(/^### /m).slice(1);
  const parsed = blocks
    .map((block) => {
      const lines = block.split(/\r?\n/);
      const rawTitle = stripMarkdownEmphasis((lines[0] || "").trim());
      const bullets = lines
        .slice(1)
        .map((line) => line.trim())
        .filter((line) => line.startsWith("- "))
        .map((line) => stripMarkdownEmphasis(line.slice(2).trim()));
      return { rawTitle, lines: bullets };
    })
    .filter((step) => step.rawTitle && !/로그인/i.test(step.rawTitle));

  return parsed.map((step, index) => {
    const plainTitle = step.rawTitle.replace(/^\d+\.\s*/, "");
    return {
      title: `${index + 1}. ${plainTitle}`,
      lines: step.lines,
    };
  });
});

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function stripMarkdownEmphasis(text: string) {
  return text.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1");
}

function formatGuideBody(body: string) {
  const lines = body.split(/\r?\n/);
  const html: string[] = [];
  for (const line of lines) {
    const trimmed = stripMarkdownEmphasis(line.trim());
    if (!trimmed) {
      html.push("<br />");
      continue;
    }
    if (trimmed.startsWith("### ")) {
      html.push(`<h3 class="guide-h3">${escapeHtml(trimmed.slice(4))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("- ")) {
      html.push(`<p class="guide-li">• ${escapeHtml(trimmed.slice(2))}</p>`);
      continue;
    }
    const withLinks = escapeHtml(trimmed).replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    );
    html.push(`<p class="guide-p">${withLinks}</p>`);
  }
  return html.join("\n");
}

function normalizeSlideImages(images?: FeGuideImage[]) {
  return normalizeGuideImages(images);
}

const renderedBody = computed(() => formatGuideBody(currentSection.value?.body || ""));

const renderedIntro = computed(() => {
  const body = currentSection.value?.body || "";
  const intro = body.split(/^### /m)[0].trim();
  return formatGuideBody(intro);
});

function defaultSectionTitle(all: GuideSection[]) {
  const ui = auth.user?.ui_type;
  if (ui === "HQ_SAFE") {
    return all.find((s) => s.title.includes("본사"))?.title ?? all[0]?.title ?? "";
  }
  if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
    if (feSiteSession.isTeamLeader) {
      return all.find((s) => s.title.includes("팀장"))?.title ?? all[0]?.title ?? "";
    }
    return all.find((s) => s.title.includes("소장"))?.title
      ?? all.find((s) => s.title.includes("팀장"))?.title
      ?? all[0]?.title
      ?? "";
  }
  return all[0]?.title ?? "";
}

function markImageFailed(src: string) {
  failedImageMap.value = { ...failedImageMap.value, [src]: true };
}

function resolveShotUrl(path: string) {
  if (!path.startsWith("/")) return path;
  return `${api.defaults.baseURL}${path}`;
}

function onUploadFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  uploadFile.value = target.files?.[0] ?? null;
}

async function loadUploadedShots(sectionTitle: string) {
  try {
    const res = await api.get("/user-guide-shots/list", { params: { section: sectionTitle } });
    const items = (res.data?.items ?? []).map((item: { src: string; label: string }) => ({
      src: resolveShotUrl(item.src),
      label: item.label || "업로드 이미지",
      guide: "사용자 업로드 이미지",
    }));
    uploadedShotsMap.value = { ...uploadedShotsMap.value, [sectionTitle]: items };
  } catch {
    uploadedShotsMap.value = { ...uploadedShotsMap.value, [sectionTitle]: [] };
  }
}

async function uploadShot() {
  const sectionTitle = currentSection.value?.title || "";
  if (!sectionTitle || !uploadFile.value) return;
  uploadLoading.value = true;
  uploadMessage.value = "";
  try {
    const form = new FormData();
    form.append("section", sectionTitle);
    if (uploadLabel.value.trim()) form.append("label", uploadLabel.value.trim());
    form.append("file", uploadFile.value);
    await api.post("/settings/document-cycles/user-guide-shots/upload", form);
    uploadMessage.value = "업로드 완료";
    uploadFile.value = null;
    uploadLabel.value = "";
    await loadUploadedShots(sectionTitle);
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    uploadMessage.value = detail || "업로드 실패";
  } finally {
    uploadLoading.value = false;
  }
}

function parseSections(markdown: string): GuideSection[] {
  const lines = markdown.split(/\r?\n/);
  const out: GuideSection[] = [];
  let currentTitle = "";
  let bodyLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("## ")) {
      if (currentTitle) {
        out.push({ title: currentTitle, body: bodyLines.join("\n").trim() });
      }
      currentTitle = line.replace(/^##\s+/, "").trim();
      bodyLines = [];
    } else if (currentTitle) {
      bodyLines.push(line);
    }
  }
  if (currentTitle) {
    out.push({ title: currentTitle, body: bodyLines.join("\n").trim() });
  }
  return out;
}

async function loadGuide() {
  loading.value = true;
  loadError.value = "";
  try {
    if (!auth.user) {
      await auth.loadMe();
    }
    const loginId = (auth.user?.login_id || "").trim();
    if (loginId && !feSiteSession.navHydrated) {
      feSiteSession.hydrateNavFromCache(loginId);
    }
    const res = await fetch(GUIDE_PATH, { cache: "no-cache" });
    if (!res.ok) {
      throw new Error(`안내 문서를 불러오지 못했습니다. (${res.status})`);
    }
    const text = await res.text();
    sections.value = parseSections(text);
    selectedTitle.value = defaultSectionTitle(sections.value);
    if (selectedTitle.value) {
      await loadUploadedShots(selectedTitle.value);
    }
  } catch (error: unknown) {
    loadError.value = error instanceof Error ? error.message : "안내를 불러오지 못했습니다.";
    sections.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadGuide();
});

watch(selectedTitle, (title) => {
  if (!title) return;
  void loadUploadedShots(title);
});
</script>

<style scoped>
.guide-page { display: grid; grid-template-columns: 260px 1fr; gap: 14px; }
.guide-page--mobile { display: block; }
.guide-menu { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:12px; display:grid; gap:8px; max-height:75vh; overflow:auto; }
.guide-menu h2 { margin:0 0 4px; font-size:16px; }
.menu-btn { text-align:left; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; background:#fff; cursor:pointer; }
.menu-btn.active { background:#eff6ff; border-color:#93c5fd; color:#1d4ed8; font-weight:600; }
.guide-content { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:16px; }
.guide-content h1 { margin:0 0 10px; font-size:20px; }
.guide-loading,
.guide-error { margin: 0 0 12px; font-size: 14px; }
.guide-error { color: #b91c1c; }
.guide-loading { color: #64748b; }
.content-box { line-height:1.7; color:#1f2937; }
.content-box--intro { margin-bottom: 8px; }
.guide-slides { display: flex; flex-direction: column; gap: 20px; margin-top: 12px; }
.guide-slide { padding-bottom: 18px; border-bottom: 1px solid #e2e8f0; }
.guide-slide:last-child { border-bottom: none; }
.guide-slide-title { margin: 0 0 10px; font-size: 17px; font-weight: 700; color: #1e3a5f; }
.guide-slide-body { display: grid; grid-template-columns: minmax(240px, 5fr) minmax(280px, 7fr); gap: 16px; align-items: start; }
.guide-slide-bullets { margin: 0; padding-left: 18px; line-height: 1.65; color: #1f2937; font-size: 14px; }
.guide-slide-bullets li { margin-bottom: 6px; }
.guide-slide-images { display: flex; gap: 8px; flex-wrap: wrap; }
.guide-slide-images.layout-single .guide-slide-figure { flex: 1 1 100%; }
.guide-slide-images.layout-dual .guide-slide-figure { flex: 1 1 calc(50% - 4px); }
.guide-slide-images.layout-triple .guide-slide-figure:first-child { flex: 1 1 100%; max-width: 100%; }
.guide-slide-images.layout-triple .guide-slide-figure:not(:first-child) { flex: 1 1 calc(50% - 4px); }
.guide-slide-images.layout-phone-reward { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-start; }
.guide-slide-images.layout-phone-reward .guide-slide-figure:first-child { flex: 1 1 100%; max-width: 100%; }
.guide-slide-images.layout-phone-reward .guide-slide-figure:not(:first-child) { flex: 1 1 calc(50% - 6px); min-width: 200px; }
.guide-slide-caption { margin: 0 0 6px; font-size: 12px; font-weight: 700; color: #475569; text-align: center; }
.guide-shot-shell { width: 100%; }
.guide-phone-shell {
  max-width: 300px;
  margin: 0 auto;
  padding: 16px 10px 20px;
  border-radius: 32px;
  border: 3px solid #1e293b;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  box-shadow: 0 10px 28px rgb(15 23 42 / 22%);
}
.guide-phone-shell::before {
  content: "";
  display: block;
  width: 38%;
  height: 5px;
  margin: 0 auto 10px;
  border-radius: 999px;
  background: #475569;
}
.guide-phone-shell .guide-slide-image { border: none; border-radius: 14px; }
.guide-slide-image {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
}
.guide-slide-images.layout-single .guide-slide-image {
  max-width: 420px;
  margin: 0 auto;
  display: block;
}
.guide-slide-placeholder { min-height: 140px; }
@media (max-width: 960px) {
  .guide-slide-body { grid-template-columns: 1fr; }
}
.content-box :deep(.guide-h3) { margin:16px 0 8px; font-size:15px; font-weight:700; color:#0f172a; }
.content-box :deep(.guide-p) { margin:0 0 8px; }
.content-box :deep(.guide-li) { margin:0 0 6px; padding-left:4px; }
.content-box :deep(a) { color:#2563eb; text-decoration:underline; }
.pdf-panel { margin-bottom:14px; padding:12px; border:1px solid #dbeafe; border-radius:10px; background:#f8fafc; }
.pdf-panel h3 { margin:0 0 8px; font-size:15px; }
.pdf-list { margin:0; padding-left:20px; }
.pdf-list li { margin-bottom:6px; }
.pdf-list a { color:#2563eb; font-weight:600; }
.upload-panel { margin-top: 14px; padding: 10px; border:1px solid #e2e8f0; border-radius:10px; background:#f8fafc; }
.upload-panel h3 { margin:0 0 8px; font-size: 15px; }
.upload-row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.upload-input { min-width: 220px; border:1px solid #cbd5e1; border-radius:8px; padding:8px 10px; }
.upload-hint { margin:8px 0 0; font-size:12px; color:#64748b; }
.upload-message { margin:8px 0 0; font-size:12px; color:#b91c1c; }
.shot-wrap { margin-top: 16px; }
.shot-wrap h3 { margin: 0 0 8px; font-size: 16px; }
.shot-grid { display:grid; grid-template-columns: repeat(auto-fill,minmax(240px,1fr)); gap:10px; }
.shot-card { border:1px solid #e2e8f0; border-radius:10px; padding:10px; background:#f8fafc; }
.shot-title { margin:0 0 8px; font-size:13px; font-weight:700; color:#334155; }
.shot-image { width:100%; border-radius:8px; border:1px solid #e2e8f0; background:#fff; }
.shot-placeholder { display:grid; gap:6px; min-height:120px; padding:10px; border:1px dashed #cbd5e1; border-radius:8px; background:#fff; color:#64748b; font-size:12px; }

.guide-mobile {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px 14px 8px;
}
.guide-mobile-head h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}
.guide-mobile-role {
  margin: 6px 0 0;
  font-size: 14px;
  color: #ea580c;
  font-weight: 600;
}
.guide-mobile-intro {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  font-size: 14px;
  line-height: 1.55;
  color: #7c2d12;
}
.guide-mobile-step {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
}
.guide-mobile-step-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 700;
  color: #1e3a5f;
}
.guide-mobile-step-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.65;
  font-size: 15px;
  color: #1f2937;
}
.guide-mobile-step-list li {
  margin-bottom: 8px;
}
.pdf-panel--mobile {
  margin-top: 16px;
}

@media (max-width: 900px) {
  .guide-page:not(.guide-page--mobile) { grid-template-columns: 1fr; }
  .guide-menu { max-height: none; }
}
</style>
