<template>
  <div class="risk-library-page">
    <div class="card no-print">
      <h1>위험성평가 DB 조회</h1>
      <p class="helper">일반 입력: 빠른 검색 / Shift+Enter: 자연어 검색(beta)</p>

      <div class="search-row">
        <input
          v-model="keywordInput"
          class="search-input"
          type="text"
          placeholder="배관, 감전, 전주, 사다리, 추락 등으로 검색"
          @keydown="onKeywordKeydown"
        />
        <button class="btn" :disabled="loading" @click="fetchNow('quick')">빠른 검색</button>
      </div>

      <p class="mode-helper">
        현재 모드:
        <span class="mode-badge">{{ modeLabel }}</span>
        <template v-if="activeMode === 'nlp_beta'">
          - AI 없이 키워드 분해 기반으로 유사 결과를 찾습니다
        </template>
      </p>

      <div class="filters">
        <label>
          작업군
          <input v-model="workCategoryFilter" type="text" placeholder="예: 배관 작업" />
        </label>
        <label>
          세부작업
          <input v-model="processFilter" type="text" placeholder="예: 배선 작업" />
        </label>
        <label>
          위험유형
          <select v-model="riskTypeFilter">
            <option value="">전체</option>
            <option v-for="t in riskTypeOptions" :key="t" :value="t">{{ t }}</option>
          </select>
        </label>
      </div>

      <div class="actions">
        <span>총 {{ total }}건</span>
        <button class="btn secondary" :disabled="loading || rows.length === 0" @click="printCurrentSearch">
          현재 검색결과 인쇄
        </button>
        <button
          class="btn secondary"
          :disabled="!selectedRow"
          @click="printSelectedRow"
        >
          선택 행 인쇄
        </button>
      </div>
    </div>

    <div class="card">
      <div v-if="loading" class="loading">불러오는 중...</div>
      <div v-else class="table-wrap">
        <table class="risk-table">
          <thead>
            <tr>
              <th>작업군</th>
              <th>세부 작업</th>
              <th>위험요인</th>
              <th>대책</th>
              <th>F</th>
              <th>S</th>
              <th>R</th>
              <th>비고</th>
              <th>출처</th>
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
              <td>
                <div v-if="isExpanded(row.risk_revision_id)">
                  {{ row.counterplan }}
                  <button class="inline-btn" @click.stop="toggleExpand(row.risk_revision_id)">접기</button>
                </div>
                <div v-else>
                  {{ shorten(row.counterplan) }}
                  <button
                    v-if="row.counterplan.length > 80"
                    class="inline-btn"
                    @click.stop="toggleExpand(row.risk_revision_id)"
                  >
                    펼치기
                  </button>
                </div>
              </td>
              <td>{{ row.risk_f }}</td>
              <td>{{ row.risk_s }}</td>
              <td>{{ row.risk_r }}</td>
              <td>{{ row.note || "-" }}</td>
              <td>{{ renderSourceLabel(row) }}</td>
            </tr>
            <tr v-if="rows.length === 0">
              <td colspan="9" class="empty">검색 결과가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="paging no-print">
        <button class="btn secondary" :disabled="offset === 0 || loading" @click="goPrev">이전</button>
        <span>{{ pageLabel }}</span>
        <button class="btn secondary" :disabled="loading || offset + limit >= total" @click="goNext">
          다음
        </button>
      </div>
    </div>

    <div class="print-only">
      <h2>위험성평가 DB 인쇄</h2>
      <p>검색어: {{ keywordInput || "(없음)" }}</p>
      <table class="risk-table">
        <thead>
          <tr>
            <th>작업군</th>
            <th>세부 작업</th>
            <th>위험요인</th>
            <th>대책</th>
            <th>F</th>
            <th>S</th>
            <th>R</th>
            <th>비고</th>
            <th>출처</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in printRows" :key="`print-${row.risk_revision_id}`">
            <td>{{ row.unit_work || row.work_category }}</td>
            <td>{{ row.process }}</td>
            <td>{{ row.risk_factor }}</td>
            <td>{{ row.counterplan }}</td>
            <td>{{ row.risk_f }}</td>
            <td>{{ row.risk_s }}</td>
            <td>{{ row.risk_r }}</td>
            <td>{{ row.note || "-" }}</td>
            <td>{{ renderSourceLabel(row) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  fetchRiskLibrary,
  type RiskLibraryItem,
  type RiskSearchMode,
} from "@/services/riskLibrary";

const riskTypeOptions = ["추락", "감전", "낙하", "협착", "끼임", "화재"];
const limit = 30;

const keywordInput = ref("");
const workCategoryFilter = ref("");
const processFilter = ref("");
const riskTypeFilter = ref("");
const activeMode = ref<RiskSearchMode>("quick");

const loading = ref(false);
const total = ref(0);
const offset = ref(0);
const rows = ref<RiskLibraryItem[]>([]);
const selectedRow = ref<RiskLibraryItem | null>(null);
const expandedIds = ref<Set<number>>(new Set());
const printRows = ref<RiskLibraryItem[]>([]);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const pageLabel = computed(() => {
  if (total.value === 0) return "0 / 0";
  const start = offset.value + 1;
  const end = Math.min(offset.value + limit, total.value);
  return `${start}-${end} / ${total.value}`;
});

function buildQuery() {
  const mergedQuery = [keywordInput.value.trim(), processFilter.value.trim()]
    .filter(Boolean)
    .join(" ")
    .trim();
  return {
    query: mergedQuery || undefined,
    mode: activeMode.value,
    unit_work: workCategoryFilter.value.trim() || undefined,
    risk_type: riskTypeFilter.value || undefined,
    limit,
    offset: offset.value,
  };
}

const modeLabel = computed(() =>
  activeMode.value === "nlp_beta" ? "자연어 검색(beta)" : "빠른 검색",
);

function normalizeSourceName(fileName: string | null | undefined): string {
  const raw = (fileName || "").trim();
  if (!raw) return "";
  if (
    raw.includes("최초위험성평가 표준 모델(배포용).xlsx")
    || raw.includes("부현전기 최초위험성평가 표준 모델rev02")
  ) {
    return "위험성평가표준모델";
  }
  return raw;
}

function renderSourceLabel(row: RiskLibraryItem): string {
  const sourceFile = normalizeSourceName(row.source_file);
  const sourceSheet = (row.source_sheet || "").trim();
  const hasRow = row.source_row != null;
  if (!sourceFile && !sourceSheet && !hasRow) {
    return "근로자의견청취";
  }

  const left = sourceFile || "-";
  const middle = sourceSheet || "-";
  const right = hasRow ? `row ${row.source_row}` : "row -";
  if (left === "-" && middle === "-" && right === "row -") {
    return "근로자의견청취";
  }
  return `${left} / ${middle} / ${right}`;
}

async function fetchNow(mode: RiskSearchMode = activeMode.value) {
  activeMode.value = mode;
  loading.value = true;
  try {
    const data = await fetchRiskLibrary(buildQuery());
    total.value = data.total;
    rows.value = data.results;
    if (selectedRow.value) {
      const latest = data.results.find((x) => x.risk_revision_id === selectedRow.value?.risk_revision_id);
      selectedRow.value = latest ?? null;
    }
  } finally {
    loading.value = false;
  }
}

function queueDebouncedFetch() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    void fetchNow("quick");
  }, 320);
}

function onKeywordKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && e.shiftKey) {
    e.preventDefault();
    offset.value = 0;
    void fetchNow("nlp_beta");
    return;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    offset.value = 0;
    void fetchNow("quick");
  }
}

function goPrev() {
  offset.value = Math.max(0, offset.value - limit);
  void fetchNow(activeMode.value);
}

function goNext() {
  offset.value += limit;
  void fetchNow(activeMode.value);
}

function shorten(value: string): string {
  return value.length > 80 ? `${value.slice(0, 80)}...` : value;
}

function toggleExpand(revisionId: number) {
  const copied = new Set(expandedIds.value);
  if (copied.has(revisionId)) copied.delete(revisionId);
  else copied.add(revisionId);
  expandedIds.value = copied;
}

function isExpanded(revisionId: number): boolean {
  return expandedIds.value.has(revisionId);
}

async function printCurrentSearch() {
  loading.value = true;
  try {
    const data = await fetchRiskLibrary({
      ...buildQuery(),
      offset: 0,
      limit: 1000,
    });
    printRows.value = data.results;
  } finally {
    loading.value = false;
  }
  await nextTick();
  window.print();
}

async function printSelectedRow() {
  if (!selectedRow.value) return;
  printRows.value = [selectedRow.value];
  await nextTick();
  window.print();
}

watch([keywordInput, workCategoryFilter, processFilter, riskTypeFilter], () => {
  offset.value = 0;
  queueDebouncedFetch();
});

onMounted(() => {
  void fetchNow("quick");
});
</script>

<style scoped>
.risk-library-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
}
.helper {
  color: #4b5563;
  margin: 4px 0 10px;
}
.search-row {
  display: flex;
  gap: 8px;
}
.search-input {
  flex: 1;
  min-width: 200px;
}
.filters {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.filters label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
.actions {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.table-wrap {
  overflow: auto;
  max-height: 560px;
}
.risk-table {
  width: 100%;
  border-collapse: collapse;
}
.risk-table th,
.risk-table td {
  border: 1px solid #e5e7eb;
  padding: 8px;
  font-size: 13px;
  vertical-align: top;
}
.risk-table th {
  background: #f9fafb;
  position: sticky;
  top: 0;
}
.selected {
  background: #eef6ff;
}
.inline-btn {
  margin-left: 6px;
  border: none;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  font-size: 12px;
}
.btn {
  padding: 6px 10px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}
.btn.secondary {
  background: #fff;
  color: #1f2937;
  border-color: #d1d5db;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.paging {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.nl-placeholder {
  margin-top: 6px;
  color: #7c3aed;
  font-size: 13px;
}
.mode-helper {
  margin-top: 6px;
  color: #374151;
  font-size: 13px;
}
.mode-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
}
.matched {
  margin-top: 4px;
  color: #6b7280;
  font-size: 11px;
}
.loading,
.empty {
  text-align: center;
  color: #6b7280;
}
.print-only {
  display: none;
}

@media (max-width: 960px) {
  .filters {
    grid-template-columns: 1fr;
  }
}

@media print {
  .no-print {
    display: none !important;
  }
  .print-only {
    display: block;
  }
  .risk-table th,
  .risk-table td {
    font-size: 11px;
    padding: 4px;
  }
}
</style>
