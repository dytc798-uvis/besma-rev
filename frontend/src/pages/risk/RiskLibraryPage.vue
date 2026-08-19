<template>
  <div class="risk-library-page">
    <section class="card no-print">
      <div class="title-row">
        <div>
          <h1>위험성평가 데이터베이스</h1>
          <p class="helper">공종이나 작업명을 검색해 현장에 필요한 위험요인과 개선대책을 확인합니다.</p>
        </div>
        <div class="scope-badge">
          <strong>{{ scopeLabel }}</strong>
          <span>{{ evaluationMethod }}</span>
        </div>
      </div>

      <div class="filters">
        <label v-if="!designation">
          건설사
          <select v-model="selectedContractor">
            <option value="">통합 조회</option>
            <option
              v-for="option in contractorOptions"
              :key="option.contractor_key"
              :value="option.contractor_name"
            >
              {{ option.contractor_name }}
            </option>
          </select>
        </label>
        <label class="keyword-field">
          공종·세부작업·위험요인
          <input
            v-model="keywordInput"
            type="search"
            placeholder="예: 케이블 포설, 감전, 사다리"
            @keydown.enter.prevent="fetchNow"
          />
        </label>
        <label>
          공종
          <input v-model="workCategoryFilter" type="text" placeholder="예: 전기공사" />
        </label>
        <label>
          재해유형
          <select v-model="riskTypeFilter">
            <option value="">전체</option>
            <option v-for="type in riskTypeOptions" :key="type" :value="type">{{ type }}</option>
          </select>
        </label>
        <button class="btn search-btn" :disabled="loading" @click="fetchNow">검색</button>
      </div>

      <p v-if="apiError" class="api-error" role="alert">{{ apiError }}</p>

      <div class="actions">
        <span>총 {{ total }}건</span>
        <span v-if="!printScopeReady" class="print-hint">인쇄할 건설사를 먼저 선택해 주세요.</span>
        <button
          class="btn secondary"
          :disabled="loading || rows.length === 0 || !printScopeReady || !canPrint"
          @click="printCurrentSearch"
        >
          검색결과 인쇄
        </button>
        <button
          class="btn secondary"
          :disabled="!selectedRow || !printScopeReady || !canPrint"
          @click="printSelectedRow"
        >
          선택 항목 인쇄
        </button>
      </div>
    </section>

    <section v-if="designation" class="card designation-card no-print">
      <div class="section-title">
        <div>
          <h2>위험성평가 점검자·확인자 지정</h2>
          <p>{{ designation.site_name }}</p>
        </div>
        <button
          v-if="designation.can_edit"
          class="btn"
          :disabled="designationSaving"
          @click="saveDesignation"
        >
          {{ designationSaving ? "저장 중" : "지정 내용 저장" }}
        </button>
      </div>
      <div class="designation-grid">
        <label>
          점검자
          <input v-model="designationForm.inspector_name" :readonly="!designation.can_edit" />
        </label>
        <label>
          확인자
          <input v-model="designationForm.verifier_name" :readonly="!designation.can_edit" />
        </label>
        <label>
          지정일
          <input v-model="designationForm.appointed_on" type="date" :readonly="!designation.can_edit" />
        </label>
        <label class="designation-note">
          비고
          <input v-model="designationForm.note" :readonly="!designation.can_edit" />
        </label>
      </div>
      <p class="helper">점검자와 확인자는 각 위험요인의 개선 담당자·개선 확인자 기본값으로 사용됩니다.</p>
    </section>

    <section class="card result-card">
      <div v-if="loading" class="loading">불러오는 중...</div>
      <div v-else class="table-wrap">
        <table class="risk-table">
          <thead>
            <tr>
              <th>공종</th>
              <th>세부작업</th>
              <th>위험요인</th>
              <th>개선대책</th>
              <th>빈도</th>
              <th>강도</th>
              <th>점수</th>
              <th>등급</th>
              <th>개선 담당자</th>
              <th>개선 확인자</th>
              <th>비고</th>
              <th v-if="canEditAssignments" class="no-print">저장</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.risk_revision_id"
              :class="{ selected: selectedRow?.risk_revision_id === row.risk_revision_id }"
              @click="selectedRow = row"
            >
              <td>{{ row.unit_work || row.work_category }}</td>
              <td>{{ row.process }}</td>
              <td>{{ row.risk_factor }}</td>
              <td>{{ row.counterplan }}</td>
              <td class="score-cell">{{ displayScore(row.display_f) }}</td>
              <td class="score-cell">{{ displayScore(row.display_s) }}</td>
              <td class="score-cell">{{ displayScore(row.display_r) }}</td>
              <td class="grade-cell" :data-grade="row.risk_grade">{{ row.risk_grade || "-" }}</td>
              <td>
                <input
                  v-if="canEditAssignments"
                  v-model="row.improvement_owner_name"
                  class="assignment-input no-print"
                  @click.stop
                />
                <span :class="{ 'print-only': canEditAssignments }">{{ row.improvement_owner_name || "-" }}</span>
              </td>
              <td>
                <input
                  v-if="canEditAssignments"
                  v-model="row.improvement_verifier_name"
                  class="assignment-input no-print"
                  @click.stop
                />
                <span :class="{ 'print-only': canEditAssignments }">{{ row.improvement_verifier_name || "-" }}</span>
              </td>
              <td>{{ row.note || "-" }}</td>
              <td v-if="canEditAssignments" class="save-cell no-print">
                <button
                  class="inline-save"
                  :disabled="savingItemId === row.risk_item_id"
                  @click.stop="saveAssignment(row)"
                >
                  {{ savingItemId === row.risk_item_id ? "저장 중" : "저장" }}
                </button>
              </td>
            </tr>
            <tr v-if="rows.length === 0">
              <td :colspan="canEditAssignments ? 12 : 11" class="empty">검색 결과가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="paging no-print">
        <button class="btn secondary" :disabled="offset === 0 || loading" @click="goPrev">이전</button>
        <span>{{ pageLabel }}</span>
        <button class="btn secondary" :disabled="loading || offset + limit >= total" @click="goNext">다음</button>
      </div>
    </section>

    <section class="print-sheet print-only">
      <header>
        <h2>위험성평가 데이터베이스</h2>
        <div class="print-meta">
          <span>건설사: {{ scopeLabel }}</span>
          <span>평가기법: {{ evaluationMethod }}</span>
          <span v-if="designation?.site_name">현장명: {{ designation.site_name }}</span>
          <span>점검자: {{ designationForm.inspector_name || "-" }}</span>
          <span>확인자: {{ designationForm.verifier_name || "-" }}</span>
        </div>
      </header>
      <table class="risk-table">
        <thead>
          <tr>
            <th>공종</th>
            <th>세부작업</th>
            <th>위험요인</th>
            <th>개선대책</th>
            <th>빈도</th>
            <th>강도</th>
            <th>점수</th>
            <th>등급</th>
            <th>개선 담당자</th>
            <th>개선 확인자</th>
            <th>비고</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in printRows" :key="`print-${row.risk_revision_id}`">
            <td>{{ row.unit_work || row.work_category }}</td>
            <td>{{ row.process }}</td>
            <td>{{ row.risk_factor }}</td>
            <td>{{ row.counterplan }}</td>
            <td>{{ displayScore(row.display_f) }}</td>
            <td>{{ displayScore(row.display_s) }}</td>
            <td>{{ displayScore(row.display_r) }}</td>
            <td>{{ row.risk_grade || "-" }}</td>
            <td>{{ row.improvement_owner_name || "-" }}</td>
            <td>{{ row.improvement_verifier_name || "-" }}</td>
            <td>{{ row.note || "-" }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import {
  fetchRiskLibrary,
  saveRiskAssessmentDesignation,
  saveRiskLibrarySiteAssignment,
  type RiskAssessmentDesignation,
  type RiskLibraryContractorOption,
  type RiskLibraryItem,
} from "@/services/riskLibrary";

const riskTypeOptions = ["추락", "감전", "낙하", "협착", "끼임", "화재", "넘어짐", "베임"];
const limit = 50;

const keywordInput = ref("");
const workCategoryFilter = ref("");
const riskTypeFilter = ref("");
const selectedContractor = ref("");
const contractorOptions = ref<RiskLibraryContractorOption[]>([]);
const contractorName = ref<string | null>(null);
const evaluationMethod = ref("회사 4×5");
const designation = ref<RiskAssessmentDesignation | null>(null);
const canPrint = ref(true);

const loading = ref(false);
const designationSaving = ref(false);
const savingItemId = ref<number | null>(null);
const apiError = ref<string | null>(null);
const total = ref(0);
const offset = ref(0);
const rows = ref<RiskLibraryItem[]>([]);
const selectedRow = ref<RiskLibraryItem | null>(null);
const printRows = ref<RiskLibraryItem[]>([]);
const designationForm = reactive({
  inspector_name: "",
  verifier_name: "",
  appointed_on: "",
  note: "",
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const scopeLabel = computed(() => contractorName.value || selectedContractor.value || "통합 DB");
const printScopeReady = computed(() => Boolean(designation.value || selectedContractor.value));
const canEditAssignments = computed(() => Boolean(designation.value?.can_edit));
const pageLabel = computed(() => {
  if (total.value === 0) return "0 / 0";
  return `${offset.value + 1}-${Math.min(offset.value + limit, total.value)} / ${total.value}`;
});

function buildQuery() {
  return {
    query: keywordInput.value.trim() || undefined,
    mode: "quick" as const,
    unit_work: workCategoryFilter.value.trim() || undefined,
    risk_type: riskTypeFilter.value || undefined,
    contractor: selectedContractor.value || undefined,
    limit,
    offset: offset.value,
  };
}

function applyDesignation(value: RiskAssessmentDesignation | null) {
  designation.value = value;
  designationForm.inspector_name = value?.inspector_name || "";
  designationForm.verifier_name = value?.verifier_name || "";
  designationForm.appointed_on = value?.appointed_on || "";
  designationForm.note = value?.note || "";
}

function parseError(error: unknown): string {
  const ax = error as { response?: { status?: number; data?: { detail?: unknown } } };
  const statusCode = ax.response?.status;
  const detail = ax.response?.data?.detail;
  const message = typeof detail === "string" ? detail : "";
  if (statusCode === 403) return "위험성평가 데이터베이스 권한이 없습니다.";
  if (statusCode) return message ? `처리 실패 (${statusCode}): ${message}` : `처리 실패 (HTTP ${statusCode})`;
  return "서버에 연결할 수 없습니다.";
}

async function fetchNow() {
  loading.value = true;
  apiError.value = null;
  try {
    const data = await fetchRiskLibrary(buildQuery());
    total.value = data.total;
    rows.value = data.results;
    contractorOptions.value = data.contractor_options;
    contractorName.value = data.contractor_name;
    evaluationMethod.value = data.evaluation_method;
    canPrint.value = data.can_print;
    applyDesignation(data.designation);
    if (selectedRow.value) {
      selectedRow.value = data.results.find(
        (row) => row.risk_revision_id === selectedRow.value?.risk_revision_id,
      ) || null;
    }
  } catch (error: unknown) {
    apiError.value = parseError(error);
    total.value = 0;
    rows.value = [];
  } finally {
    loading.value = false;
  }
}

function queueFetch() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    offset.value = 0;
    void fetchNow();
  }, 320);
}

