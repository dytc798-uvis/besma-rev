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

      <div class="risk-scale" aria-label="적용 위험성 구간">
        <strong>{{ riskBasis }}</strong>
        <span
          v-for="band in riskBands"
          :key="`${band.range}-${band.label}`"
          class="risk-band"
          :data-tone="band.tone"
        >
          {{ band.range }} {{ band.label }}
        </span>
        <small v-if="usesCompanyRiskStandard" class="visual-note">색상은 화면 구분용</small>
      </div>

      <div class="filters" :class="{ 'site-filters': Boolean(designation) }">
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
        <span class="result-summary">
          총 {{ total }}건
          <small v-if="accidentCount > 0">현재 목록 사고사례 {{ accidentCount }}건</small>
        </span>
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
              <th>위험수준</th>
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
              <td class="hazard-cell">
                <span v-if="isAccidentCase(row)" class="accident-badge">사고사례</span>
                <span>{{ hazardText(row) }}</span>
              </td>
              <td>{{ row.counterplan }}</td>
              <td class="score-cell">{{ displayScore(row.display_f) }}</td>
              <td class="score-cell">{{ displayScore(row.display_s) }}</td>
              <td class="score-cell">{{ displayScore(row.display_r) }}</td>
              <td class="grade-cell" :data-tone="gradeTone(row.risk_grade)">{{ row.risk_grade || "-" }}</td>
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
              <td :class="{ 'accident-note': isAccidentCase(row) }">{{ row.note || "-" }}</td>
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
        <p class="print-scale">위험성 구간: {{ riskBandSummary }}</p>
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
            <th>위험수준</th>
            <th>개선 담당자</th>
            <th>개선 확인자</th>
            <th>비고</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in printRows" :key="`print-${row.risk_revision_id}`">
            <td>{{ row.unit_work || row.work_category }}</td>
            <td>{{ row.process }}</td>
            <td class="hazard-cell">
              <span v-if="isAccidentCase(row)" class="accident-badge">사고사례</span>
              <span>{{ hazardText(row) }}</span>
            </td>
            <td>{{ row.counterplan }}</td>
            <td>{{ displayScore(row.display_f) }}</td>
            <td>{{ displayScore(row.display_s) }}</td>
            <td>{{ displayScore(row.display_r) }}</td>
            <td class="grade-cell" :data-tone="gradeTone(row.risk_grade)">{{ row.risk_grade || "-" }}</td>
            <td>{{ row.improvement_owner_name || "-" }}</td>
            <td>{{ row.improvement_verifier_name || "-" }}</td>
            <td :class="{ 'accident-note': isAccidentCase(row) }">{{ row.note || "-" }}</td>
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
const accidentCount = computed(() => rows.value.filter(isAccidentCase).length);
const companyRiskBands = [
  { range: "1–3", label: "무시", tone: "neutral" },
  { range: "4–6", label: "미미", tone: "safe" },
  { range: "7–8", label: "경미", tone: "watch" },
  { range: "9–12", label: "상당", tone: "elevated" },
  { range: "14–15", label: "중대", tone: "high" },
  { range: "16–20", label: "허용불가", tone: "critical" },
];
const usesCompanyRiskStandard = computed(() => evaluationMethod.value === "회사 4×5");
const riskBands = computed(() => (usesCompanyRiskStandard.value ? companyRiskBands : []));
const riskBasis = computed(() => (
  usesCompanyRiskStandard.value
    ? "BTMS-PS-002 기준 4×5"
    : `${evaluationMethod.value} — 승인 절차 기준 확인 필요`
));
const riskBandSummary = computed(() => (
  usesCompanyRiskStandard.value
    ? riskBands.value.map((band) => `${band.range} ${band.label}`).join(" · ")
    : "승인 절차 기준 확인 필요"
));

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

