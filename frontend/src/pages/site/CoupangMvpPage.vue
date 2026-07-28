<template>
  <section class="coupang-page">
    <header class="hero">
      <div>
        <p class="eyebrow">PRIVATE PILOT · NOT RELEASED</p>
        <h2>쿠팡 MVP 실험실</h2>
        <p>도면 위에 작업 아이콘과 현장사진을 배치하고 서버에 저장합니다.</p>
        <p v-if="pilotSiteName" class="pilot-site">실험 대상: {{ pilotSiteName }}</p>
      </div>
      <span class="save-state" :class="{ saved: !dirty && currentId }">
        {{ saving ? "저장 중" : dirty ? "저장 필요" : currentId ? "저장됨" : "새 문서" }}
      </span>
    </header>

    <div v-if="loading" class="state-card">쿠팡 현장 정보를 확인하고 있습니다.</div>
    <div v-else-if="accessError" class="state-card error">{{ accessError }}</div>
    <template v-else>
      <nav class="mobile-tabs" aria-label="편집 단계">
        <button v-for="item in tabs" :key="item.key" type="button" :class="{ active: activeTab === item.key }" @click="activeTab = item.key">
          {{ item.label }}
        </button>
      </nav>
      <p class="pilot-notice">현재 정상익 본인 계정에서만 보이는 비공개 실험 기능입니다. 쿠팡 현장 계정에는 공개되지 않습니다.</p>
      <section class="automation-card">
        <div>
          <p class="eyebrow dark">FORM AUTOMATION CHECK</p>
          <h3>쿠팡 제출양식 자동화 시험</h3>
          <p>
            저장한 작업정보와 현재 도면을 노트북의 양지 5FC 승인 원본에 넣어
            제출용 Excel을 생성합니다.
          </p>
          <div class="automation-status">
            <span :class="selectedSite?.template_ready ? 'ready' : 'mapping'">
              {{ selectedSite?.template_ready ? "자동 생성 가능" : "원본 매핑 전" }}
            </span>
            <strong>{{ selectedSite?.label }}{{ selectedSite?.template_ready ? " · 제출 시트 10종" : " · 텍스트 복사 가능" }}</strong>
          </div>
          <details>
            <summary>취합된 INC 46FC 양식 검토 현황</summary>
            <p>
              중복 2세트를 제외하면 9종입니다. XLSX 6종은 셀 매핑 후보,
              PPTX 2종과 PDF 1종은 별도 출력 엔진 대상으로 분류했습니다.
            </p>
          </details>
        </div>
        <div class="automation-actions">
          <button type="button" class="preview-action" @click="activeTab = 'preview'">페이지별 미리보기</button>
          <button type="button" class="excel-action" :disabled="exporting || uploading || !selectedSite?.template_ready" @click="exportWorkbook">
            {{ exporting ? "제출본 생성 중" : selectedSite?.template_ready ? "제출용 Excel 자동 생성" : "원본 매핑 후 생성 가능" }}
          </button>
        </div>
      </section>

      <div class="workspace">
        <aside class="form-panel" :class="{ 'mobile-hidden': activeTab !== 'form' }">
          <div class="panel-title">
            <h3>작업 기본정보</h3>
            <button type="button" class="text-button" @click="newDocument">새로 작성</button>
          </div>
          <label>대상 현장
            <select v-model.number="form.target_site_id" @change="handleSiteChange">
              <option v-for="site in pilotSites" :key="site.id" :value="site.id">
                {{ site.label }}{{ site.template_ready ? " · Excel 자동화" : " · 매핑 검토" }}
              </option>
            </select>
          </label>
          <div class="input-mode-tabs">
            <button type="button" :class="{ active: inputMode === 'paste' }" @click="inputMode = 'paste'">전체 붙여넣기</button>
            <button type="button" :class="{ active: inputMode === 'manual' }" @click="inputMode = 'manual'">항목별 수정</button>
          </div>
          <template v-if="inputMode === 'paste'">
            <label>작업계획 전체 붙여넣기
              <textarea
                v-model="bulkText"
                class="bulk-textarea"
                rows="18"
                placeholder="[쿠팡 양지 5 금일 작업계획]부터 연락처까지 받은 내용을 그대로 붙여넣으세요."
              />
            </label>
            <button type="button" class="parse-action" @click="applyBulkText">붙여넣은 내용 자동 분해</button>
            <button type="button" class="copy-action" @click="copyCurrentTemplate">현재 내용을 작업계획 템플릿으로 복사</button>
            <p class="paste-help">자동 분해 후 `항목별 수정`에서 필요한 부분만 고칠 수 있습니다.</p>
          </template>
          <template v-else>
            <div class="field-grid">
              <label>작업일<input v-model="form.work_date" type="date" @input="markDirty" /></label>
              <label>층
                <select v-model="form.floor" @change="markDirty">
                  <option>4F</option><option>6F</option><option>4F/6F</option><option>기타</option>
                </select>
              </label>
            </div>
            <label>문서 제목<input v-model="form.title" maxlength="160" @input="markDirty" /></label>
            <div class="field-grid">
              <label>공정률(%)<input v-model.number="form.progress_rate" type="number" min="0" max="100" step=".01" @input="markDirty" /></label>
              <label>업체명<input v-model="form.contractor_name" maxlength="100" @input="markDirty" /></label>
            </div>
            <div class="field-grid">
              <label>시작시간<input v-model="form.start_time" type="time" @input="markDirty" /></label>
              <label>종료시간<input v-model="form.end_time" type="time" @input="markDirty" /></label>
            </div>
            <div class="count-grid">
              <label>총원<input v-model.number="form.total_count" type="number" min="0" @input="markDirty" /></label>
              <label>관리자<input v-model.number="form.manager_count" type="number" min="0" @input="markDirty" /></label>
              <label>근로자<input v-model.number="form.worker_count" type="number" min="0" @input="markDirty" /></label>
              <label>신호수<input v-model.number="form.signal_count" type="number" min="0" @input="markDirty" /></label>
            </div>
            <div class="work-item-editor">
              <div class="panel-title"><h4>위치별 작업 {{ todayJobs.length }}건</h4><button type="button" class="text-button" @click="addWorkItem">작업 추가</button></div>
              <div v-for="(job, index) in todayJobs" :key="index" class="work-item">
                <div class="field-grid">
                  <label>층<input v-model="job.floor" @input="syncJobs" /></label>
                  <label>작업장소<input v-model="job.workplace" @input="syncJobs" /></label>
                </div>
                <label>작업내용<textarea v-model="job.description" rows="2" @input="syncJobs" /></label>
                <label>이 작업 투입인원<input v-model.number="job.people" type="number" min="0" @input="syncJobs" /></label>
                <button type="button" class="remove-job" @click="removeWorkItem(index)">이 작업 삭제</button>
              </div>
            </div>
            <label>위험요인<textarea v-model="form.hazard" rows="3" @input="markDirty" /></label>
            <label>안전대책<textarea v-model="form.control" rows="3" @input="markDirty" /></label>
            <label>관리자 연락처<textarea v-model="form.contacts" rows="5" @input="markDirty" /></label>
            <label>비고<textarea v-model="form.notes" rows="2" @input="markDirty" /></label>
          </template>
        </aside>

        <main class="drawing-panel" :class="{ 'mobile-hidden': activeTab !== 'drawing' }">
          <div class="panel-title drawing-heading">
            <div>
              <h3>도면 표시</h3>
              <p>아이콘 또는 사진을 추가한 뒤 손가락으로 위치를 옮기세요.</p>
            </div>
            <button type="button" class="text-button" @click="fitDrawing">전체 보기</button>
          </div>

          <div class="upload-row">
            <label class="upload-button">
              도면 배경 올리기
              <input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadBackground" />
            </label>
            <label class="upload-button accent">
              현장사진 촬영·추가
              <input type="file" accept="image/*" capture="environment" @change="uploadPhoto" />
            </label>
          </div>

          <div class="tool-strip" aria-label="도면 아이콘">
            <button v-for="tool in iconTools" :key="tool.label" type="button" @click="addIcon(tool)">
              <span>{{ tool.glyph }}</span>{{ tool.label }}
            </button>
          </div>

          <div v-if="selectedObject" class="selection-tools">
            <label>표시 이름<input v-model="selectedObject.label" maxlength="30" @input="markDirty" /></label>
            <label>크기
              <input v-model.number="selectedObject.w" type="range" min="70" max="480" @input="resizeSelected" />
            </label>
            <label v-if="selectedObject.type === 'icon'">색상<input v-model="selectedObject.color" type="color" @input="markDirty" /></label>
            <div class="selection-actions">
              <button type="button" @click="moveLayer(-1)">뒤로</button>
              <button type="button" @click="moveLayer(1)">앞으로</button>
              <button type="button" class="danger" @click="removeSelected">삭제</button>
              <button type="button" @click="selectedId = null">선택해제</button>
            </div>
          </div>

          <div ref="canvasWrap" class="canvas-wrap">
            <svg
              ref="svgRef"
              class="drawing-svg"
              :viewBox="`0 0 ${drawing.width} ${drawing.height}`"
              role="img"
              aria-label="쿠팡 현장 작업 도면 편집기"
              @pointermove="moveObject"
              @pointerup="endDrag"
              @pointercancel="endDrag"
              @pointerleave="endDrag"
            >
              <rect width="100%" height="100%" fill="#f8fafc" />
              <image
                v-if="drawing.background_asset_id && assetUrls[drawing.background_asset_id]"
                :href="assetUrls[drawing.background_asset_id]"
                x="0" y="0" width="1600" height="1000"
                preserveAspectRatio="xMidYMid meet"
              />
              <g v-else class="empty-drawing">
                <rect x="40" y="40" width="1520" height="920" rx="24" fill="none" stroke="#cbd5e1" stroke-width="4" stroke-dasharray="18 14" />
                <text x="800" y="475" text-anchor="middle">도면 배경 이미지를 올려주세요</text>
                <text x="800" y="525" text-anchor="middle" class="small">JPG · PNG · WEBP, 최대 15MB</text>
              </g>

              <g
                v-for="object in drawing.objects"
                :key="object.id"
                :transform="`translate(${object.x} ${object.y})`"
                class="drawing-object"
                :class="{ selected: selectedId === object.id }"
                @pointerdown.stop.prevent="startDrag($event, object)"
                @click.stop="selectedId = object.id"
              >
                <template v-if="object.type === 'photo'">
                  <rect :width="object.w" :height="object.h" rx="12" fill="#fff" stroke="#fff" stroke-width="8" />
                  <image
                    v-if="object.asset_id && assetUrls[object.asset_id]"
                    :href="assetUrls[object.asset_id]"
                    :width="object.w" :height="object.h"
                    preserveAspectRatio="xMidYMid slice"
                  />
                  <rect :width="object.w" :height="object.h" rx="12" fill="none" stroke="#0f172a" stroke-width="4" />
                  <rect y="calc(100% - 38px)" :width="object.w" height="38" fill="#0f172a" opacity=".78" />
                  <text :x="object.w / 2" :y="object.h - 12" text-anchor="middle" fill="#fff" font-size="24">{{ object.label }}</text>
                </template>
                <template v-else>
                  <circle :cx="object.w / 2" :cy="object.h / 2" :r="object.w / 2 - 5" :fill="object.color" stroke="#fff" stroke-width="8" />
                  <text :x="object.w / 2" :y="object.h / 2 + 16" text-anchor="middle" font-size="48">{{ object.glyph }}</text>
                  <rect :x="-20" :y="object.h + 8" :width="object.w + 40" height="38" rx="10" fill="#0f172a" opacity=".88" />
                  <text :x="object.w / 2" :y="object.h + 35" text-anchor="middle" fill="#fff" font-size="24">{{ object.label }}</text>
                </template>
                <rect v-if="selectedId === object.id" x="-10" y="-10" :width="object.w + 20" :height="object.h + 65" rx="14" fill="none" stroke="#2563eb" stroke-width="6" stroke-dasharray="12 8" />
              </g>
            </svg>
          </div>

        </main>

        <section class="preview-panel" :class="{ 'mobile-hidden': activeTab !== 'preview' }">
          <div class="panel-title">
            <div><h3>제출본 페이지별 미리보기</h3><p>{{ previewPages.length }}개 제출 시트를 한 장씩 확인합니다.</p></div>
            <button type="button" class="text-button" @click="exportWorkbook">Excel 생성</button>
          </div>
          <div class="preview-page-tabs">
            <button v-for="(page, index) in previewPages" :key="page.key" type="button" :class="{ active: previewIndex === index }" @click="previewIndex = index">
              {{ index + 1 }}. {{ page.label }}
            </button>
          </div>
          <article class="paper-preview">
            <header><strong>{{ selectedSite?.label || "쿠팡 현장" }}</strong><span>{{ previewIndex + 1 }} / {{ previewPages.length }}</span></header>
            <h3>{{ currentPreview.label }}</h3>
            <template v-if="currentPreview.kind === 'drawing'">
              <div class="preview-drawing" v-html="previewSvgMarkup" />
              <div class="preview-jobs">
                <p v-for="(job, index) in todayJobs" :key="index"><strong>{{ job.workplace || job.floor }}</strong> — {{ job.description }}</p>
              </div>
            </template>
            <template v-else>
              <dl class="preview-fields">
                <div><dt>작업일자</dt><dd>{{ form.work_date }} {{ form.start_time }}~{{ form.end_time }}</dd></div>
                <div><dt>업체·공정률</dt><dd>{{ form.contractor_name }} · {{ form.progress_rate }}%</dd></div>
                <div><dt>인원현황</dt><dd>총 {{ form.total_count }} / 관리자 {{ form.manager_count }} / 근로자 {{ form.worker_count }} / 신호수 {{ form.signal_count }}</dd></div>
                <div><dt>작업장소</dt><dd>{{ todayJobs.map((job) => job.workplace || job.floor).filter(Boolean).join(", ") || form.workplace }}</dd></div>
                <div><dt>위험요인</dt><dd>{{ form.hazard }}</dd></div>
                <div><dt>안전대책</dt><dd>{{ form.control }}</dd></div>
              </dl>
            </template>
            <footer>미리보기 · 실제 Excel은 원본 시트 서식과 수식을 유지하여 생성됩니다.</footer>
          </article>
          <div class="preview-nav">
            <button type="button" :disabled="previewIndex === 0" @click="previewIndex--">이전 페이지</button>
            <button type="button" :disabled="previewIndex === previewPages.length - 1" @click="previewIndex++">다음 페이지</button>
          </div>
        </section>

        <aside class="history-panel" :class="{ 'mobile-hidden': activeTab !== 'history' }">
          <div class="panel-title">
            <h3>저장 내역</h3>
            <button type="button" class="text-button" @click="loadDocuments">새로고침</button>
          </div>
          <p v-if="documents.length === 0" class="empty-list">저장된 작업계획이 없습니다.</p>
          <button v-for="doc in documents" :key="doc.id" type="button" class="history-item" :class="{ active: currentId === doc.id }" @click="openDocument(doc)">
            <strong>{{ doc.title }}</strong>
            <span>{{ doc.work_date }} · {{ doc.floor }} · 표시 {{ doc.drawing?.objects?.length || 0 }}개</span>
          </button>
        </aside>
      </div>

      <footer class="action-bar">
        <button type="button" class="secondary-action" @click="downloadPng">도면 PNG 저장</button>
        <button type="button" class="primary-action" :disabled="saving || uploading" @click="saveDocument">
          {{ uploading ? "사진 업로드 중" : saving ? "저장 중" : currentId ? "변경사항 저장" : "서버에 저장" }}
        </button>
      </footer>
      <p v-if="message" class="toast" :class="{ error: messageIsError }">{{ message }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";

type TabKey = "form" | "drawing" | "preview" | "history";
type PilotSite = { id: number; name: string; label: string; template_ready: boolean };
type WorkItem = { floor: string; workplace: string; description: string; people: number };
type DrawingObject = {
  id: string;
  type: "icon" | "photo";
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  color?: string;
  glyph?: string;
  asset_id?: string;
};
type Drawing = { width: number; height: number; background_asset_id: string | null; objects: DrawingObject[] };
type StoredDocument = Record<string, any> & { id: number; title: string; work_date: string; floor: string; drawing: Drawing };

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "form", label: "① 붙여넣기" },
  { key: "drawing", label: "② 도면·사진" },
  { key: "preview", label: "③ 미리보기" },
  { key: "history", label: "④ 저장내역" },
];
const previewPages = [
  { key: "daily-report", label: "일일보고 대표", kind: "summary" },
  { key: "ptw", label: "PTW 작업허가서", kind: "summary" },
  { key: "prevention", label: "PTW 예방조치", kind: "summary" },
  { key: "daily-safety", label: "일일안전관리현황", kind: "summary" },
  { key: "meeting-4f", label: "공정회의록 4F", kind: "drawing" },
  { key: "meeting-6f", label: "공정회의록 6F", kind: "drawing" },
  { key: "grade-c", label: "C등급 평가표", kind: "summary" },
  { key: "waiting", label: "작업대기 공정", kind: "summary" },
  { key: "daily-check", label: "체크리스트 일일", kind: "summary" },
  { key: "weekly-check", label: "체크리스트 주간", kind: "summary" },
] as const;
const iconTools = [
  { label: "작업구역", glyph: "⚒", color: "#dc2626" },
  { label: "이동경로", glyph: "➜", color: "#2563eb" },
  { label: "소화기", glyph: "🧯", color: "#ef4444" },
  { label: "비상구", glyph: "↗", color: "#16a34a" },
  { label: "작업자", glyph: "👷", color: "#f59e0b" },
  { label: "고소작업", glyph: "▲", color: "#ea580c" },
  { label: "감전위험", glyph: "⚡", color: "#7c3aed" },
];

