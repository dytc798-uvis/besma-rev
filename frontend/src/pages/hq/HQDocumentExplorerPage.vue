<template>
  <div class="doc-explorer-page">
    <section class="hero-panel">
      <div class="hero-copy">
        <h1 class="page-title">문서 탐색</h1>
        <p class="page-subtitle">삼성관련·일반 양식(docs/base)과 현장 제출본(문서취합 저장소)을 탐색합니다.</p>
        <p class="page-note">기본 화면은 양식만 표시합니다. 검색은 파일명과 폴더 경로 기준입니다.</p>
      </div>
      <button type="button" class="law-registry-link" @click="openLawRegistry">법규등록부</button>
    </section>

    <section class="stitch-kpi-grid">
      <KpiCard label="전체 문서" :value="allDocuments.length" accent="blue" footer-note="실파일 스캔 기준" />
      <KpiCard label="현장 문서" :value="categoryCounts.field" accent="blue" footer-note="기본 업로드 문서" />
      <KpiCard label="양식" :value="categoryCounts.template" accent="slate" footer-note="삼성관련 양식" />
      <KpiCard label="일반 양식" :value="categoryCounts.general" accent="slate" footer-note="표준 현장 안전서류" />
    </section>

    <div class="explorer-layout">
      <aside class="left-rail">
        <BaseCard class="filter-panel">
          <template #head>
            <div class="panel-heading">
              <h2 class="panel-title">필터</h2>
              <span class="panel-help">MVP</span>
            </div>
          </template>

          <div class="filter-group">
            <div class="filter-label">문서 유형</div>
            <label v-for="option in docTypeOptions" :key="option.key" class="check-row">
              <input v-model="selectedDocTypes" type="checkbox" :value="option.key" />
              <span>{{ option.label }}</span>
            </label>
          </div>

          <div class="filter-group">
            <label class="filter-label" for="site-filter">폴더명</label>
            <select id="site-filter" v-model="selectedSite" class="filter-select">
              <option value="">전체 폴더 선택</option>
              <option v-for="site in siteOptions" :key="site" :value="site">{{ site }}</option>
            </select>
          </div>

          <div class="filter-group">
            <label class="filter-label" for="date-range">작성일자</label>
            <select id="date-range" v-model="selectedDateRange" class="filter-select">
              <option value="">전체 기간</option>
              <option v-for="option in dateRangeOptions" :key="option.key" :value="option.key">
                {{ option.label }}
              </option>
            </select>
          </div>

          <div class="filter-group">
            <div class="filter-label">태그</div>
            <div class="tag-cloud">
              <button
                v-for="tag in tagOptions"
                :key="tag"
                type="button"
                class="tag-pill"
                :class="{ active: selectedTags.includes(tag) }"
                @click="toggleTag(tag)"
              >
                {{ tag }}
              </button>
            </div>
          </div>
        </BaseCard>

        <BaseCard class="favorites-panel">
          <template #head>
            <div class="favorites-head">
              <h2 class="panel-title">최근 파일</h2>
            </div>
          </template>

          <button
            v-for="doc in favoriteDocuments"
            :key="doc.id"
            type="button"
            class="favorite-item"
            @click="noopAction('favorite', doc)"
          >
            <strong>{{ doc.name }}</strong>
            <span>{{ doc.relative_path }} · {{ formatDate(doc.modified_at) }}</span>
          </button>
          <p v-if="favoriteDocuments.length === 0" class="favorite-empty">현재 표시할 파일이 없습니다.</p>
        </BaseCard>
      </aside>

      <section class="main-rail">
        <BaseCard class="search-shell">
          <FilterBar class="search-row">
            <div class="search-input-wrap">
              <span class="search-icon" aria-hidden="true">⌕</span>
              <input
                v-model="searchText"
                type="search"
                class="search-input"
                placeholder="파일명, 경로로 검색"
                autocomplete="off"
                autocorrect="off"
                spellcheck="false"
                :readonly="searchFieldAutofillGuard"
                @focus="searchFieldAutofillGuard = false"
              />
            </div>
          </FilterBar>
        </BaseCard>

        <BaseCard class="results-shell">
          <template #head>
            <div class="results-head">
              <div class="tab-row">
                <button
                  v-for="tab in tabs"
                  :key="tab.key"
                  type="button"
                  class="tab-btn"
                  :class="{ active: activeTab === tab.key }"
                  @click="activeTab = tab.key"
                >
                  {{ tab.label }}
                </button>
              </div>
              <div class="results-meta">
                <span>총 {{ filteredDocuments.length }}건</span>
                <button type="button" class="sort-link" @click="noopAction('sort', activeTab)">최신순</button>
              </div>
            </div>
          </template>

          <p v-if="loading" class="state-msg">파일 목록을 불러오는 중입니다.</p>
          <p v-else-if="error" class="state-msg state-error">{{ error }}</p>

          <div v-else class="document-table-wrap">
            <table v-if="pagedDocuments.length > 0" class="document-table">
              <thead>
                <tr>
                  <th>유형</th>
                  <th>파일명</th>
                  <th>폴더</th>
                  <th>수정일</th>
                  <th>크기</th>
                  <th>작업</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in pagedDocuments" :key="doc.id">
                  <td>
                    <span class="category-badge" :class="`category-${doc.category}`">
                      {{ categoryLabel(doc.category) }}
                    </span>
                  </td>
                  <td class="doc-name-cell">{{ doc.name }}</td>
                  <td class="doc-folder-cell">{{ folderLabel(doc.relative_path) }}</td>
                  <td>{{ formatDate(doc.modified_at) }}</td>
                  <td>{{ formatSize(doc.size_bytes) }}</td>
                  <td class="doc-actions-cell">
                    <button
                      v-if="canInlineView(doc)"
                      type="button"
                      class="icon-btn"
                      @click="handleDocumentAction('view', doc)"
                    >
                      보기
                    </button>
                    <button type="button" class="icon-btn" @click="handleDocumentAction('download', doc)">다운로드</button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div v-if="pagedDocuments.length === 0" class="empty-state">
              업로드된 파일이 없거나 검색 조건과 일치하는 파일이 없습니다.
            </div>
          </div>

          <div v-if="totalPages > 1" class="pagination-row">
            <button
              v-for="page in totalPages"
              :key="`page-${page}`"
              type="button"
              class="page-btn"
              :class="{ active: currentPage === page }"
              @click="currentPage = page"
            >
              {{ page }}
            </button>
          </div>
        </BaseCard>

        <BaseCard v-if="shouldShowLawSection" class="law-results-shell">
          <template #head>
            <div class="results-head">
              <div>
                <h2 class="panel-title">관련 법령</h2>
                <p class="law-subtitle">같은 검색어로 찾은 조문 결과입니다.</p>
              </div>
              <div class="results-meta">
                <span>총 {{ lawResultsTotal }}건</span>
              </div>
            </div>
          </template>

          <p v-if="lawLoading" class="state-msg">관련 법령을 검색하는 중입니다.</p>
          <p v-else-if="lawError" class="state-msg state-error">{{ lawError }}</p>
          <p v-else-if="visibleLawResults.length === 0" class="state-msg">관련 법령 없음</p>

          <div v-else class="law-list">
            <article v-for="law in visibleLawResults" :key="law.article_item_id" class="law-card">
              <div class="law-top">
                <div class="law-heading">
                  <strong class="law-name">{{ law.law_name }}</strong>
                  <span class="law-type-badge">{{ law.law_type }}</span>
                </div>
                <span class="law-article">{{ law.article_display || "-" }}</span>
              </div>
              <p class="law-summary">{{ law.summary_title || "-" }}</p>
              <p class="law-action">
                <span class="law-label">조치</span>
                <span>{{ law.action_required || "-" }}</span>
              </p>
            </article>
          </div>

          <div v-if="canExpandLawResults" class="law-more-row">
            <button type="button" class="detail-btn" @click="showAllLawResults = !showAllLawResults">
              {{ showAllLawResults ? "접기" : "더보기" }}
            </button>
          </div>
        </BaseCard>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { AxiosError } from "axios";