function gradeTone(grade: string): string {
  if (grade === "허용불가") return "critical";
  if (grade === "중대" || grade.startsWith("CⅠ") || grade === "상") return "high";
  if (grade === "상당") return "elevated";
  if (grade.startsWith("CⅡ")) return "medium";
  if (grade === "경미" || grade === "중") return "watch";
  if (grade === "미미" || grade === "하") return "safe";
  return "neutral";
}

const accidentPrefix = "(사고사례)";

function isAccidentCase(row: RiskLibraryItem): boolean {
  return (row.risk_factor || "").trim().startsWith(accidentPrefix);
}

function hazardText(row: RiskLibraryItem): string {
  const value = (row.risk_factor || "").trim();
  return isAccidentCase(row) ? value.slice(accidentPrefix.length).trim() : value;
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
.risk-scale { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 12px; padding: 8px 10px; border: 1px solid #d7dce2; border-radius: 5px; background: #fafbfc; color: #374151; font-size: 12px; }
.risk-scale > strong { margin-right: 3px; }
.risk-band { border: 1px solid #c7ced6; border-radius: 999px; padding: 2px 7px; white-space: nowrap; }
.visual-note { margin-left: auto; color: #6b7280; font-size: 11px; }
.scope-badge strong, .scope-badge span { display: block; }
.scope-badge span { margin-top: 3px; color: #59636e; font-size: 12px; }
.filters { display: grid; grid-template-columns: 180px minmax(360px, 1fr) 180px 150px auto; gap: 10px; align-items: end; margin-top: 16px; }
.filters.site-filters { grid-template-columns: minmax(360px, 1fr) 200px 160px 150px; }
.filters label, .designation-grid label { display: flex; flex-direction: column; gap: 5px; color: #374151; font-size: 13px; }
input, select { min-height: 36px; border: 1px solid #b8c0ca; border-radius: 4px; padding: 6px 8px; background: #fff; color: #111827; }
input[readonly] { background: #f5f5f5; }
.btn { min-height: 36px; border: 1px solid #2f5f85; border-radius: 4px; padding: 7px 12px; background: #2f5f85; color: #fff; cursor: pointer; }
.btn.secondary { background: #fff; color: #273746; border-color: #aeb7c1; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.actions { justify-content: flex-end; margin-top: 12px; }
.actions > span:first-child { margin-right: auto; font-weight: 600; }
.result-summary { display: inline-flex; align-items: center; gap: 8px; }
.result-summary small { border-left: 1px solid #c7ced6; padding-left: 8px; color: #9a3412; font-size: 12px; font-weight: 700; }
.print-hint { color: #8a5a00; font-size: 12px; }
.api-error { margin-top: 10px; padding: 8px 10px; border: 1px solid #e4a3a3; background: #fff3f3; color: #8b1f1f; }
.designation-card { border-left: 4px solid #5d7f98; }
.section-title p { margin-top: 3px; color: #59636e; font-size: 13px; }
.designation-grid { display: grid; grid-template-columns: repeat(3, minmax(150px, 1fr)) 2fr; gap: 10px; margin-top: 12px; }
.table-wrap { max-height: 650px; overflow: auto; }
.risk-table { width: 100%; min-width: 1240px; border-collapse: collapse; table-layout: fixed; }
.risk-table th, .risk-table td { border: 1px solid #aeb7c1; padding: 7px; font-size: 12px; line-height: 1.45; vertical-align: top; overflow-wrap: anywhere; }
.risk-table th { position: sticky; top: 0; z-index: 1; background: #e8edf2; text-align: center; }
.risk-table th:nth-child(1) { width: 7.5%; }
.risk-table th:nth-child(2) { width: 8.5%; }
.risk-table th:nth-child(3) { width: 19.5%; }
.risk-table th:nth-child(4) { width: 21.5%; }
.risk-table th:nth-child(5), .risk-table th:nth-child(6), .risk-table th:nth-child(7) { width: 3%; }
.risk-table th:nth-child(8) { width: 7%; }
.risk-table th:nth-child(9), .risk-table th:nth-child(10) { width: 7%; }
.risk-table th:nth-child(11) { width: 7%; }
.risk-table th:nth-child(12) { width: 6%; }
.selected { background: #f0f6fb; }
.score-cell, .grade-cell, .save-cell { text-align: center; vertical-align: middle !important; }
.grade-cell, .risk-band { font-weight: 700; }
[data-tone="neutral"] { background: #f3f4f6; color: #374151; }
[data-tone="safe"] { background: #e5f2df; color: #28551e; }
[data-tone="watch"] { background: #fff2cc; color: #664d03; }
[data-tone="medium"] { background: #dedede; color: #3f3f46; }
[data-tone="elevated"] { background: #fce4d6; color: #8a3b12; }
[data-tone="high"] { background: #f8cbad; color: #7c2d12; }
[data-tone="critical"] { background: #f4cccc; color: #8a1414; }
.assignment-input { width: 100%; min-height: 30px; padding: 4px 5px; }
.inline-save { width: 100%; border: 1px solid #8294a3; border-radius: 3px; padding: 5px 4px; background: #fff; cursor: pointer; }
.hazard-cell { position: relative; }
.accident-badge { display: inline-block; margin: 0 5px 3px 0; border: 1px solid #d97706; border-radius: 999px; padding: 1px 6px; background: #fff7ed; color: #9a3412; font-size: 10px; font-weight: 800; white-space: nowrap; }
.accident-note { background: #fff7ed; color: #9a3412; font-weight: 700; text-align: center; }
.loading, .empty { padding: 24px !important; text-align: center; color: #66717c; }
.paging { justify-content: flex-end; margin-top: 10px; }
.print-only { display: none; }

@media (max-width: 1100px) {
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filters.site-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .search-btn { width: 100%; }
  .designation-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .title-row, .section-title { align-items: stretch; flex-direction: column; }
  .scope-badge { min-width: 0; text-align: left; }
  .filters, .filters.site-filters, .designation-grid { grid-template-columns: 1fr; }
  .actions { align-items: stretch; flex-wrap: wrap; }
  .actions .btn { flex: 1 1 auto; }
}

@media print {
  .no-print, .result-card { display: none !important; }
  .print-only { display: block !important; }
  .print-sheet, .print-sheet * { visibility: visible !important; }
  .print-sheet { position: absolute; inset: 0 auto auto 0; width: 100%; background: #fff; }
  .print-sheet header { margin-bottom: 10px; }
  .print-sheet h2 { text-align: center; font-size: 20px; }
  .print-meta { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px 20px; margin-top: 8px; font-size: 11px; }
  .print-scale { margin: 7px 0 0; text-align: center; font-size: 9px; color: #333; }
  .print-sheet .risk-table { min-width: 0; }
  .risk-table thead { display: table-header-group; }
  .risk-table tr { break-inside: avoid; }
  .risk-table th, .risk-table td { padding: 4px; font-size: 9px; }
  .risk-table th { position: static; background: #ececec !important; }
  .accident-badge { border-color: #777; background: #fff !important; color: #222; font-size: 8px; }
  .accident-note { background: #fff !important; color: #222; }
}
</style>

<style>
@page risk-library {
  size: A3 landscape;
  margin: 10mm;
}

@media print {
  .site-shell .layout-sidebar,
  .site-shell .layout-header,
  .site-shell .notice-ticker,
  .layout-root .role-preview-banner {
    display: none !important;
  }
  .site-shell,
  .site-shell .layout-content,
  .site-shell .layout-main {
    display: block !important;
    width: 100% !important;
    min-width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
  }
  .risk-library-page .print-sheet,
  .risk-library-page .print-sheet * {
    visibility: visible !important;
  }
  .risk-library-page {
    page: risk-library;
  }
  .risk-library-page .print-sheet {
    page: risk-library;
  }
}
</style>
