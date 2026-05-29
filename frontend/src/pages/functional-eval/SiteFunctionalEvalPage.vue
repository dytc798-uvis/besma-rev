<template>
  <div class="fe-page">
    <div class="page-head">
      <div class="page-head-text">
        <h1 class="page-title">기능인제 인사고과</h1>
        <p class="page-sub">
          마감일 <strong>{{ period?.deadline_date || "—" }}</strong>
          <span v-if="period?.last_attendance_date"> · 출역 {{ period.last_attendance_date }} ({{ workers.length }}명)</span>
          <span v-if="!period?.is_closed" class="incomplete-count">미평가 {{ incompleteCount }}명</span>
          <span v-if="period?.is_closed" class="badge closed">마감</span>
          <span v-else class="badge open">진행</span>
        </p>
        <p v-if="attendanceMessage" class="attendance-warn">{{ attendanceMessage }}</p>
      </div>
      <button class="btn-refresh stitch-btn-secondary" type="button" @click="load">새로고침</button>
    </div>

    <nav class="fe-tabs" aria-label="인사고과 구역">
      <button type="button" class="fe-tab" :class="{ active: activeTab === 'functional' }" @click="activeTab = 'functional'">
        2-1 기능
      </button>
      <button type="button" class="fe-tab" :class="{ active: activeTab === 'safety' }" @click="activeTab = 'safety'">
        2-2 안전
      </button>
      <button type="button" class="fe-tab" :class="{ active: activeTab === 'sanctions' }" @click="activeTab = 'sanctions'">
        제재
      </button>
    </nav>

    <FunctionalEvalWorkspace
      v-if="activeTab !== 'sanctions' && evalCriteria.length"
      :key="activeTab"
      :workers="workers"
      :eval-type="currentEvalType"
      :title="evalTabTitle"
      :criteria="evalCriteria"
      :period-closed="Boolean(period?.is_closed)"
      :focus-worker-id="focusWorkerId"
      :reload="load"
      @request-safety="onRequestSafety"
    />

    <!-- 모바일: 제재·이력 바텀시트 -->
    <Teleport to="body">
      <div
        v-if="isMobileViewport && (selectedWorker || historyWorker)"
        class="fe-sheet-backdrop"
        aria-hidden="true"
        @click="closePanels"
      />
      <section
        v-if="selectedWorker"
        class="panel sanction-form"
        :class="{ 'fe-sheet': isMobileViewport, 'fe-sheet-open': isMobileViewport }"
        role="dialog"
        aria-modal="true"
        :aria-label="`${selectedWorker.name} 제재 등록`"
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <h2>{{ selectedWorker.name }} — 위반·제재</h2>
        <label class="field">
          <span class="field-label">위반 항목</span>
          <select v-model="form.violation_code" class="field-control">
            <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
              <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
            </optgroup>
          </select>
        </label>
        <label class="field">
          <span class="field-label">비고</span>
          <textarea v-model="form.note" class="field-control" rows="3" placeholder="위반 상황 (선택)" />
        </label>
        <div class="actions" :class="{ 'actions-sticky': isMobileViewport }">
          <button class="stitch-btn-secondary touch-btn" type="button" @click="closeForm">취소</button>
          <button
            class="stitch-btn-primary touch-btn"
            type="button"
            :disabled="!form.violation_code || saving || period?.is_closed"
            @click="submitSanction"
          >
            {{ saving ? "등록 중…" : "제재 등록" }}
          </button>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <section
        v-if="historyWorker"
        class="panel history-panel"
        :class="{ 'fe-sheet': isMobileViewport, 'fe-sheet-open': isMobileViewport }"
        role="dialog"
        aria-modal="true"
        :aria-label="`${historyWorker.name} 이력`"
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <div class="history-head">
          <h2>{{ historyWorker.name }} — 이력</h2>
          <button class="link-btn touch-btn-inline" type="button" @click="closeHistory">닫기</button>
        </div>
        <p v-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</p>
        <ul v-else class="history-list">
          <li v-for="s in allHistorySanctions" :key="`${s.id}-h`">
            <span v-if="s.from_prior_period" class="tag">이전</span>
            {{ s.violation_label }} → {{ s.sanction_result_label }} ({{ s.strike_number }}차)
            <span class="meta">{{ formatDate(s.created_at) }}</span>
          </li>
          <li v-if="!allHistorySanctions.length">제재 이력 없음</li>
        </ul>
        <div class="mileage-box">
          <h3>마일리지 (운영 준비)</h3>
          <p>{{ historyData?.mileage?.message }}</p>
          <p class="meta">적립 예정: {{ historyData?.mileage?.points ?? 0 }}점</p>
        </div>
      </section>
    </Teleport>

    <!-- 데스크톱: 인라인 패널 -->
    <section v-if="!isMobileViewport && selectedWorker" class="panel sanction-form">
      <h2>{{ selectedWorker.name }} — 위반·제재 등록</h2>
      <label class="field">
        <span class="field-label">위반 항목</span>
        <select v-model="form.violation_code" class="field-control">
          <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
            <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
          </optgroup>
        </select>
      </label>
      <label class="field">
        <span class="field-label">비고</span>
        <textarea v-model="form.note" class="field-control" rows="2" placeholder="위반 상황 (선택)" />
      </label>
      <div class="actions">
        <button class="stitch-btn-secondary" type="button" @click="closeForm">취소</button>
        <button
          class="stitch-btn-primary"
          type="button"
          :disabled="!form.violation_code || saving || period?.is_closed"
          @click="submitSanction"
        >
          {{ saving ? "등록 중..." : "제재 등록" }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <section v-if="!isMobileViewport && historyWorker" class="panel history-panel">
      <div class="history-head">
        <h2>{{ historyWorker.name }} — 이력</h2>
        <button class="link-btn" type="button" @click="closeHistory">닫기</button>
      </div>
      <p v-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</p>
      <ul v-else class="history-list">
        <li v-for="s in allHistorySanctions" :key="`${s.id}-h`">
          <span v-if="s.from_prior_period" class="tag">이전</span>
          {{ s.violation_label }} → {{ s.sanction_result_label }} ({{ s.strike_number }}차)
          <span class="meta">{{ formatDate(s.created_at) }}</span>
        </li>
        <li v-if="!allHistorySanctions.length">제재 이력 없음</li>
      </ul>
      <div class="mileage-box">
        <h3>마일리지 (운영 준비)</h3>
        <p>{{ historyData?.mileage?.message }}</p>
        <p class="meta">적립 예정 포인트: {{ historyData?.mileage?.points ?? 0 }}</p>
      </div>
    </section>

    <section v-show="activeTab === 'sanctions'" class="panel workers-panel">
      <div class="workers-head">
        <h2>제재 대상 근로자 <span class="count">{{ filteredWorkers.length }}</span>명</h2>
        <input
          v-model.trim="workerSearch"
          type="search"
          class="worker-search field-control"
          placeholder="이름 검색"
          autocomplete="off"
          enterkeyhint="search"
        />
      </div>

      <!-- 데스크톱 테이블 -->
      <div class="table-wrap desktop-only">
        <table class="data-table">
          <thead>
            <tr>
              <th>번호</th>
              <th>성명</th>
              <th>제재 상태</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in filteredWorkers" :key="w.id">
              <td>{{ w.row_no }}</td>
              <td>{{ w.name }}</td>
              <td>
                <span :class="['status-pill', statusClass(w.sanction_status)]">{{ w.sanction_status_label }}</span>
              </td>
              <td class="actions-cell">
                <button class="link-btn" type="button" @click="openHistory(w)">이력</button>
                <button
                  class="link-btn"
                  type="button"
                  :disabled="period?.is_closed || w.is_permanently_expelled"
                  @click="openSanction(w)"
                >
                  제재
                </button>
              </td>
            </tr>
            <tr v-if="!filteredWorkers.length">
              <td colspan="4" class="empty-cell">검색 결과가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 모바일 카드 목록 -->
      <ul class="worker-cards mobile-only">
        <li v-for="w in filteredWorkers" :key="w.id" class="worker-card">
          <div class="worker-card-main">
            <span class="worker-no">{{ w.row_no }}</span>
            <div class="worker-info">
              <span class="worker-name">{{ w.name }}</span>
              <span :class="['status-pill', statusClass(w.sanction_status)]">{{ w.sanction_status_label }}</span>
            </div>
          </div>
          <div class="worker-card-actions">
            <button class="card-btn card-btn-secondary touch-btn" type="button" @click="openHistory(w)">이력</button>
            <button
              class="card-btn card-btn-primary touch-btn"
              type="button"
              :disabled="period?.is_closed || w.is_permanently_expelled"
              @click="openSanction(w)"
            >
              제재
            </button>
          </div>
        </li>
        <li v-if="!filteredWorkers.length" class="worker-card empty-card">검색 결과가 없습니다.</li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import FunctionalEvalWorkspace from "@/components/functional-eval/FunctionalEvalWorkspace.vue";
import type { Criterion } from "@/components/functional-eval/EvalAssessmentSheet.vue";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { api } from "@/services/api";
import { countIncompleteWorkers } from "@/utils/functionalEvalCompletion";

type MainTab = "functional" | "safety" | "sanctions";
type EvalType = "FUNCTIONAL" | "SAFETY";

interface AssessmentBrief {
  scores: Record<string, string>;
  total_score: number;
  max_score: number;
  grade_code: string;
  grade_label: string;
  is_complete: boolean;
}

interface EvalCatalogBlock {
  title: string;
  criteria: Criterion[];
  max_score: number;
}

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
  last_attendance_date?: string | null;
  attendance_row_count?: number;
}