import { useRoute } from "vue-router";
import { BaseCard, FilterBar, KpiCard } from "@/components/product";
import { api } from "@/services/api";
import { formatDateKst, toDate } from "@/utils/datetime";

type DocumentCategory = "field" | "template" | "general";
type ExplorerTab = "all" | DocumentCategory;

interface ExplorerDocument {
  id: string;
  name: string;
  relative_path: string;
  modified_at: string;
  size_bytes: number;
  extension: string;
  category: DocumentCategory;
}

interface ExplorerListResponse {
  items: ExplorerDocument[];
}

interface LawSearchResult {
  law_master_id: number;
  law_name: string;
  law_type: string;
  article_item_id: number;
  article_display: string | null;
  summary_title: string | null;
  action_required: string | null;
  countermeasure: string | null;
  penalty: string | null;
}

interface LawSearchResponse {
  total: number;
  limit: number;
  offset: number;
  items: LawSearchResult[];
}

const tabs: { key: ExplorerTab; label: string }[] = [
  { key: "template", label: "양식" },
  { key: "general", label: "일반 양식" },
  { key: "field", label: "현장문서" },
  { key: "all", label: "전체" },
];

const docTypeOptions: { key: DocumentCategory; label: string }[] = [
  { key: "template", label: "양식" },
  { key: "general", label: "일반 양식" },
  { key: "field", label: "현장문서" },
];

