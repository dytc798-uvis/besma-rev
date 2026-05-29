<template>
  <div class="fe-hq-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">기능인제 인사고과 · 본사</h1>
        <p class="page-sub">현장별 평가 진행 확인 — 상세는 현장 선택, 전체 명단은 엑셀</p>
      </div>
      <div class="head-actions">
        <button class="stitch-btn-secondary" type="button" :disabled="exporting" @click="downloadEvalExcel">
          {{ exporting ? "다운로드 중..." : "평가 현황 엑셀" }}
        </button>
        <button class="stitch-btn-secondary" type="button" @click="loadOverview">새로고침</button>
      </div>
    </div>

    <section class="panel">
      <h2>평가 회차</h2>
      <div class="row">
        <label>
          마감일
          <input v-model="deadlineInput" type="date" />
        </label>
        <button class="stitch-btn-primary" type="button" :disabled="!period" @click="saveDeadline">마감일 저장</button>
        <span v-if="period?.is_closed" class="badge closed">마감됨</span>
        <span v-else class="badge open">진행 중</span>
        <span v-if="totals" class="kpi">
          현장 {{ totals.sites }} · 근로자 {{ totals.workers }}명 · 전체완료 {{ totals.fully_complete }}
        </span>
      </div>
    </section>

    <!-- 현장 목록 -->
    <section v-if="!selectedSite" class="panel">
      <h2>현장별 평가 진행</h2>
      <p class="panel-sub">현장을 선택하면 <strong>평가 완료(기능+안전)</strong>된 근로자만 표시됩니다.</p>
      <div class="toolbar">
        <label>
          현장 검색
          <input v-model="siteSearch" type="text" placeholder="현장명·코드·소장명" class="input-md" />
        </label>
        <label>
          정렬
          <select v-model="sortBy" @change="loadOverview">
            <option value="site_code">현장코드</option>
            <option value="site_name">현장명</option>
            <option value="evaluator_name">평가자</option>
            <option value="progress">진행률</option>
          </select>
        </label>
        <label>
          방향
          <select v-model="sortDir" @change="loadOverview">
            <option value="asc">오름차순</option>
            <option value="desc">내림차순</option>
          </select>
        </label>
      </div>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>현장명</th>
              <th>평가자(소장)</th>
              <th>평가 현황</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in filteredSites"
              :key="s.site_code"
              class="site-row"
              :class="{ 'site-row--active': s.has_completed }"
              @click="openSite(s)"
            >
              <td>{{ s.site_name }}</td>
              <td>{{ s.evaluator_name }}</td>
              <td>
                <span class="progress-pill" :class="{ done: s.fully_complete > 0 }">{{ s.progress }}</span>
              </td>
              <td class="chevron">›</td>
            </tr>
            <tr v-if="!filteredSites.length">
              <td colspan="4" class="muted">표시할 현장이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 현장 상세: 완료자만 -->
    <section v-else class="panel">
      <div class="detail-head">
        <button class="stitch-btn-secondary back-btn" type="button" @click="closeSite">← 현장 목록</button>
        <div>
          <h2>{{ selectedSite.site_name }}</h2>
          <p class="panel-sub">
            평가자 {{ selectedSite.evaluator_name }} · 진행
            <strong>{{ siteDetail?.site?.progress || selectedSite.progress }}</strong>
          </p>
        </div>
      </div>

      <div v-if="loadingSite" class="muted">불러오는 중...</div>
      <template v-else>
        <p v-if="!evalRows.length" class="empty-msg">
          아직 평가 완료(기능+안전)된 근로자가 없습니다. 진행률은 {{ siteDetail?.site?.progress || selectedSite.progress }} 입니다.
        </p>
        <div v-else class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>이름</th>
                <th>안전등급</th>
                <th>품질등급</th>
                <th>비고</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in evalRows" :key="row.worker_id">
                <td>{{ row.name }}</td>
                <td><span :class="gradeClass(row.safety_grade)">{{ row.safety_grade }}</span></td>
                <td><span :class="gradeClass(row.functional_grade)">{{ row.functional_grade }}</span></td>
                <td class="remark">{{ row.remark }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>

    <section class="panel collapsible">
      <button class="section-toggle" type="button" @click="showAdmin = !showAdmin">
        {{ showAdmin ? "▾" : "▸" }} 명부·제재 관리
      </button>
      <template v-if="showAdmin">
        <h3>일용직 명부 (xlsx)</h3>
        <div class="row import-row">
          <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" />
          <button class="stitch-btn-secondary" type="button" :disabled="!rosterFile || diffing" @click="runDiff">
            {{ diffing ? "DIFF 중..." : "DIFF 미리보기" }}
          </button>
          <button class="stitch-btn-primary" type="button" :disabled="!rosterFile || applying" @click="applyRoster">
            {{ applying ? "반영 중..." : "DIFF 반영" }}
          </button>
          <button class="stitch-btn-secondary" type="button" :disabled="!period?.is_closed" @click="downloadSanctionExcel">
            제재 엑셀 (마감 후)
          </button>
        </div>
        <div v-if="diffResult" class="diff-summary">
          <span>신규 {{ diffResult.new_count }}</span>
          <span>변경 {{ diffResult.updated_count }}</span>
          <span>제외 {{ diffResult.removed_count }}</span>
        </div>
        <p v-if="applyResult" class="meta success">{{ applyResult }}</p>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
}