interface ViolationItem {
  code: string;
  category: string;
  category_label: string;
  label: string;
}

interface Worker {
  id: number;
  row_no: number;
  name: string;
  sanction_status: string;
  sanction_status_label: string;
  is_permanently_expelled: boolean;
  history_visible: boolean;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
}

interface SanctionRow {
  id: number;
  violation_label: string;
  sanction_result_label: string;
  strike_number: number;
  created_at: string;
  from_prior_period?: boolean;
}

const { isMobileViewport } = useMobileViewport();

const activeTab = ref<MainTab>("functional");
const focusWorkerId = ref<number | null>(null);
const evalCatalog = ref<{ FUNCTIONAL: EvalCatalogBlock; SAFETY: EvalCatalogBlock } | null>(null);
const period = ref<Period | null>(null);
const attendanceMessage = ref("");
const workers = ref<Worker[]>([]);
const violations = ref<ViolationItem[]>([]);
const selectedWorker = ref<Worker | null>(null);
const historyWorker = ref<Worker | null>(null);
const historyData = ref<{
  history_visible: boolean;
  message?: string;
  sanctions: SanctionRow[];
  prior_sanctions: SanctionRow[];
  mileage: { message?: string; points?: number };
} | null>(null);
const saving = ref(false);
const error = ref("");
const workerSearch = ref("");
const form = reactive({ violation_code: "", note: "" });