const dateRangeOptions = [
  { key: "1d", label: "1일" },
  { key: "7d", label: "1주일" },
  { key: "30d", label: "1개월" },
  { key: "90d", label: "3개월" },
  { key: "365d", label: "1년" },
] as const;

const tagOptions = ["#실파일", "#경로검색", "#MVP"];

const route = useRoute();

/** 모바일 브라우저가 첫 텍스트 필드에 로그인 ID 등을 자동완성하면 검색 API만 타고 목록이 비는 경우를 줄인다. */
const searchFieldAutofillGuard = ref(true);

const loading = ref(false);
const error = ref("");
const allDocuments = ref<ExplorerDocument[]>([]);
const searchResults = ref<ExplorerDocument[]>([]);
const lawResults = ref<LawSearchResult[]>([]);
const lawResultsTotal = ref(0);
const lawLoading = ref(false);
const lawError = ref("");
const showAllLawResults = ref(false);
const searchText = ref("");
const activeTab = ref<ExplorerTab>("template");
const selectedDocTypes = ref<DocumentCategory[]>(["template"]);
const selectedSite = ref("");
const selectedDateRange = ref("");
const selectedTags = ref<string[]>([]);
const currentPage = ref(1);
const pageSize = 20;

const siteOptions = computed(() => {
  const values = new Set<string>();
  for (const doc of allDocuments.value) {
    const dir = doc.relative_path.includes("/") ? doc.relative_path.slice(0, doc.relative_path.lastIndexOf("/")) : "/";
    values.add(dir || "/");
  }
  return Array.from(values).sort((a, b) => a.localeCompare(b, "ko"));
});

const categoryCounts = computed(() => ({
  field: allDocuments.value.filter((doc) => doc.category === "field").length,
  template: allDocuments.value.filter((doc) => doc.category === "template").length,
  general: allDocuments.value.filter((doc) => doc.category === "general").length,
}));

const favoriteDocuments = computed(() => allDocuments.value.slice(0, 4));
const shouldShowLawSection = computed(() => searchText.value.trim().length > 0);
const visibleLawResults = computed(() =>
  showAllLawResults.value ? lawResults.value : lawResults.value.slice(0, 5),
);
const canExpandLawResults = computed(() => lawResults.value.length > 5);

const filteredDocuments = computed(() => {
  let rows = searchText.value.trim() ? searchResults.value : allDocuments.value;
  rows = rows.filter((doc) => selectedDocTypes.value.includes(doc.category));
  if (activeTab.value !== "all") {
    rows = rows.filter((doc) => doc.category === activeTab.value);
  }
  if (selectedSite.value) {
    rows = rows.filter((doc) => {
      const dir = doc.relative_path.includes("/") ? doc.relative_path.slice(0, doc.relative_path.lastIndexOf("/")) : "/";
      return dir === selectedSite.value || doc.relative_path.startsWith(`${selectedSite.value}/`);
    });
  }
  if (selectedDateRange.value) {
    rows = rows.filter((doc) => isWithinDateRange(doc.modified_at, selectedDateRange.value));
  }
  return rows;
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredDocuments.value.length / pageSize)));
const pagedDocuments = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredDocuments.value.slice(start, start + pageSize);
});

watch([activeTab, selectedDocTypes, selectedSite, selectedDateRange, selectedTags], () => {
  currentPage.value = 1;
});

function resetExplorerUiState() {
  searchText.value = "";
  searchResults.value = [];
  lawResults.value = [];
  lawResultsTotal.value = 0;
  lawError.value = "";
  showAllLawResults.value = false;
  activeTab.value = "template";
  selectedDocTypes.value = ["template"];
  selectedSite.value = "";
  selectedDateRange.value = "";
  selectedTags.value = [];
  currentPage.value = 1;
  searchFieldAutofillGuard.value = true;
}

let searchAutofillUnlockTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => route.name,
  (name) => {
    if (name !== "site-document-explorer" && name !== "hq-safe-document-explorer") {
      return;
    }
    resetExplorerUiState();
    void loadAllDocuments();
    if (searchAutofillUnlockTimer) {
      clearTimeout(searchAutofillUnlockTimer);
    }
    searchAutofillUnlockTimer = setTimeout(() => {
      searchFieldAutofillGuard.value = false;
      searchAutofillUnlockTimer = null;
    }, 400);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (searchAutofillUnlockTimer) {
    clearTimeout(searchAutofillUnlockTimer);
    searchAutofillUnlockTimer = null;
  }
});