interface Totals {
  sites: number;
  workers: number;
  fully_complete: number;
  incomplete: number;
}

interface SiteRow {
  site_code: string;
  site_name: string;
  evaluator_name: string;
  total: number;
  fully_complete: number;
  progress: string;
  has_completed: boolean;
}

interface EvalRow {
  worker_id: number;
  name: string;
  functional_grade: string;
  safety_grade: string;
  remark: string;
}

interface DiffResult {
  new_count: number;
  updated_count: number;
  removed_count: number;
}

const period = ref<Period | null>(null);
const totals = ref<Totals | null>(null);
const sites = ref<SiteRow[]>([]);
const selectedSite = ref<SiteRow | null>(null);
const siteDetail = ref<{ site: SiteRow } | null>(null);
const evalRows = ref<EvalRow[]>([]);
const loadingSite = ref(false);
const exporting = ref(false);
const deadlineInput = ref("");
const sortBy = ref("site_code");
const sortDir = ref("asc");
const siteSearch = ref("");
const showAdmin = ref(false);
const rosterFile = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const diffing = ref(false);
const applying = ref(false);
const diffResult = ref<DiffResult | null>(null);
const applyResult = ref("");

const filteredSites = computed(() => {
  const q = siteSearch.value.trim().toLowerCase();
  if (!q) return sites.value;
  return sites.value.filter(
    (s) =>
      s.site_code.toLowerCase().includes(q) ||
      (s.site_name || "").toLowerCase().includes(q) ||
      (s.evaluator_name || "").toLowerCase().includes(q),
  );
});

function gradeClass(grade: string) {
  if (grade === "미평가") return "grade pending";
  if (grade === "S" || grade === "우수") return "grade s";
  if (grade === "A") return "grade a";
  if (grade === "B" || grade === "보통") return "grade b";
  if (grade === "C" || grade === "부족") return "grade c";
  if (grade === "D" || grade === "최하") return "grade d";
  return "grade done";
}

async function loadOverview() {
  const res = await api.get("/functional-eval/hq/summary", {
    params: { sort_by: sortBy.value, sort_dir: sortDir.value },
  });
  period.value = res.data.period;
  totals.value = res.data.totals || null;
  sites.value = res.data.sites || [];
  deadlineInput.value = period.value?.deadline_date || "";
}