const loading = ref(true);
const saving = ref(false);
const exporting = ref(false);
const uploading = ref(false);
const dirty = ref(false);
const accessError = ref("");
const pilotSiteName = ref("");
const pilotSites = ref<PilotSite[]>([]);
const inputMode = ref<"paste" | "manual">("paste");
const bulkText = ref("");
const todayJobs = ref<WorkItem[]>([]);
const previewIndex = ref(0);
const message = ref("");
const messageIsError = ref(false);
const activeTab = ref<TabKey>("form");
const currentId = ref<number | null>(null);
const documents = ref<StoredDocument[]>([]);
const selectedId = ref<string | null>(null);
const svgRef = ref<SVGSVGElement | null>(null);
const canvasWrap = ref<HTMLElement | null>(null);
const assetUrls = reactive<Record<string, string>>({});
const form = reactive({
  target_site_id: 101,
  title: "쿠팡 일일 작업계획",
  work_date: todayKst(),
  progress_rate: 0,
  start_time: "07:00",
  end_time: "17:00",
  floor: "4F",
  workplace: "지하1층 2번코어",
  work_description: "",
  hazard: "안전고리 미체결로 인한 추락 위험",
  control: "적정 안전고리 체결 및 관리감독자 확인",
  contractor_name: "부현전기",
  manager_name: "",
  worker_count: 0,
  total_count: 0,
  manager_count: 0,
  signal_count: 0,
  fire_watch_count: 0,
  extra_time: "",
  extra_people: 0,
  extra_work: "",
  forklift_used: 0,
  forklift_owned: 0,
  lift_used: 0,
  lift_owned: 0,
  overtime: "무",
  fire_work: "무",
  contacts: "",
  foreign_worker_count: 0,
  raw_plan_text: "",
  notes: "",
});
const drawing = reactive<Drawing>({ width: 1600, height: 1000, background_asset_id: null, objects: [] });
const selectedObject = computed(() => drawing.objects.find((item) => item.id === selectedId.value) || null);
const selectedSite = computed(() => pilotSites.value.find((site) => site.id === Number(form.target_site_id)) || null);
const currentPreview = computed(() => previewPages[previewIndex.value] || previewPages[0]);
const previewSvgMarkup = computed(() => {
  JSON.stringify(drawing);
  if (!svgRef.value) return '<p class="preview-empty">도면을 먼저 올려주세요.</p>';
  const clone = svgRef.value.cloneNode(true) as SVGSVGElement;
  clone.querySelectorAll("rect[stroke='#2563eb']").forEach((node) => node.remove());
  clone.removeAttribute("class");
  return clone.outerHTML;
});
let dragState: { id: string; offsetX: number; offsetY: number } | null = null;