async function saveDesignation() {
  designationSaving.value = true;
  apiError.value = null;
  try {
    const saved = await saveRiskAssessmentDesignation({
      inspector_name: designationForm.inspector_name || null,
      verifier_name: designationForm.verifier_name || null,
      appointed_on: designationForm.appointed_on || null,
      note: designationForm.note || null,
    });
    applyDesignation(saved);
    rows.value = rows.value.map((row) => ({
      ...row,
      improvement_owner_name: row.improvement_owner_name || saved.inspector_name,
      improvement_verifier_name: row.improvement_verifier_name || saved.verifier_name,
    }));
  } catch (error: unknown) {
    apiError.value = parseError(error);
  } finally {
    designationSaving.value = false;
  }
}

async function saveAssignment(row: RiskLibraryItem) {
  savingItemId.value = row.risk_item_id;
  apiError.value = null;
  try {
    const saved = await saveRiskLibrarySiteAssignment(row.risk_item_id, {
      improvement_owner_name: row.improvement_owner_name || null,
      improvement_verifier_name: row.improvement_verifier_name || null,
    });
    row.improvement_owner_name = saved.improvement_owner_name;
    row.improvement_verifier_name = saved.improvement_verifier_name;
  } catch (error: unknown) {
    apiError.value = parseError(error);
  } finally {
    savingItemId.value = null;
  }
}