const currentEvalType = computed<EvalType>(() => (activeTab.value === "safety" ? "SAFETY" : "FUNCTIONAL"));

const evalTabTitle = computed(() => {
  const block = evalCatalog.value?.[currentEvalType.value];
  return block?.title || (activeTab.value === "safety" ? "2-2 안전 인사고과" : "2-1 기능 인사고과");
});

const evalCriteria = computed(() => evalCatalog.value?.[currentEvalType.value]?.criteria || []);

const incompleteCount = computed(() => countIncompleteWorkers(workers.value));

const filteredWorkers = computed(() => {
  const q = workerSearch.value.toLowerCase();
  if (!q) return workers.value;
  return workers.value.filter((w) => w.name.toLowerCase().includes(q));
});

const groupedViolations = computed(() => {
  const map = new Map<string, { category: string; label: string; items: ViolationItem[] }>();
  for (const item of violations.value) {
    if (!map.has(item.category)) {
      map.set(item.category, { category: item.category, label: item.category_label, items: [] });
    }
    map.get(item.category)!.items.push(item);
  }
  return Array.from(map.values());
});

const allHistorySanctions = computed(() => {
  if (!historyData.value?.history_visible) return [];
  return [...(historyData.value.prior_sanctions || []), ...(historyData.value.sanctions || [])];
});