onMounted(async () => {
  try {
    const { data } = await api.get("/coupang-mvp/access");
    pilotSiteName.value = data.site_name || "";
    pilotSites.value = data.sites || [];
    Object.assign(form, data.defaults || {});
    await loadDocuments();
  } catch (error: any) {
    accessError.value = error?.response?.data?.detail || "쿠팡 MVP에 접근할 수 없습니다.";
  } finally {
    loading.value = false;
  }
});

function notify(text: string, isError = false) {
  message.value = text;
  messageIsError.value = isError;
  window.setTimeout(() => {
    if (message.value === text) message.value = "";
  }, 3500);
}

function markDirty() {
  dirty.value = true;
}

function resetDrawing() {
  drawing.width = 1600;
  drawing.height = 1000;
  drawing.background_asset_id = null;
  drawing.objects.splice(0);
  selectedId.value = null;
}

function newDocument() {
  currentId.value = null;
  Object.assign(form, {
    target_site_id: 101,
    title: "쿠팡 일일 작업계획",
    work_date: todayKst(),
    progress_rate: 0,
    start_time: "07:00",
    end_time: "17:00",
    floor: "4F",
    workplace: "",
    work_description: "",
    hazard: "안전고리 미체결로 인한 추락 위험",
    control: "적정 안전고리 체결 및 관리감독자 확인",
    contractor_name: "부현전기",
    manager_name: "",
    worker_count: 0,
    total_count: 0,
    manager_count: 0,
    signal_count: 0,
    fire_watch_count: 0,
    extra_time: "",
    extra_people: 0,
    extra_work: "",
    forklift_used: 0,
    forklift_owned: 0,
    lift_used: 0,
    lift_owned: 0,
    overtime: "무",
    fire_work: "무",
    contacts: "",
    foreign_worker_count: 0,
    raw_plan_text: "",
    notes: "",
  });
  bulkText.value = "";
  todayJobs.value = [];
  inputMode.value = "paste";
  previewIndex.value = 0;
  resetDrawing();
  dirty.value = false;
  activeTab.value = "form";
}

