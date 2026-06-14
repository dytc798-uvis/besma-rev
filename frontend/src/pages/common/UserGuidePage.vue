<template>
  <div class="guide-page">
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

      <div v-if="showPdfDownloads" class="pdf-panel">
        <h3>역할별 A4 PDF</h3>
        <ul class="pdf-list">
          <li v-for="pdf in pdfDownloads" :key="pdf.href">
            <a :href="pdf.href" target="_blank" rel="noopener noreferrer">{{ pdf.label }}</a>
          </li>
        </ul>
      </div>

      <div class="content-box" v-html="renderedBody" />

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
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface GuideSection {
  title: string;
  body: string;
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
const auth = useAuthStore();

const canManageGuideShots = computed(
  () => (auth.user?.login_id || "").trim().toLowerCase() === "hq01",
);

const currentSection = computed(() => sections.value.find((s) => s.title === selectedTitle.value) ?? sections.value[0]);

const showPdfDownloads = computed(() => currentSection.value?.title === "PDF 다운로드");

const currentShots = computed(() => {
  const title = currentSection.value?.title || "";
  return uploadedShotsMap.value[title] || [];
});

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatGuideBody(body: string) {
  const lines = body.split(/\r?\n/);
  const html: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
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

const renderedBody = computed(() => formatGuideBody(currentSection.value?.body || ""));

function defaultSectionTitle(all: GuideSection[]) {
  const ui = auth.user?.ui_type;
  if (ui === "HQ_SAFE") {
    return all.find((s) => s.title.includes("본사"))?.title ?? all[0]?.title ?? "";
  }
  if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
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

onMounted(async () => {
  if (!auth.user) {
    await auth.loadMe();
  }
  const res = await fetch(GUIDE_PATH, { cache: "no-cache" });
  const text = await res.text();
  sections.value = parseSections(text);
  selectedTitle.value = defaultSectionTitle(sections.value);
  if (selectedTitle.value) {
    await loadUploadedShots(selectedTitle.value);
  }
});

watch(selectedTitle, (title) => {
  if (!title) return;
  void loadUploadedShots(title);
});
</script>

<style scoped>
.guide-page { display: grid; grid-template-columns: 260px 1fr; gap: 14px; }
.guide-menu { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:12px; display:grid; gap:8px; max-height:75vh; overflow:auto; }
.guide-menu h2 { margin:0 0 4px; font-size:16px; }
.menu-btn { text-align:left; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px; background:#fff; cursor:pointer; }
.menu-btn.active { background:#eff6ff; border-color:#93c5fd; color:#1d4ed8; font-weight:600; }
.guide-content { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:16px; }
.guide-content h1 { margin:0 0 10px; font-size:20px; }
.content-box { line-height:1.7; color:#1f2937; }
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
@media (max-width: 900px) {
  .guide-page { grid-template-columns: 1fr; }
  .guide-menu { max-height: none; }
}
</style>