watch(searchText, async () => {
  currentPage.value = 1;
  showAllLawResults.value = false;
  await loadSearchResults();
});

async function loadAllDocuments() {
  loading.value = true;
  error.value = "";
  try {
    const res = await api.get<ExplorerListResponse>("/document-explorer/list");
    allDocuments.value = res.data.items ?? [];
    if (!searchText.value.trim()) {
      searchResults.value = [];
    }
  } catch {
    error.value = "문서 탐색 목록을 불러오지 못했습니다.";
    allDocuments.value = [];
    searchResults.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadSearchResults() {
  const q = searchText.value.trim();
  if (!q) {
    searchResults.value = [];
    lawResults.value = [];
    lawResultsTotal.value = 0;
    lawError.value = "";
    return;
  }

  loading.value = true;
  lawLoading.value = true;
  error.value = "";
  lawError.value = "";

  const [documentResult, lawResult] = await Promise.allSettled([
    api.get<ExplorerListResponse>("/document-explorer/search", { params: { q } }),
    api.get<LawSearchResponse>("/law-registry/search", {
      params: {
        q,
        limit: 20,
      },
    }),
  ]);

  if (documentResult.status === "fulfilled") {
    searchResults.value = documentResult.value.data.items ?? [];
  } else {
    error.value = "검색 결과를 불러오지 못했습니다.";
    searchResults.value = [];
  }

  if (lawResult.status === "fulfilled") {
    lawResults.value = lawResult.value.data.items ?? [];
    lawResultsTotal.value = lawResult.value.data.total ?? lawResults.value.length;
  } else {
    lawError.value = "관련 법령을 불러오지 못했습니다.";
    lawResults.value = [];
    lawResultsTotal.value = 0;
  }

  loading.value = false;
  lawLoading.value = false;
}

function folderLabel(relativePath: string) {
  const withoutSource = relativePath.replace(/^base\//, "").replace(/^field\//, "");
  const idx = withoutSource.lastIndexOf("/");
  if (idx <= 0) return "/";
  return withoutSource.slice(0, idx);
}

function canInlineView(doc: ExplorerDocument) {
  return doc.extension.toLowerCase() === ".pdf";
}

async function handleDocumentAction(action: "view" | "download", doc: ExplorerDocument) {
  const disposition = action === "view" ? "inline" : "attachment";
  try {
    const res = await api.get("/document-explorer/file", {
      params: { relative_path: doc.relative_path, disposition },
      responseType: "blob",
    });
    const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
    const blob = new Blob([res.data], { type: contentType });
    const url = window.URL.createObjectURL(blob);
    if (action === "view") {
      window.open(url, "_blank", "noopener");
      setTimeout(() => window.URL.revokeObjectURL(url), 5000);
      return;
    }
    const link = document.createElement("a");
    link.href = url;
    link.download = doc.name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (err: unknown) {
    const statusCode = (err as AxiosError)?.response?.status;
    if (statusCode === 401) {
      window.alert("인증이 만료되었거나 로그인 정보가 없습니다. 다시 로그인 후 시도해주세요.");
      return;
    }
    if (statusCode === 404) {
      window.alert(`파일이 존재하지 않습니다.\n경로: ${doc.relative_path}`);
      await loadAllDocuments();
      return;
    }
    window.alert("파일을 열거나 다운로드하지 못했습니다.");
  }
}

function toggleTag(tag: string) {
  selectedTags.value = selectedTags.value.includes(tag)
    ? selectedTags.value.filter((item) => item !== tag)
    : [...selectedTags.value, tag];
}

function categoryLabel(category: DocumentCategory) {
  if (category === "field") return "현장문서";
  if (category === "template") return "양식";
  return "일반 양식";
}

function formatDate(value: string) {
  return formatDateKst(value, value);
}

function formatSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 102.4) / 10} KB`;
  return `${Math.round(value / (1024 * 102.4)) / 10} MB`;
}

function isWithinDateRange(value: string, rangeKey: string) {
  const targetDate = toDate(value);
  if (!targetDate) return false;

  const rangeDaysMap: Record<string, number> = {
    "1d": 1,
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "365d": 365,
  };
  const days = rangeDaysMap[rangeKey];
  if (!days) return true;

  const now = Date.now();
  const diffMs = now - targetDate.getTime();
  return diffMs >= 0 && diffMs <= days * 24 * 60 * 60 * 1000;
}

function openLawRegistry() {
  window.alert("검색어를 입력하면 아래에서 관련 법령 결과를 함께 확인할 수 있습니다.");
}

function noopAction(action: string, payload: unknown) {
  console.log(`[document-explorer] ${action}`, payload);
}
</script>

<style scoped>
.doc-explorer-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
}

.page-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  color: #475569;
}

.page-note {
  margin: 8px 0 0;
  font-size: 12px;
  color: #64748b;
}

.law-registry-link {
  border: 0;
  background: transparent;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  padding: 6px 0;
}

.law-results-shell :deep(.body) {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.law-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
}

.law-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.law-card {
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fcfdff;
  padding: 16px;
}

.law-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.law-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.law-name {
  font-size: 15px;
  color: #0f172a;
}

.law-type-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
}

.law-article {
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
}

.law-summary,
.law-action {
  margin: 10px 0 0;
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
}

.law-label {
  display: inline-block;
  min-width: 28px;
  font-weight: 700;
  color: #0f172a;
}

.law-more-row {
  display: flex;
  justify-content: flex-end;
}

.explorer-layout {
  display: grid;
  grid-template-columns: minmax(320px, 360px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.left-rail,
.main-rail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-heading,
.favorites-head,
.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.panel-help {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.filter-panel :deep(.body) {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  line-height: 1.4;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #334155;
}

.filter-select,
.filter-input,
.search-input {
  width: 100%;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #fff;
  min-height: 44px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.35;
  color: #0f172a;
  box-sizing: border-box;
}

.filter-select {
  padding-right: 34px;
  text-overflow: ellipsis;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-pill {
  border: 1px solid #dbe2ea;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  padding: 7px 10px;
  font-size: 12px;
  cursor: pointer;
}

.tag-pill.active {
  background: #dbeafe;
  border-color: #93c5fd;
  color: #1d4ed8;
}

.favorites-panel {
  background: linear-gradient(180deg, #153a74 0%, #0f2d5c 100%);
  color: #fff;
}

.favorites-panel :deep(.body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.favorites-panel .panel-title {
  color: #fff;
}

.favorite-item {
  border: 0;
  background: transparent;
  color: inherit;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 0;
  text-align: left;
  cursor: default;
}

.favorite-item strong {
  font-size: 14px;
}

.favorite-item span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.favorite-empty {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.search-shell :deep(.body) {
  padding: 0;
}

.search-row {
  display: block;
}

.search-input-wrap {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #64748b;
}

.search-input {
  padding-left: 36px;
  height: 54px;
  background: #f8fafc;
}

.tab-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tab-btn {
  border: 0;
  background: transparent;
  border-bottom: 2px solid transparent;
  padding: 8px 4px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.tab-btn.active {
  border-bottom-color: #2563eb;
  color: #0f172a;
}

.results-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #64748b;
}

.state-msg {
  margin: 0;
  padding: 18px 0;
  color: #64748b;
  font-size: 14px;
}

.state-error {
  color: #b91c1c;
}

.sort-link {
  border: 0;
  background: transparent;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.document-table-wrap {
  overflow-x: auto;
}

.document-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.document-table th,
.document-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 12px 10px;
  text-align: left;
  vertical-align: middle;
}

.document-table th {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  background: #f8fafc;
}

.doc-name-cell {
  font-weight: 600;
  color: #0f172a;
  min-width: 220px;
}

.doc-folder-cell {
  color: #475569;
  min-width: 180px;
  word-break: break-all;
}

.doc-actions-cell {
  white-space: nowrap;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.category-field {
  background: #dbeafe;
  color: #1d4ed8;
}

.category-template {
  background: #e2e8f0;
  color: #475569;
}

.category-general {
  background: #dcfce7;
  color: #15803d;
}

.empty-state {
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  padding: 32px 20px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
  background: #f8fafc;
}

.icon-btn,
.detail-btn,
.page-btn {
  border: 1px solid #dbe2ea;
  border-radius: 10px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-weight: 600;
}

.icon-btn {
  padding: 10px 12px;
  font-size: 12px;
}

.detail-btn {
  padding: 10px 14px;
  font-size: 12px;
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.pagination-row {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 22px;
}

.page-btn {
  min-width: 40px;
  height: 40px;
  padding: 0 12px;
}

.page-btn.active {
  background: #16376d;
  border-color: #16376d;
  color: #fff;
}

@media (max-width: 1080px) {
  .explorer-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .hero-panel,
  .results-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