function handleSiteChange() {
  if (selectedSite.value) {
    pilotSiteName.value = selectedSite.value.name;
    form.title = `${selectedSite.value.label} 일일 작업계획`;
  }
  markDirty();
}

function numberAfter(text: string, label: string) {
  const match = text.match(new RegExp(`${label}\\s*[:：]\\s*(\\d+)`, "i"));
  return match ? Number(match[1]) : 0;
}

function sectionLines(lines: string[], start: RegExp, end: RegExp) {
  const startIndex = lines.findIndex((line) => start.test(line));
  if (startIndex < 0) return [];
  const tail = lines.slice(startIndex + 1);
  const endIndex = tail.findIndex((line) => end.test(line));
  return (endIndex < 0 ? tail : tail.slice(0, endIndex)).filter(Boolean);
}

function parseJobs(lines: string[]): WorkItem[] {
  const result: WorkItem[] = [];
  let currentFloor = "";
  for (const raw of lines) {
    const line = raw.replace(/^[-•]\s*/, "").trim();
    const floorMatch = line.match(/^(\d+)\s*층$/);
    if (floorMatch) {
      currentFloor = `${floorMatch[1]}층`;
      continue;
    }
    if (!line || /^\d+$/.test(line)) continue;
    const placeMatch = line.match(/^([0-9~～\-–,]+\s*챔버)\s+(.+)$/);
    const workplace = [currentFloor, placeMatch?.[1]].filter(Boolean).join(" ");
    result.push({
      floor: currentFloor ? currentFloor.replace("층", "F") : "",
      workplace: workplace || currentFloor,
      description: placeMatch?.[2] || line,
      people: 0,
    });
  }
  return result.slice(0, 10);
}

function detectSite(text: string) {
  const aliases: Array<[RegExp, number]> = [
    [/양지|YAN\s*5/i, 101],
    [/INC\s*46|인천/i, 48],
    [/DAE|대구/i, 46],
    [/GYS|경산/i, 47],
    [/CHA6|천안/i, 86],
    [/GWJ|광주/i, 89],
  ];
  const found = aliases.find(([pattern]) => pattern.test(text));
  if (found && pilotSites.value.some((site) => site.id === found[1])) form.target_site_id = found[1];
}