function statusClass(status: string) {
  if (status.includes("EXPULSION") || status.includes("BAN")) return "danger";
  if (status.includes("WARNING") || status.includes("TRAINING")) return "warn";
  return "normal";
}

function formatDate(v: string) {
  try {
    return new Date(v).toLocaleString("ko-KR");
  } catch {
    return v;
  }
}

function closePanels() {
  closeForm();
  closeHistory();
}

function onRequestSafety(workerId: number) {
  focusWorkerId.value = workerId;
  activeTab.value = "safety";
}

watch(activeTab, (tab, prev) => {
  closeForm();
  closeHistory();
  if (tab !== "safety" || prev === "safety") {
    focusWorkerId.value = null;
  }
});

function closeHistory() {
  historyWorker.value = null;
  historyData.value = null;
  if (!selectedWorker.value) {
    document.body.classList.remove("fe-sheet-open-body");
  }
}

async function loadCatalog() {
  const res = await api.get("/functional-eval/violation-catalog");
  violations.value = res.data.items || [];
  if (violations.value.length && !form.violation_code) {
    form.violation_code = violations.value[0].code;
  }
}

async function load() {
  error.value = "";
  attendanceMessage.value = "";
  const res = await api.get("/functional-eval/my-site/workers");
  period.value = res.data.period;
  workers.value = res.data.items || [];
  attendanceMessage.value = res.data.attendance_message || "";
}

async function openHistory(worker: Worker) {
  historyWorker.value = worker;
  selectedWorker.value = null;
  error.value = "";
  const res = await api.get(`/functional-eval/workers/${worker.id}/history`);
  historyData.value = res.data;
  if (isMobileViewport.value) {
    document.body.classList.add("fe-sheet-open-body");
  }
}

function openSanction(worker: Worker) {
  selectedWorker.value = worker;
  historyWorker.value = null;
  form.note = "";
  error.value = "";
  if (isMobileViewport.value) {
    document.body.classList.add("fe-sheet-open-body");
  }
}

function closeForm() {
  selectedWorker.value = null;
  if (!historyWorker.value) {
    document.body.classList.remove("fe-sheet-open-body");
  }
}

async function submitSanction() {
  if (!selectedWorker.value) return;
  saving.value = true;
  error.value = "";
  try {
    await api.post("/functional-eval/sanctions", {
      worker_id: selectedWorker.value.id,
      violation_code: form.violation_code,
      note: form.note || null,
    });
    selectedWorker.value = null;
    document.body.classList.remove("fe-sheet-open-body");
    await load();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "제재 등록에 실패했습니다.";
  } finally {
    saving.value = false;
  }
}

async function loadEvalCatalog() {
  const res = await api.get("/functional-eval/eval-catalog");
  evalCatalog.value = res.data;
}

onMounted(async () => {
  await Promise.all([loadCatalog(), loadEvalCatalog(), load()]);
});
</script>

<style scoped>
.attendance-warn {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  color: #9a3412;
  font-size: 14px;
}

.fe-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.page-head-text {
  min-width: 0;
}

.page-title {
  margin: 0;
  font-size: 1.25rem;
}

