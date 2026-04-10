<template>
  <div class="guide-page">
    <aside class="guide-menu">
      <h2>사용설명서</h2>
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
      <h1>{{ currentSection?.title || "사용설명서" }}</h1>
      <div class="content-box">{{ currentSection?.body || "불러오는 중..." }}</div>
      <div class="shot-wrap">
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
              <span>{{ shot.src }}</span>
              <span>{{ shot.guide }}</span>
            </div>
          </article>
        </div>
      </div>
      <div class="capture-tip">
        <strong>촬영 팁</strong>
        <p>헤더/사이드바/핵심 버튼이 함께 보이도록 1장, 상세 동작(등록/저장/업로드) 1장을 권장합니다.</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

interface GuideSection {
  title: string;
  body: string;
}

const sections = ref<GuideSection[]>([]);
const selectedTitle = ref("");
const failedImageMap = ref<Record<string, boolean>>({});

const currentSection = computed(() => sections.value.find((s) => s.title === selectedTitle.value) ?? sections.value[0]);
const screenshotConfig: Record<string, Array<{ src: string; label: string; guide: string }>> = {
  "대시보드": [
    { src: "/guide-shots/dashboard-overview.png", label: "대시보드 개요", guide: "KPI 카드와 주요 버튼이 보이게 촬영" },
    { src: "/guide-shots/dashboard-filter.png", label: "대시보드 필터", guide: "필터 적용 전/후 화면 중 1개 촬영" },
  ],
  "공지사항": [
    { src: "/guide-shots/notices-list.png", label: "공지사항 목록", guide: "목록 + 작성 버튼이 보이게 촬영" },
    { src: "/guide-shots/notices-detail-comment.png", label: "공지사항 상세/댓글", guide: "댓글 입력 영역 포함 촬영" },
  ],
  "안전보건 방침 및 목표": [
    { src: "/guide-shots/policy-goals-hq.png", label: "HQ 업로드 화면", guide: "방침/목표 2패널이 보이게 촬영" },
    { src: "/guide-shots/policy-goals-site.png", label: "SITE 조회 화면", guide: "현장/본사 전환 버튼 포함 촬영" },
  ],
  "근로자의견청취": [
    { src: "/guide-shots/worker-voice-list.png", label: "의견청취 목록", guide: "상태칩/액션버튼이 보이게 촬영" },
    { src: "/guide-shots/worker-voice-upload.png", label: "의견청취 업로드", guide: "파일 선택 + 업로드 버튼 포함 촬영" },
  ],
  "동적 메뉴(본사 설정)": [
    { src: "/guide-shots/dynamic-menu-settings.png", label: "동적 메뉴 설정", guide: "드래그앤드롭 순서 영역 포함 촬영" },
    { src: "/guide-shots/dynamic-menu-runtime.png", label: "동적 메뉴 실행 화면", guide: "게시판형 또는 표형 화면 촬영" },
  ],
  "구글설문 연동 운영(A안)": [
    { src: "/guide-shots/google-form-csv-download.png", label: "구글설문 CSV 다운로드", guide: "응답 다운로드 메뉴가 보이게 촬영" },
    { src: "/guide-shots/worker-voice-csv-upload.png", label: "BESMA CSV 업로드", guide: "근로자의견청취 업로드 단계 촬영" },
  ],
};
const currentShots = computed(() => {
  const title = currentSection.value?.title || "";
  return screenshotConfig[title] || [{ src: "/guide-shots/default.png", label: "기본 화면", guide: "해당 메뉴 대표 화면 1장을 배치하세요." }];
});

function markImageFailed(src: string) {
  failedImageMap.value = { ...failedImageMap.value, [src]: true };
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
  const res = await fetch("/BESMA_USER_GUIDE.md", { cache: "no-cache" });
  const text = await res.text();
  sections.value = parseSections(text);
  selectedTitle.value = sections.value[0]?.title ?? "";
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
.content-box { white-space:pre-wrap; line-height:1.7; color:#1f2937; }
.shot-wrap { margin-top: 16px; }
.shot-wrap h3 { margin: 0 0 8px; font-size: 16px; }
.shot-grid { display:grid; grid-template-columns: repeat(auto-fill,minmax(240px,1fr)); gap:10px; }
.shot-card { border:1px solid #e2e8f0; border-radius:10px; padding:10px; background:#f8fafc; }
.shot-title { margin:0 0 8px; font-size:13px; font-weight:700; color:#334155; }
.shot-image { width:100%; border-radius:8px; border:1px solid #e2e8f0; background:#fff; }
.shot-placeholder { display:grid; gap:6px; min-height:120px; padding:10px; border:1px dashed #cbd5e1; border-radius:8px; background:#fff; color:#64748b; font-size:12px; }
.capture-tip { margin-top: 12px; padding: 10px 12px; border:1px solid #e2e8f0; border-radius:10px; background:#fff; }
.capture-tip strong { font-size:13px; color:#0f172a; }
.capture-tip p { margin:4px 0 0; font-size:12px; color:#64748b; }
@media (max-width: 900px) {
  .guide-page { grid-template-columns: 1fr; }
  .guide-menu { max-height: none; }
}
</style>