function applyBulkText() {
  const text = bulkText.value.replace(/\r/g, "").trim();
  if (!text) {
    notify("작업계획 내용을 먼저 붙여넣어 주세요.", true);
    return;
  }
  const lines = text.split("\n").map((line) => line.trim());
  detectSite(text);
  const header = lines.find((line) => /^\[.+작업계획.*\]$/.test(line));
  if (header) form.title = header.replace(/^\[|\]$/g, "").replace(/\s+/g, " ").trim();
  const companyLine = lines.find((line) => /업체명\s*:/.test(line));
  if (companyLine) {
    form.contractor_name = companyLine.split(":").slice(1).join(":").replace(/\s*\(공정[율률].*$/i, "").trim();
  }
  const progress = text.match(/공정[율률]\s*([0-9.]+)\s*%/);
  if (progress) form.progress_rate = Number(progress[1]);
  const workDate = text.match(/(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})/);
  if (workDate) form.work_date = `${workDate[1]}-${workDate[2].padStart(2, "0")}-${workDate[3].padStart(2, "0")}`;
  const times = text.match(/\((\d{1,2}:\d{2})\s*[~～-]\s*(\d{1,2}:\d{2})\)/);
  if (times) {
    form.start_time = times[1].padStart(5, "0");
    form.end_time = times[2].padStart(5, "0");
  }
  form.total_count = numberAfter(text, "총원");
  form.manager_count = numberAfter(text, "관리자");
  form.worker_count = numberAfter(text, "근로자");
  form.signal_count = numberAfter(text, "신호수(?:/유도원)?");
  const jobs = parseJobs(sectionLines(lines, /^5\.\s*작업내용/, /^6\.\s*작업장소/));
  todayJobs.value = jobs;
  const locationLines = sectionLines(lines, /^6\.\s*작업장소/, /^7\.\s*장비현황/)
    .map((line) => line.replace(/^[-•]\s*/, "").trim())
    .filter(Boolean);
  form.workplace = [...new Set([...jobs.map((job) => job.workplace), ...locationLines])].filter(Boolean).join(", ");
  form.work_description = jobs.map((job) => `${job.workplace || job.floor} ${job.description}`.trim()).join("\n");
  const floors = [...new Set(jobs.map((job) => job.floor).filter(Boolean))];
  form.floor = floors.length > 1 ? floors.join("/") : floors[0] || "기타";
  const forklift = text.match(/지게차[^\n]*\((\d+)\s*\/\s*(\d+)\)/);
  if (forklift) [form.forklift_used, form.forklift_owned] = [Number(forklift[1]), Number(forklift[2])];
  const lift = text.match(/고소작업대[^\n]*\((\d+)\s*\/\s*(\d+)\)/);
  if (lift) [form.lift_used, form.lift_owned] = [Number(lift[1]), Number(lift[2])];
  form.overtime = text.match(/연장,\s*야간,\s*익일조출\s*유무\s*:\s*([^\n]+)/)?.[1]?.trim() || "무";
  form.fire_work = text.match(/화기작업\s*유무\s*:\s*([^\n]+)/)?.[1]?.trim() || "무";
  form.foreign_worker_count = Number(text.match(/외국인\s*근로자\s*현황\s*:\s*(\d+)/)?.[1] || 0);
  const contacts = sectionLines(lines, /^10\.\s*관리자\s*연락처/, /^11\.\s*외국인/)
    .map((line) => line.replace(/^[-•]\s*/, "").trim())
    .filter(Boolean);
  form.contacts = contacts.join("\n");
  form.manager_name = contacts[0]?.replace(/\s*\(.+$/, "").trim() || "";
  form.raw_plan_text = text;
  pilotSiteName.value = selectedSite.value?.name || pilotSiteName.value;
  markDirty();
  inputMode.value = "manual";
  notify(`작업계획을 자동 분해했습니다. 위치별 작업 ${jobs.length}건을 확인해 주세요.`);
}

function syncJobs() {
  form.workplace = [...new Set(todayJobs.value.map((job) => job.workplace).filter(Boolean))].join(", ");
  form.work_description = todayJobs.value.map((job) => `${job.workplace || job.floor} ${job.description}`.trim()).join("\n");
  markDirty();
}

function addWorkItem() {
  todayJobs.value.push({ floor: "", workplace: "", description: "", people: 0 });
  markDirty();
}

function removeWorkItem(index: number) {
  todayJobs.value.splice(index, 1);
  syncJobs();
}

function koreanWeekday(value: string) {
  const day = new Date(`${value}T00:00:00`).getDay();
  return ["일", "월", "화", "수", "목", "금", "토"][day];
}

function currentTemplateText() {
  const siteLabel = selectedSite.value?.label || "쿠팡 현장";
  const jobsByFloor = new Map<string, WorkItem[]>();
  for (const job of todayJobs.value) {
    const floor = job.floor || "기타";
    jobsByFloor.set(floor, [...(jobsByFloor.get(floor) || []), job]);
  }
  const workLines = [...jobsByFloor.entries()].flatMap(([floor, jobs]) => [
    floor.replace("F", "층"),
    ...jobs.map((job) => `${job.workplace.replace(/^\d+층\s*/, "")} ${job.description}`.trim()),
    "",
  ]);
  const contacts = form.contacts
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `- ${line}`)
    .join("\n");
  return `[${siteLabel} 금일 작업계획]\n\n1. 업체명 : ${form.contractor_name} (공정율 ${form.progress_rate}%)\n\n2. 작업일자 : ${form.work_date.replace(/-/g, ".")} ${koreanWeekday(form.work_date)}요일 (${form.start_time}~${form.end_time})\n\n3. 인원현황\n- 총원 : ${form.total_count}명\n- 관리자 : ${form.manager_count}명\n- 근로자 : ${form.worker_count}명\n- 신호수/유도원 : ${form.signal_count}명\n\n4. 추가작업 인원\n- 시간 : ${form.extra_time}\n- 인원 : ${form.extra_people || ""}\n- 작업내용 : ${form.extra_work}\n\n5. 작업내용(위치별 전체작업 작성)\n\n${workLines.join("\n").trim()}\n\n6. 작업장소\n- ${form.workplace}\n\n7. 장비현황(사용/보유)\n- 지게차(${form.forklift_used}/${form.forklift_owned})\n- 고소작업대(${form.lift_used}/${form.lift_owned})\n\n8. 연장, 야간, 익일조출 유무 : ${form.overtime}\n\n9. 화기작업 유무 : ${form.fire_work}\n\n10. 관리자 연락처\n\n${contacts}\n\n11. 외국인 근로자 현황 : ${form.foreign_worker_count}`;
}

async function copyCurrentTemplate() {
  const text = currentTemplateText();
  bulkText.value = text;
  try {
    await navigator.clipboard.writeText(text);
    notify("현재 내용을 작업계획 템플릿으로 복사했습니다.");
  } catch {
    notify("클립보드 권한이 없어 붙여넣기 칸에 내용을 만들었습니다. 전체 선택해 복사하세요.", true);
  }
}

function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function addIcon(tool: { label: string; glyph: string; color: string }) {
  const index = drawing.objects.length % 6;
  const object: DrawingObject = {
    id: makeId("icon"),
    type: "icon",
    x: 650 + index * 28,
    y: 380 + index * 24,
    w: 120,
    h: 120,
    label: tool.label,
    glyph: tool.glyph,
    color: tool.color,
  };
  drawing.objects.push(object);
  selectedId.value = object.id;
  markDirty();
}

function svgPoint(event: PointerEvent) {
  const rect = svgRef.value!.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * drawing.width,
    y: ((event.clientY - rect.top) / rect.height) * drawing.height,
  };
}

function startDrag(event: PointerEvent, object: DrawingObject) {
  selectedId.value = object.id;
  const point = svgPoint(event);
  dragState = { id: object.id, offsetX: point.x - object.x, offsetY: point.y - object.y };
  svgRef.value?.setPointerCapture(event.pointerId);
}

function moveObject(event: PointerEvent) {
  if (!dragState) return;
  const object = drawing.objects.find((item) => item.id === dragState!.id);
  if (!object) return;
  const point = svgPoint(event);
  object.x = Math.round(Math.max(0, Math.min(drawing.width - object.w, point.x - dragState.offsetX)));
  object.y = Math.round(Math.max(0, Math.min(drawing.height - object.h - 55, point.y - dragState.offsetY)));
  markDirty();
}

function endDrag(event: PointerEvent) {
  if (dragState) svgRef.value?.releasePointerCapture?.(event.pointerId);
  dragState = null;
}