function goPrev() {
  offset.value = Math.max(0, offset.value - limit);
  void fetchNow();
}

function goNext() {
  offset.value += limit;
  void fetchNow();
}

function displayScore(value: number | null): string {
  return value == null ? "-" : String(value);
}

async function printCurrentSearch() {
  if (!printScopeReady.value || !canPrint.value) return;
  loading.value = true;
  apiError.value = null;
  try {
    const data = await fetchRiskLibrary({ ...buildQuery(), offset: 0, limit: 1000 });
    printRows.value = data.results;
  } catch (error: unknown) {
    apiError.value = parseError(error);
    return;
  } finally {
    loading.value = false;
  }
  await nextTick();
  window.print();
}

async function printSelectedRow() {
  if (!selectedRow.value || !printScopeReady.value || !canPrint.value) return;
  printRows.value = [selectedRow.value];
  await nextTick();
  window.print();
}

watch([keywordInput, workCategoryFilter, riskTypeFilter, selectedContractor], queueFetch);
onMounted(() => void fetchNow());
</script>

<style scoped>
.risk-library-page { display: flex; flex-direction: column; gap: 12px; }
.card { background: #fff; border: 1px solid #d7dce2; border-radius: 8px; padding: 16px; }
.title-row, .section-title, .actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h1, h2, p { margin: 0; }
h1 { font-size: 24px; }
h2 { font-size: 18px; }
.helper { margin-top: 5px; color: #59636e; font-size: 13px; }
.scope-badge { min-width: 180px; padding: 8px 12px; border: 1px solid #b9c7d5; background: #f5f8fb; text-align: right; }
.scope-badge strong, .scope-badge span { display: block; }
.scope-badge span { margin-top: 3px; color: #59636e; font-size: 12px; }
.filters { display: grid; grid-template-columns: 180px minmax(280px, 1fr) 180px 150px auto; gap: 10px; align-items: end; margin-top: 16px; }
.filters label, .designation-grid label { display: flex; flex-direction: column; gap: 5px; color: #374151; font-size: 13px; }
input, select { min-height: 36px; border: 1px solid #b8c0ca; border-radius: 4px; padding: 6px 8px; background: #fff; color: #111827; }
input[readonly] { background: #f5f5f5; }
.btn { min-height: 36px; border: 1px solid #2f5f85; border-radius: 4px; padding: 7px 12px; background: #2f5f85; color: #fff; cursor: pointer; }
.btn.secondary { background: #fff; color: #273746; border-color: #aeb7c1; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.actions { justify-content: flex-end; margin-top: 12px; }
.actions > span:first-child { margin-right: auto; font-weight: 600; }
.print-hint { color: #8a5a00; font-size: 12px; }
.api-error { margin-top: 10px; padding: 8px 10px; border: 1px solid #e4a3a3; background: #fff3f3; color: #8b1f1f; }
.designation-card { border-left: 4px solid #5d7f98; }
.section-title p { margin-top: 3px; color: #59636e; font-size: 13px; }
.designation-grid { display: grid; grid-template-columns: repeat(3, minmax(150px, 1fr)) 2fr; gap: 10px; margin-top: 12px; }
.table-wrap { max-height: 650px; overflow: auto; }
.risk-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.risk-table th, .risk-table td { border: 1px solid #aeb7c1; padding: 7px; font-size: 12px; line-height: 1.45; vertical-align: top; overflow-wrap: anywhere; }
.risk-table th { position: sticky; top: 0; z-index: 1; background: #e8edf2; text-align: center; }
.risk-table th:nth-child(1) { width: 10%; }
.risk-table th:nth-child(2) { width: 11%; }
.risk-table th:nth-child(3), .risk-table th:nth-child(4) { width: 22%; }
.risk-table th:nth-child(5), .risk-table th:nth-child(6), .risk-table th:nth-child(7), .risk-table th:nth-child(8) { width: 4%; }
.risk-table th:nth-child(9), .risk-table th:nth-child(10) { width: 7%; }
.risk-table th:nth-child(11) { width: 7%; }
.selected { background: #f0f6fb; }
.score-cell, .grade-cell, .save-cell { text-align: center; vertical-align: middle !important; }
.grade-cell[data-grade="상"] { background: #f6c7c7; color: #8a1414; font-weight: 700; }
.grade-cell[data-grade="중"] { background: #f8dfad; color: #704400; font-weight: 700; }
.grade-cell[data-grade="하"] { background: #dcefd7; color: #28551e; font-weight: 700; }
.assignment-input { width: 100%; min-height: 30px; padding: 4px 5px; }
.inline-save { border: 1px solid #8294a3; border-radius: 3px; padding: 5px 8px; background: #fff; cursor: pointer; }
.loading, .empty { padding: 24px !important; text-align: center; color: #66717c; }
.paging { justify-content: flex-end; margin-top: 10px; }
.print-only { display: none; }

@media (max-width: 1100px) {
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .search-btn { width: 100%; }
  .designation-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media print {
  @page { size: A3 landscape; margin: 10mm; }
  .no-print, .result-card { display: none !important; }
  .print-only { display: block !important; }
  .print-sheet header { margin-bottom: 10px; }
  .print-sheet h2 { text-align: center; font-size: 20px; }
  .print-meta { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px 20px; margin-top: 8px; font-size: 11px; }
  .risk-table th, .risk-table td { padding: 4px; font-size: 9px; }
  .risk-table th { position: static; background: #ececec !important; }
}
</style>