.page-sub {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.badge {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  vertical-align: middle;
}

.badge.open {
  background: #dcfce7;
  color: #166534;
}

.badge.closed {
  background: #fee2e2;
  color: #991b1b;
}

.incomplete-count {
  margin-left: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
}

.btn-refresh {
  flex-shrink: 0;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}

.field {
  display: block;
  margin-top: 12px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 16px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
}

select.field-control {
  min-height: 48px;
}

textarea.field-control {
  resize: vertical;
  min-height: 80px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.actions-sticky {
  position: sticky;
  bottom: 0;
  padding-bottom: env(safe-area-inset-bottom, 0);
  background: linear-gradient(transparent, #fff 12px);
}

.touch-btn {
  flex: 1;
  min-height: 48px;
  font-size: 15px;
}

.touch-btn-inline {
  min-height: 44px;
  padding: 8px 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #e5e7eb;
  padding: 10px 8px;
  text-align: left;
}

.actions-cell {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.status-pill.danger {
  background: #fee2e2;
  color: #991b1b;
}

.status-pill.warn {
  background: #fef3c7;
  color: #92400e;
}

.status-pill.normal {
  background: #f1f5f9;
  color: #475569;
}

.status-pill.done {
  background: #dcfce7;
  color: #166534;
}

.status-pill.pending {
  background: #fef3c7;
  color: #92400e;
}

.fe-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.fe-tab {
  flex: 1;
  min-width: 100px;
  min-height: 44px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  color: #334155;
}

.fe-tab.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.eval-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.eval-actions .full-width {
  grid-column: 1 / -1;
}

.error {
  color: #b91c1c;
  margin-top: 8px;
}

.history-list {
  padding-left: 18px;
  font-size: 14px;
  margin: 12px 0 0;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.history-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.mileage-box {
  margin-top: 16px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 8px;
}

.mileage-box h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.tag {
  font-size: 11px;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 4px;
}

.warn {
  color: #991b1b;
}

.meta {
  color: #64748b;
  font-size: 12px;
  display: block;
  margin-top: 4px;
}

.workers-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.workers-head h2 {
  margin: 0;
  font-size: 1.05rem;
}

.count {
  color: #64748b;
  font-weight: 500;
}

.worker-search {
  max-width: 100%;
}

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 24px;
}

.desktop-only {
  display: block;
}

.mobile-only {
  display: none;
}

.worker-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.worker-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fafafa;
}

.worker-card-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.worker-no {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.worker-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.worker-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.worker-card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.card-btn {
  min-height: 44px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.card-btn-secondary {
  background: #fff;
  border-color: #cbd5e1;
  color: #334155;
}

.card-btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.card-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.empty-card {
  text-align: center;
  color: #64748b;
  background: #fff;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 0;
}

@media (max-width: 768px) {
  .desktop-only {
    display: none;
  }

  .mobile-only {
    display: flex;
  }

  .page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .btn-refresh {
    width: 100%;
    min-height: 44px;
  }

  .workers-panel {
    padding: 12px;
  }
}
</style>

<!-- 바텀시트: Teleport 콘텐츠는 scoped 밖 전역 클래스 -->
<style>
.fe-sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 400;
  background: rgba(15, 23, 42, 0.45);
}

.fe-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 410;
  max-height: min(88vh, 640px);
  overflow-y: auto;
  border-radius: 16px 16px 0 0;
  margin: 0;
  padding: 12px 16px calc(16px + env(safe-area-inset-bottom, 0));
  box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.15);
  transform: translateY(100%);
  transition: transform 0.22s ease;
}

.fe-sheet.fe-sheet-open {
  transform: translateY(0);
}

.fe-sheet-handle {
  width: 40px;
  height: 4px;
  background: #cbd5e1;
  border-radius: 999px;
  margin: 0 auto 12px;
}

body.fe-sheet-open-body {
  overflow: hidden;
}
</style>