async function openSite(site: SiteRow) {
  selectedSite.value = site;
  loadingSite.value = true;
  evalRows.value = [];
  try {
    const res = await api.get(`/functional-eval/hq/sites/${encodeURIComponent(site.site_code)}/evaluations`, {
      params: { sort_by: "name", sort_dir: "asc" },
    });
    siteDetail.value = res.data;
    evalRows.value = res.data.eval_rows || [];
  } finally {
    loadingSite.value = false;
  }
}

function closeSite() {
  selectedSite.value = null;
  siteDetail.value = null;
  evalRows.value = [];
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  rosterFile.value = input.files?.[0] || null;
  diffResult.value = null;
  applyResult.value = "";
}

async function uploadFile(endpoint: string) {
  const form = new FormData();
  form.append("file", rosterFile.value!);
  return api.post(endpoint, form);
}

async function runDiff() {
  if (!rosterFile.value) return;
  diffing.value = true;
  try {
    const res = await uploadFile("/functional-eval/hq/roster/diff");
    diffResult.value = res.data;
    period.value = res.data.period;
    deadlineInput.value = period.value?.deadline_date || "";
  } finally {
    diffing.value = false;
  }
}

async function applyRoster() {
  if (!rosterFile.value) return;
  applying.value = true;
  try {
    const res = await uploadFile("/functional-eval/hq/roster/apply");
    applyResult.value = `반영 완료 — 신규 ${res.data.new_count}, 변경 ${res.data.updated_count}`;
    rosterFile.value = null;
    if (fileInput.value) fileInput.value.value = "";
    await loadOverview();
    if (selectedSite.value) await openSite(selectedSite.value);
  } finally {
    applying.value = false;
  }
}

async function saveDeadline() {
  if (!period.value || !deadlineInput.value) return;
  await api.patch(`/functional-eval/period/${period.value.id}/deadline`, {
    deadline_date: deadlineInput.value,
  });
  await loadOverview();
}

async function downloadEvalExcel() {
  exporting.value = true;
  try {
    const res = await api.get("/functional-eval/hq/export/evaluations", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = "functional_eval_grades.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}

async function downloadSanctionExcel() {
  const res = await api.get("/functional-eval/hq/export", { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "functional_eval_sanctions.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(loadOverview);
</script>

<style scoped>
.fe-hq-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.panel-sub { color: #64748b; font-size: 13px; margin: 4px 0 12px; }
.row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-top: 8px; }
.toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; align-items: flex-end; }
.toolbar label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.input-md { min-width: 200px; padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.kpi { font-size: 13px; color: #475569; margin-left: 8px; }
.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border-bottom: 1px solid #e5e7eb; padding: 10px 8px; text-align: left; }
.site-row { cursor: pointer; }
.site-row:hover { background: #f8fafc; }
.site-row--active .progress-pill { font-weight: 600; }
.chevron { color: #94a3b8; width: 24px; text-align: right; }
.progress-pill { font-variant-numeric: tabular-nums; }
.progress-pill.done { color: #166534; }
.detail-head { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
.back-btn { flex-shrink: 0; }
.empty-msg { color: #64748b; font-size: 14px; padding: 12px 0; }
.grade { font-weight: 600; font-size: 13px; }
.grade.pending { color: #94a3b8; font-weight: 400; }
.grade.s { color: #166534; }
.grade.a { color: #15803d; }
.grade.b { color: #1d4ed8; }
.grade.c { color: #b45309; }
.grade.d { color: #991b1b; }
.remark { font-size: 13px; color: #475569; }
.badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.badge.open { background: #dcfce7; color: #166534; }
.badge.closed { background: #fee2e2; color: #991b1b; }
.meta.success { color: #166534; font-size: 13px; }
.muted { color: #94a3b8; }
.section-toggle { width: 100%; text-align: left; background: none; border: none; font-size: 15px; font-weight: 600; cursor: pointer; padding: 0 0 12px; }
.diff-summary { display: flex; gap: 12px; margin-top: 8px; font-size: 14px; }
</style>