function resizeSelected() {
  const object = selectedObject.value;
  if (!object) return;
  object.h = object.type === "photo" ? Math.round(object.w * 0.7) : object.w;
  markDirty();
}

function moveLayer(direction: number) {
  const index = drawing.objects.findIndex((item) => item.id === selectedId.value);
  const next = Math.max(0, Math.min(drawing.objects.length - 1, index + direction));
  if (index < 0 || next === index) return;
  const [object] = drawing.objects.splice(index, 1);
  drawing.objects.splice(next, 0, object);
  markDirty();
}

function removeSelected() {
  const index = drawing.objects.findIndex((item) => item.id === selectedId.value);
  if (index < 0) return;
  drawing.objects.splice(index, 1);
  selectedId.value = null;
  markDirty();
}

async function uploadFile(file: File) {
  const body = new FormData();
  body.append("file", file);
  const { data } = await api.post("/coupang-mvp/assets", body, { headers: { "Content-Type": "multipart/form-data" } });
  assetUrls[data.asset_id] = await fileToDataUrl(file);
  return data;
}

function fileToDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function handleUpload(event: Event, kind: "background" | "photo") {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    const asset = await uploadFile(file);
    if (kind === "background") {
      drawing.background_asset_id = asset.asset_id;
    } else {
      const ratio = Math.max(0.45, Math.min(1.4, asset.height / asset.width));
      const object: DrawingObject = {
        id: makeId("photo"),
        type: "photo",
        x: 570,
        y: 330,
        w: 460,
        h: Math.round(460 * ratio),
        label: "현장사진",
        asset_id: asset.asset_id,
      };
      drawing.objects.push(object);
      selectedId.value = object.id;
    }
    markDirty();
    notify(kind === "background" ? "도면 배경을 올렸습니다." : "현장사진을 도면에 추가했습니다.");
  } catch (error: any) {
    notify(error?.response?.data?.detail || "이미지 업로드에 실패했습니다.", true);
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

const uploadBackground = (event: Event) => handleUpload(event, "background");
const uploadPhoto = (event: Event) => handleUpload(event, "photo");

async function loadAsset(assetId?: string | null) {
  if (!assetId || assetUrls[assetId]) return;
  try {
    const { data } = await api.get(`/coupang-mvp/assets/${assetId}`, { responseType: "blob" });
    assetUrls[assetId] = await fileToDataUrl(data);
  } catch {
    notify("저장된 이미지 일부를 불러오지 못했습니다.", true);
  }
}

async function hydrateAssets() {
  const ids = [
    drawing.background_asset_id,
    ...drawing.objects.map((item) => item.asset_id),
  ].filter(Boolean) as string[];
  await Promise.all([...new Set(ids)].map(loadAsset));
}

async function loadDocuments() {
  try {
    const { data } = await api.get("/coupang-mvp/documents");
    documents.value = data.items || [];
  } catch (error: any) {
    notify(error?.response?.data?.detail || "저장 내역을 불러오지 못했습니다.", true);
  }
}

async function openDocument(document: StoredDocument) {
  if (dirty.value && !window.confirm("저장하지 않은 변경사항이 있습니다. 이 문서를 여시겠습니까?")) return;
  currentId.value = document.id;
  for (const key of Object.keys(form) as Array<keyof typeof form>) {
    if (key in document) (form[key] as any) = document[key];
  }
  todayJobs.value = (document.today_jobs || []).map((item: WorkItem) => ({ ...item }));
  bulkText.value = document.raw_plan_text || currentTemplateText();
  pilotSiteName.value = selectedSite.value?.name || document.site_name || "";
  resetDrawing();
  Object.assign(drawing, {
    width: document.drawing?.width || 1600,
    height: document.drawing?.height || 1000,
    background_asset_id: document.drawing?.background_asset_id || null,
  });
  drawing.objects.push(...(document.drawing?.objects || []).map((item: DrawingObject) => ({ ...item })));
  await hydrateAssets();
  dirty.value = false;
  activeTab.value = "drawing";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function payload() {
  return {
    ...form,
    worker_count: Number(form.worker_count || 0),
    total_count: Number(form.total_count || 0),
    manager_count: Number(form.manager_count || 0),
    signal_count: Number(form.signal_count || 0),
    fire_watch_count: Number(form.fire_watch_count || 0),
    extra_people: Number(form.extra_people || 0),
    forklift_used: Number(form.forklift_used || 0),
    forklift_owned: Number(form.forklift_owned || 0),
    lift_used: Number(form.lift_used || 0),
    lift_owned: Number(form.lift_owned || 0),
    foreign_worker_count: Number(form.foreign_worker_count || 0),
    today_jobs: JSON.parse(JSON.stringify(todayJobs.value)),
    drawing: JSON.parse(JSON.stringify(drawing)),
  };
}

async function saveDocument() {
  if (!form.title.trim() || !form.work_date) {
    activeTab.value = "form";
    notify("작업일과 문서 제목을 입력해주세요.", true);
    return false;
  }
  saving.value = true;
  try {
    const { data } = currentId.value
      ? await api.put(`/coupang-mvp/documents/${currentId.value}`, payload())
      : await api.post("/coupang-mvp/documents", payload());
    currentId.value = data.id;
    dirty.value = false;
    await loadDocuments();
    notify("도면과 작업정보를 서버에 저장했습니다.");
    return true;
  } catch (error: any) {
    notify(error?.response?.data?.detail || "저장에 실패했습니다.", true);
    return false;
  } finally {
    saving.value = false;
  }
}

async function renderDrawingPng() {
  if (!svgRef.value) return;
  const clone = svgRef.value.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(drawing.width));
  clone.setAttribute("height", String(drawing.height));
  const source = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = reject;
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = drawing.width;
    canvas.height = drawing.height;
    canvas.getContext("2d")!.drawImage(image, 0, 0);
    return canvas.toDataURL("image/png");
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function downloadPng() {
  try {
    const png = await renderDrawingPng();
    if (!png) return;
    const link = document.createElement("a");
    link.download = `${form.work_date}_${form.floor}_쿠팡작업도면.png`;
    link.href = png;
    link.click();
    notify("현재 도면을 PNG로 저장했습니다.");
  } catch {
    notify("도면 이미지 생성에 실패했습니다.", true);
  }
}

async function exportWorkbook() {
  exporting.value = true;
  try {
    if (!currentId.value || dirty.value) {
      const saved = await saveDocument();
      if (!saved || !currentId.value) return;
    }
    const drawingPng = await renderDrawingPng();
    const { data } = await api.post(
      `/coupang-mvp/documents/${currentId.value}/export-xlsx`,
      { drawing_png: drawingPng || null },
      { responseType: "blob", timeout: 60_000 },
    );
    const url = URL.createObjectURL(data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${form.work_date}_${form.floor}_쿠팡_제출서류.xlsx`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("쿠팡 제출용 Excel을 자동 생성했습니다.");
  } catch (error: any) {
    const fallback = "제출용 Excel 생성에 실패했습니다.";
    if (error?.response?.data instanceof Blob) {
      try {
        const payload = JSON.parse(await error.response.data.text());
        notify(payload.detail || fallback, true);
      } catch {
        notify(fallback, true);
      }
    } else {
      notify(error?.response?.data?.detail || fallback, true);
    }
  } finally {
    exporting.value = false;
  }
}

function fitDrawing() {
  canvasWrap.value?.scrollTo({ left: 0, top: 0, behavior: "smooth" });
}
</script>

<style scoped>
.coupang-page { padding: 0 0 92px; color: #172033; }
.hero { display: flex; justify-content: space-between; gap: 24px; align-items: center; padding: 24px 28px; margin-bottom: 18px; color: #fff; border-radius: 22px; background: linear-gradient(125deg, #0b1736, #173f70 65%, #167e87); box-shadow: 0 16px 36px rgba(15, 23, 42, .18); }
.hero h2 { margin: 2px 0 6px; font-size: 28px; }.hero p { margin: 0; color: #dbeafe; }.eyebrow { font-size: 11px; letter-spacing: .18em; font-weight: 800; color: #67e8f9 !important; }
.hero .pilot-site { margin-top: 8px; color: #a5f3fc; font-size: 12px; font-weight: 800; }
.pilot-notice { margin: 0 0 12px; padding: 10px 13px; border: 1px solid #fbbf24; border-radius: 11px; color: #78350f; background: #fffbeb; font-size: 12px; font-weight: 800; }
.automation-card { display: flex; justify-content: space-between; align-items: center; gap: 24px; margin: 0 0 16px; padding: 18px 20px; border: 1px solid #99f6e4; border-radius: 16px; background: linear-gradient(120deg, #f0fdfa, #ecfeff); box-shadow: 0 8px 22px rgba(15,118,110,.08); }
.automation-card h3 { margin: 2px 0 5px; }.automation-card p { margin: 0; color: #475569; font-size: 13px; }.eyebrow.dark { color: #0f766e !important; }
.automation-status { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; }.automation-status .ready,.automation-status .mapping { padding: 4px 7px; border-radius: 999px; color: #fff; background: #0f766e; font-weight: 900; }.automation-status .mapping { background: #b45309; }
.automation-card details { margin-top: 10px; color: #334155; font-size: 12px; }.automation-card details p { margin-top: 7px; }.automation-card summary { cursor: pointer; font-weight: 800; }
.automation-actions { display: grid; flex: none; gap: 7px; }
.preview-action { min-height: 42px; padding: 0 18px; border: 1px solid #0f766e; border-radius: 11px; color: #0f766e; background: #fff; font-weight: 900; }
.excel-action { flex: none; min-height: 48px; padding: 0 18px; border: 0; border-radius: 11px; color: #fff; background: #166534; font-weight: 900; box-shadow: 0 7px 16px rgba(22,101,52,.2); }.excel-action:disabled { opacity: .55; }
.save-state { flex: none; padding: 8px 12px; border: 1px solid rgba(255,255,255,.3); border-radius: 999px; font-size: 12px; font-weight: 800; background: rgba(15,23,42,.35); }.save-state.saved { background: #0f766e; }
.workspace { display: grid; grid-template-columns: minmax(260px, .72fr) minmax(520px, 1.8fr) minmax(230px, .62fr); gap: 16px; align-items: start; }
.form-panel,.drawing-panel,.history-panel,.preview-panel,.state-card { background: #fff; border: 1px solid #dfe7f0; border-radius: 18px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,.06); }
.panel-title { display: flex; justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 14px; }.panel-title h3 { margin: 0; font-size: 18px; }.drawing-heading p { margin: 5px 0 0; font-size: 12px; color: #64748b; }
label { display: grid; gap: 6px; margin-bottom: 12px; font-size: 12px; font-weight: 800; color: #475569; }
input,textarea,select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px 11px; font: inherit; font-weight: 500; color: #0f172a; background: #fff; } textarea { resize: vertical; }.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.input-mode-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 12px; padding: 4px; border-radius: 11px; background: #e2e8f0; }.input-mode-tabs button { min-height: 38px; border: 0; border-radius: 8px; color: #475569; background: transparent; font-weight: 900; }.input-mode-tabs button.active { color: #fff; background: #173f70; }
.bulk-textarea { min-height: 310px; line-height: 1.55; }.parse-action,.copy-action { width: 100%; min-height: 44px; margin-bottom: 7px; border: 0; border-radius: 10px; color: #fff; background: #173f70; font-weight: 900; }.copy-action { color: #173f70; border: 1px solid #173f70; background: #fff; }.paste-help { margin: 4px 0 12px; color: #64748b; font-size: 11px; }
.count-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 6px; }.work-item-editor { margin: 5px 0 14px; padding: 11px; border: 1px solid #bae6fd; border-radius: 12px; background: #f0f9ff; }.work-item-editor h4 { margin: 0; }.work-item { position: relative; margin-top: 9px; padding: 10px; border-radius: 10px; background: #fff; }.remove-job { width: 100%; min-height: 32px; border: 1px solid #fecaca; border-radius: 8px; color: #b91c1c; background: #fff; font-size: 11px; }
button { font: inherit; cursor: pointer; }.text-button { padding: 0; border: 0; color: #2563eb; background: transparent; font-size: 12px; font-weight: 800; }
.upload-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }.upload-button { display: flex; justify-content: center; align-items: center; min-height: 44px; margin: 0; padding: 0 12px; border: 1px dashed #64748b; border-radius: 12px; color: #1e3a5f; background: #eff6ff; cursor: pointer; }.upload-button.accent { color: #075985; border-color: #0891b2; background: #ecfeff; }.upload-button input { display: none; }
.tool-strip { display: flex; gap: 7px; padding: 2px 0 12px; overflow-x: auto; }.tool-strip button { flex: 0 0 auto; display: grid; justify-items: center; gap: 2px; min-width: 68px; padding: 7px 8px; border: 1px solid #dbe3ed; border-radius: 11px; color: #334155; background: #fff; font-size: 11px; font-weight: 800; }.tool-strip button span { font-size: 22px; }
.canvas-wrap { width: 100%; overflow: auto; border: 1px solid #94a3b8; border-radius: 14px; background: #e2e8f0; }.drawing-svg { display: block; width: 100%; min-width: 520px; aspect-ratio: 1.6; background: #fff; touch-action: none; user-select: none; }.drawing-object { cursor: grab; }.drawing-object:active { cursor: grabbing; }.empty-drawing text { fill: #64748b; font-size: 34px; font-weight: 800; }.empty-drawing .small { font-size: 22px; font-weight: 500; }
.selection-tools { position: sticky; z-index: 8; top: 4px; display: grid; grid-template-columns: 1.3fr 1fr .55fr auto; gap: 10px; align-items: end; margin-bottom: 10px; padding: 12px; border: 1px solid #60a5fa; border-radius: 12px; background: #eff6ff; box-shadow: 0 7px 18px rgba(37,99,235,.14); }.selection-tools label { margin: 0; }.selection-actions { display: flex; gap: 5px; }.selection-actions button { min-height: 38px; border: 1px solid #cbd5e1; border-radius: 9px; background: #fff; }.selection-actions .danger { color: #b91c1c; }
.history-panel { max-height: 720px; overflow: auto; }.history-item { display: grid; width: 100%; gap: 5px; margin-bottom: 8px; padding: 12px; text-align: left; border: 1px solid #e2e8f0; border-radius: 11px; background: #f8fafc; }.history-item.active { border-color: #2563eb; background: #eff6ff; }.history-item span,.empty-list { color: #64748b; font-size: 11px; }
.preview-panel { grid-column: 1 / -1; }.preview-panel .panel-title p { margin: 4px 0 0; color: #64748b; font-size: 12px; }.preview-page-tabs { display: flex; gap: 6px; padding-bottom: 10px; overflow-x: auto; }.preview-page-tabs button { flex: 0 0 auto; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 9px; color: #475569; background: #fff; font-size: 11px; font-weight: 800; }.preview-page-tabs button.active { color: #fff; border-color: #173f70; background: #173f70; }
.paper-preview { width: min(900px,100%); min-height: 560px; box-sizing: border-box; margin: 0 auto; padding: 34px 38px; border: 1px solid #94a3b8; background: #fff; box-shadow: 0 8px 24px rgba(15,23,42,.12); }.paper-preview > header { display: flex; justify-content: space-between; padding-bottom: 10px; border-bottom: 3px solid #173f70; }.paper-preview > h3 { margin: 24px 0; text-align: center; font-size: 24px; }.paper-preview > footer { margin-top: 25px; padding-top: 10px; border-top: 1px solid #cbd5e1; color: #64748b; text-align: center; font-size: 11px; }.preview-drawing { overflow: hidden; border: 1px solid #cbd5e1; }.preview-drawing :deep(svg) { display: block; width: 100%; height: auto; }.preview-jobs p { margin: 8px 0; }.preview-fields { display: grid; gap: 0; border: 1px solid #94a3b8; }.preview-fields div { display: grid; grid-template-columns: 150px 1fr; border-bottom: 1px solid #cbd5e1; }.preview-fields div:last-child { border-bottom: 0; }.preview-fields dt,.preview-fields dd { margin: 0; padding: 13px; }.preview-fields dt { background: #eff6ff; font-weight: 900; }.preview-fields dd { white-space: pre-line; }.preview-nav { display: flex; justify-content: center; gap: 8px; margin-top: 12px; }.preview-nav button { min-height: 40px; padding: 0 20px; border: 1px solid #94a3b8; border-radius: 9px; background: #fff; font-weight: 800; }.preview-nav button:disabled { opacity: .4; }
.action-bar { position: fixed; z-index: 20; right: 24px; bottom: 18px; display: flex; gap: 8px; padding: 8px; border: 1px solid #dbe3ed; border-radius: 16px; background: rgba(255,255,255,.94); box-shadow: 0 12px 35px rgba(15,23,42,.22); backdrop-filter: blur(10px); }.action-bar button { min-height: 46px; padding: 0 20px; border-radius: 11px; font-weight: 900; }.primary-action { color: #fff; border: 0; background: #0f766e; }.primary-action:disabled { opacity: .55; }.secondary-action { color: #1e3a5f; border: 1px solid #94a3b8; background: #fff; }
.mobile-tabs { display: none; }.toast { position: fixed; z-index: 30; left: 50%; bottom: 88px; transform: translateX(-50%); padding: 11px 16px; border-radius: 11px; color: #fff; background: #0f766e; box-shadow: 0 8px 30px rgba(0,0,0,.25); }.toast.error,.state-card.error { color: #b91c1c; background: #fff1f2; }
@media (max-width: 1180px) { .workspace { grid-template-columns: 280px 1fr; }.history-panel { grid-column: 1 / -1; max-height: none; }.history-item { display: inline-grid; width: min(280px, 100%); margin-right: 8px; } }
@media (max-width: 760px) {
  .coupang-page { padding-bottom: 86px; }.hero { align-items: start; padding: 18px; border-radius: 16px; }.hero h2 { font-size: 21px; }.hero p:not(.eyebrow) { font-size: 12px; }.save-state { padding: 6px 8px; }
  .automation-card { display: grid; gap: 14px; padding: 15px; }.automation-actions,.excel-action,.preview-action { width: 100%; }
  .mobile-tabs { position: sticky; z-index: 12; top: 0; display: grid; grid-template-columns: repeat(4,1fr); gap: 3px; margin: 0 0 10px; padding: 4px; border: 1px solid #dbe3ed; border-radius: 12px; background: #fff; }.mobile-tabs button { min-height: 40px; padding: 0 3px; border: 0; border-radius: 9px; color: #64748b; background: transparent; font-size: 11px; font-weight: 900; }.mobile-tabs button.active { color: #fff; background: #173f70; }
  .workspace { display: block; }.form-panel,.drawing-panel,.history-panel,.preview-panel { border-radius: 14px; padding: 13px; }.mobile-hidden { display: none; }.field-grid { grid-template-columns: 1fr 1fr; }.count-grid { grid-template-columns: 1fr 1fr; }.upload-row { grid-template-columns: 1fr; }.drawing-svg { min-width: 460px; }.selection-tools { top: 50px; grid-template-columns: 1fr 1fr; }.selection-actions { grid-column: 1/-1; flex-wrap: wrap; }.selection-actions button { flex: 1; }.history-item { display: grid; width: 100%; margin-right: 0; }.paper-preview { min-height: 470px; padding: 20px 15px; }.paper-preview > h3 { font-size: 19px; }.preview-fields div { grid-template-columns: 105px 1fr; }.preview-fields dt,.preview-fields dd { padding: 9px; font-size: 12px; }
  .action-bar { right: 10px; bottom: 10px; left: 10px; }.action-bar button { flex: 1; padding: 0 9px; font-size: 13px; }.toast { width: calc(100% - 40px); box-sizing: border-box; text-align: center; }
}
</style>
