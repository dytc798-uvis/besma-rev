<template>
  <div class="explorer-page">
    <section class="hero">
      <div>
        <p class="eyebrow">BESMA SEARCH</p>
        <h1>양식·법령 탐색</h1>
        <p>업무 양식과 현장 문서는 파일 내용까지, 법령은 조문과 조치사항을 별도 인덱스로 검색합니다.</p>
      </div>
    </section>

    <section class="domain-switch" aria-label="검색 대상">
      <button
        type="button"
        :class="{ active: activeDomain === 'documents' }"
        @click="activeDomain = 'documents'"
      >
        <span class="domain-icon">▤</span>
        <span><strong>양식·현장문서</strong><small>삼성관련 양식 · 일반 양식 · 현장 제출문서</small></span>
      </button>
      <button
        type="button"
        :class="{ active: activeDomain === 'laws' }"
        @click="activeDomain = 'laws'"
      >
        <span class="domain-icon">§</span>
        <span><strong>법령·조문</strong><small>법령명 · 조문 · 의무사항 · 벌칙</small></span>
      </button>
    </section>

    <BaseCard class="search-card">
      <div class="search-wrap">
        <span aria-hidden="true">⌕</span>
        <input
          v-model="searchText"
          type="search"
          :placeholder="searchPlaceholder"
          autocomplete="off"
          autocorrect="off"
          spellcheck="false"
          :readonly="searchFieldAutofillGuard"
          @focus="searchFieldAutofillGuard = false"
        />
        <button v-if="searchText" type="button" class="clear-btn" @click="searchText = ''">지우기</button>
      </div>
      <div class="keyword-row">
        <span>추천 검색어</span>
        <button v-for="keyword in suggestedKeywords" :key="keyword" type="button" @click="searchText = keyword">
          {{ keyword }}
        </button>
      </div>
    </BaseCard>

    <template v-if="activeDomain === 'documents'">
      <section class="kpi-grid">
        <KpiCard label="전체 문서" :value="allDocuments.length" accent="blue" footer-note="실파일 기준" />
        <KpiCard label="삼성관련 양식" :value="categoryCounts.template" accent="slate" footer-note="삼성인정제 양식" />
        <KpiCard label="일반 양식" :value="categoryCounts.general" accent="slate" footer-note="표준 안전서류" />
        <KpiCard label="현장 문서" :value="categoryCounts.field" accent="blue" footer-note="현장 제출본" />
      </section>

      <div class="document-layout">
        <aside>
          <BaseCard>
            <template #head><h2 class="card-title">문서 필터</h2></template>
            <div class="filter-stack">
              <div>
                <span class="filter-label">문서 유형</span>
                <label v-for="option in documentTypeOptions" :key="option.key" class="check-row">
                  <input v-model="selectedDocumentTypes" type="checkbox" :value="option.key" />
                  <span>{{ option.label }}</span>
                </label>
              </div>
              <label>
                <span class="filter-label">폴더</span>
                <select v-model="selectedFolder">
                  <option value="">전체 폴더</option>
                  <option v-for="folder in folderOptions" :key="folder" :value="folder">{{ folder }}</option>
                </select>
              </label>
              <label>
                <span class="filter-label">수정일</span>
                <select v-model="selectedDateRange">
                  <option value="">전체 기간</option>
                  <option value="7d">최근 1주</option>
                  <option value="30d">최근 1개월</option>
                  <option value="90d">최근 3개월</option>
                  <option value="365d">최근 1년</option>
                </select>
              </label>
            </div>
          </BaseCard>

          <BaseCard class="recent-card">
            <template #head><h2 class="card-title light">최근 문서</h2></template>
            <button
              v-for="document in recentDocuments"
              :key="document.id"
              type="button"
              class="recent-item"
              @click="handleDocumentAction(canInlineView(document) ? 'view' : 'download', document)"
            >
              <strong>{{ document.name }}</strong>
              <span>{{ categoryLabel(document.category) }} · {{ formatDate(document.modified_at) }}</span>
            </button>
            <p v-if="recentDocuments.length === 0" class="empty-light">표시할 문서가 없습니다.</p>
          </BaseCard>
        </aside>

        <BaseCard class="result-card">
          <template #head>
            <div class="result-head">
              <div class="sub-tabs">
                <button
                  v-for="tab in documentTabs"
                  :key="tab.key"
                  type="button"
                  :class="{ active: activeDocumentTab === tab.key }"
                  @click="activeDocumentTab = tab.key"
                >
                  {{ tab.label }}
                </button>
              </div>
              <span>{{ filteredDocuments.length }}건</span>
            </div>
          </template>

          <p v-if="documentLoading" class="state">문서 인덱스를 검색하는 중입니다.</p>
          <p v-else-if="documentError" class="state error">{{ documentError }}</p>
          <div v-else-if="pagedDocuments.length" class="document-list">
            <article v-for="document in pagedDocuments" :key="document.id" class="document-row">
              <div class="document-main">
                <div class="badge-row">
                  <span class="category-badge" :class="`category-${document.category}`">
                    {{ categoryLabel(document.category) }}
                  </span>
                  <span v-if="document.match_source === 'content'" class="content-badge">내용 일치</span>
                  <span v-else-if="searchText.trim()" class="metadata-badge">파일명·경로 일치</span>
                </div>
                <strong>{{ document.name }}</strong>
                <p v-if="document.snippet" class="snippet">{{ document.snippet }}</p>
                <p class="document-meta">
                  {{ folderLabel(document.relative_path) }} · {{ formatDate(document.modified_at) }} ·
                  {{ formatSize(document.size_bytes) }}
                </p>
              </div>
              <div class="actions">
                <button v-if="canInlineView(document)" type="button" @click="handleDocumentAction('view', document)">보기</button>
                <button type="button" class="primary" @click="handleDocumentAction('download', document)">다운로드</button>
              </div>
            </article>
          </div>
          <div v-else class="empty">
            <strong>{{ searchText.trim() ? "일치하는 문서가 없습니다." : "표시할 문서가 없습니다." }}</strong>
            <span v-if="searchText.trim()">파일명뿐 아니라 지원 형식의 문서 내용도 검색했습니다.</span>
          </div>

          <div v-if="documentTotalPages > 1" class="pagination">
            <button
              v-for="page in documentTotalPages"
              :key="page"
              type="button"
              :class="{ active: currentDocumentPage === page }"
              @click="currentDocumentPage = page"
            >
              {{ page }}
            </button>
          </div>
        </BaseCard>
      </div>
    </template>

    <template v-else>
      <div class="law-layout">
        <aside>
          <BaseCard>
            <template #head><h2 class="card-title">법령 필터</h2></template>
            <div class="law-filter-list">
              <button
                v-for="option in lawTypeOptions"
                :key="option.key"
                type="button"
                :class="{ active: selectedLawType === option.key }"
                @click="selectedLawType = option.key"
              >
                <span>{{ option.label }}</span>
                <small>{{ option.description }}</small>
              </button>
            </div>
          </BaseCard>
          <div class="law-guide">
            <strong>검색 안내</strong>
            <p>두세 개의 핵심어를 함께 입력하면 법령명, 조문, 조치사항, 키워드 일치도를 합산해 관련도순으로 표시합니다.</p>
            <p>법적 판단 전에는 반드시 최신 공식 원문을 다시 확인하세요.</p>
          </div>
        </aside>

        <BaseCard class="result-card law-results">
          <template #head>
            <div class="result-head">
              <div>
                <h2 class="card-title">법령·조문 검색결과</h2>
                <p>파일검색 결과에 묻히지 않도록 별도 목록으로 제공합니다.</p>
              </div>
              <span>{{ lawResultsTotal }}건</span>
            </div>
          </template>

          <div v-if="!searchText.trim()" class="law-empty">
            <span class="law-symbol">§</span>
            <strong>찾으려는 작업이나 위험요인을 입력하세요.</strong>
            <p>예: 밀폐공간 산소농도, 추락 안전난간, 위험성평가 근로자 참여</p>
          </div>
          <p v-else-if="lawLoading" class="state">법령 인덱스를 검색하는 중입니다.</p>
          <p v-else-if="lawError" class="state error">{{ lawError }}</p>
          <div v-else-if="visibleLawResults.length" class="law-list">
            <article v-for="law in visibleLawResults" :key="law.article_item_id" class="law-item">
              <div class="law-top">
                <div>
                  <div class="badge-row">
                    <span class="law-type">{{ lawTypeLabel(law.law_type) }}</span>
                    <span class="relevance">관련도 {{ Math.round(law.relevance) }}</span>
                  </div>
                  <strong>{{ law.law_name }}</strong>
                </div>
                <span class="article-label">{{ law.article_display || "조문 정보 없음" }}</span>
              </div>
              <h3>{{ law.summary_title || "요약 제목 없음" }}</h3>
              <div class="law-action">
                <span>필요 조치</span>
                <p>{{ law.action_required || "등록된 조치사항이 없습니다." }}</p>
              </div>
              <details v-if="law.countermeasure || law.penalty">
                <summary>대책·벌칙 상세보기</summary>
                <div v-if="law.countermeasure"><strong>대책</strong><p>{{ law.countermeasure }}</p></div>
                <div v-if="law.penalty"><strong>벌칙</strong><p>{{ law.penalty }}</p></div>
              </details>
            </article>
          </div>
          <div v-else class="empty">
            <strong>일치하는 법령·조문이 없습니다.</strong>
            <span>검색어를 줄이거나 작업명과 위험요인을 구분해 다시 입력해 보세요.</span>
          </div>

          <button
            v-if="lawResults.length > visibleLawLimit"
            type="button"
            class="more-btn"
            @click="visibleLawLimit += 10"
          >
            결과 더보기
          </button>
        </BaseCard>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { AxiosError } from "axios";
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { BaseCard, KpiCard } from "@/components/product";
import { api } from "@/services/api";
import { formatDateKst, toDate } from "@/utils/datetime";

type SearchDomain = "documents" | "laws";
type DocumentCategory = "field" | "template" | "general";
type DocumentTab = "all" | DocumentCategory;

interface ExplorerDocument {
  id: string;
  name: string;
  relative_path: string;
  modified_at: string;
  size_bytes: number;
  extension: string;
  category: DocumentCategory;
  relevance: number;
  snippet: string | null;
  match_source: "content" | "metadata" | null;
  index_status: string | null;
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
  relevance: number;
}

interface ExplorerListResponse { items: ExplorerDocument[] }
interface LawSearchResponse { total: number; limit: number; offset: number; items: LawSearchResult[] }

const route = useRoute();
const activeDomain = ref<SearchDomain>("documents");
const searchText = ref("");
const searchFieldAutofillGuard = ref(true);
const allDocuments = ref<ExplorerDocument[]>([]);
const documentSearchResults = ref<ExplorerDocument[]>([]);
const documentLoading = ref(false);
const documentError = ref("");
const lawResults = ref<LawSearchResult[]>([]);
const lawResultsTotal = ref(0);
const lawLoading = ref(false);
const lawError = ref("");
const activeDocumentTab = ref<DocumentTab>("all");
const selectedDocumentTypes = ref<DocumentCategory[]>(["template", "general"]);
const selectedFolder = ref("");
const selectedDateRange = ref("");
const selectedLawType = ref("");
const currentDocumentPage = ref(1);
const visibleLawLimit = ref(10);
const pageSize = 15;
let searchTimer: ReturnType<typeof setTimeout> | null = null;
let requestSequence = 0;
let autofillTimer: ReturnType<typeof setTimeout> | null = null;

const documentTabs = [
  { key: "all" as const, label: "전체" },
  { key: "template" as const, label: "삼성관련 양식" },
  { key: "general" as const, label: "일반 양식" },
  { key: "field" as const, label: "현장문서" },
];
const documentTypeOptions = documentTabs.filter((item) => item.key !== "all") as {
  key: DocumentCategory;
  label: string;
}[];
const lawTypeOptions = [
  { key: "", label: "전체 법령", description: "등록된 모든 법령·조문" },
  { key: "법", label: "법률", description: "산업안전보건법 등" },
  { key: "령", label: "시행령", description: "법률의 위임사항" },
  { key: "규칙", label: "시행규칙", description: "세부 절차와 서식" },
  { key: "고시", label: "고시·지침", description: "기술기준과 행정지침" },
];

const searchPlaceholder = computed(() =>
  activeDomain.value === "documents"
    ? "파일명, 폴더명 또는 문서 내용으로 검색"
    : "법령명, 작업명, 위험요인 또는 조치사항으로 검색",
);
const suggestedKeywords = computed(() =>
  activeDomain.value === "documents"
    ? ["TBM", "위험성평가", "안전교육", "작업계획서", "밀폐공간"]
    : ["추락 안전난간", "밀폐공간 산소농도", "보호구 지급", "위험성평가", "작업중지"],
);
const categoryCounts = computed(() => ({
  field: allDocuments.value.filter((item) => item.category === "field").length,
  template: allDocuments.value.filter((item) => item.category === "template").length,
  general: allDocuments.value.filter((item) => item.category === "general").length,
}));
const recentDocuments = computed(() => allDocuments.value.slice(0, 5));
const folderOptions = computed(() => {
  const folders = new Set(allDocuments.value.map((item) => folderLabel(item.relative_path)));
  return [...folders].filter((item) => item !== "/").sort((a, b) => a.localeCompare(b, "ko"));
});
const filteredDocuments = computed(() => {
  let rows = searchText.value.trim() ? documentSearchResults.value : allDocuments.value;
  rows = rows.filter((item) => selectedDocumentTypes.value.includes(item.category));
  if (activeDocumentTab.value !== "all") rows = rows.filter((item) => item.category === activeDocumentTab.value);
  if (selectedFolder.value) rows = rows.filter((item) => folderLabel(item.relative_path) === selectedFolder.value);
  if (selectedDateRange.value) rows = rows.filter((item) => isWithinDateRange(item.modified_at, selectedDateRange.value));
  return rows;
});
const documentTotalPages = computed(() => Math.max(1, Math.ceil(filteredDocuments.value.length / pageSize)));
const pagedDocuments = computed(() => {
  const start = (currentDocumentPage.value - 1) * pageSize;
  return filteredDocuments.value.slice(start, start + pageSize);
});
const visibleLawResults = computed(() => lawResults.value.slice(0, visibleLawLimit.value));

watch(
  () => route.name,
  (name) => {
    if (name !== "site-document-explorer" && name !== "hq-safe-document-explorer") return;
    resetPage();
    void loadDocuments();
    if (autofillTimer) clearTimeout(autofillTimer);
    autofillTimer = setTimeout(() => {
      searchFieldAutofillGuard.value = false;
      autofillTimer = null;
    }, 400);
  },
  { immediate: true },
);

watch([searchText, activeDomain, selectedLawType], () => {
  currentDocumentPage.value = 1;
  visibleLawLimit.value = 10;
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => void runActiveSearch(), 280);
});
watch([activeDocumentTab, selectedDocumentTypes, selectedFolder, selectedDateRange], () => {
  currentDocumentPage.value = 1;
});
watch(documentTotalPages, (pages) => {
  if (currentDocumentPage.value > pages) currentDocumentPage.value = pages;
});

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer);
  if (autofillTimer) clearTimeout(autofillTimer);
});

function resetPage() {
  activeDomain.value = "documents";
  searchText.value = "";
  documentSearchResults.value = [];
  lawResults.value = [];
  lawResultsTotal.value = 0;
  documentError.value = "";
  lawError.value = "";
  activeDocumentTab.value = "all";
  selectedDocumentTypes.value = ["template", "general"];
  selectedFolder.value = "";
  selectedDateRange.value = "";
  selectedLawType.value = "";
  currentDocumentPage.value = 1;
  visibleLawLimit.value = 10;
  searchFieldAutofillGuard.value = true;
}

async function loadDocuments() {
  documentLoading.value = true;
  documentError.value = "";
  try {
    const response = await api.get<ExplorerListResponse>("/document-explorer/list");
    allDocuments.value = response.data.items ?? [];
  } catch {
    allDocuments.value = [];
    documentError.value = "문서 목록을 불러오지 못했습니다.";
  } finally {
    documentLoading.value = false;
  }
}

async function runActiveSearch() {
  const sequence = ++requestSequence;
  const query = searchText.value.trim();
  if (!query) {
    documentSearchResults.value = [];
    lawResults.value = [];
    lawResultsTotal.value = 0;
    documentLoading.value = false;
    lawLoading.value = false;
    return;
  }
  if (activeDomain.value === "documents") {
    documentLoading.value = true;
    documentError.value = "";
    try {
      const response = await api.get<ExplorerListResponse>("/document-explorer/search", { params: { q: query } });
      if (sequence === requestSequence) documentSearchResults.value = response.data.items ?? [];
    } catch {
      if (sequence === requestSequence) {
        documentSearchResults.value = [];
        documentError.value = "문서 검색결과를 불러오지 못했습니다.";
      }
    } finally {
      if (sequence === requestSequence) documentLoading.value = false;
    }
    return;
  }

  lawLoading.value = true;
  lawError.value = "";
  try {
    const response = await api.get<LawSearchResponse>("/law-registry/search", {
      params: { q: query, law_type: selectedLawType.value || undefined, limit: 50 },
    });
    if (sequence === requestSequence) {
      lawResults.value = response.data.items ?? [];
      lawResultsTotal.value = response.data.total ?? lawResults.value.length;
    }
  } catch {
    if (sequence === requestSequence) {
      lawResults.value = [];
      lawResultsTotal.value = 0;
      lawError.value = "법령 검색결과를 불러오지 못했습니다.";
    }
  } finally {
    if (sequence === requestSequence) lawLoading.value = false;
  }
}

function folderLabel(relativePath: string) {
  const clean = relativePath.replace(/^base\//, "").replace(/^field\//, "");
  const index = clean.lastIndexOf("/");
  return index <= 0 ? "/" : clean.slice(0, index);
}
function categoryLabel(category: DocumentCategory) {
  if (category === "template") return "삼성관련 양식";
  if (category === "general") return "일반 양식";
  return "현장문서";
}
function lawTypeLabel(type: string) {
  return lawTypeOptions.find((item) => item.key === type)?.label || type || "법령";
}
function formatDate(value: string) {
  return formatDateKst(value, value);
}
function formatSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 102.4) / 10} KB`;
  return `${Math.round(value / (1024 * 102.4)) / 10} MB`;
}
function canInlineView(document: ExplorerDocument) {
  return document.extension.toLowerCase() === ".pdf";
}
function isWithinDateRange(value: string, key: string) {
  const date = toDate(value);
  if (!date) return false;
  const rangeDays: Record<string, number> = { "7d": 7, "30d": 30, "90d": 90, "365d": 365 };
  const days = rangeDays[key];
  if (!days) return true;
  const difference = Date.now() - date.getTime();
  return difference >= 0 && difference <= days * 86_400_000;
}

async function handleDocumentAction(action: "view" | "download", document: ExplorerDocument) {
  try {
    const response = await api.get("/document-explorer/file", {
      params: { relative_path: document.relative_path, disposition: action === "view" ? "inline" : "attachment" },
      responseType: "blob",
    });
    const blob = new Blob([response.data], {
      type: (response.headers["content-type"] as string | undefined) || "application/octet-stream",
    });
    const url = URL.createObjectURL(blob);
    if (action === "view") {
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      return;
    }
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = document.name;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  } catch (error: unknown) {
    const status = (error as AxiosError)?.response?.status;
    if (status === 401) window.alert("로그인이 만료되었습니다. 다시 로그인해주세요.");
    else if (status === 404) window.alert("파일이 존재하지 않습니다.");
    else window.alert("파일을 열거나 다운로드하지 못했습니다.");
  }
}
</script>

<style scoped>
.explorer-page { display: flex; flex-direction: column; gap: 20px; }
.hero h1 { margin: 2px 0 8px; font-size: clamp(27px, 4vw, 36px); color: #0f172a; letter-spacing: -.04em; }
.hero p { margin: 0; color: #64748b; font-size: 14px; }
.hero .eyebrow { color: #2563eb; font-size: 11px; font-weight: 800; letter-spacing: .14em; }
.domain-switch { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.domain-switch button { display: flex; align-items: center; gap: 14px; padding: 18px; border: 1px solid #dbe3ee; border-radius: 18px; background: #fff; text-align: left; color: #475569; cursor: pointer; }
.domain-switch button.active { border-color: #2563eb; background: linear-gradient(135deg, #eff6ff, #fff); box-shadow: 0 8px 24px rgba(37, 99, 235, .1); color: #0f172a; }
.domain-switch strong, .domain-switch small { display: block; }
.domain-switch strong { font-size: 16px; }
.domain-switch small { margin-top: 4px; color: #64748b; font-size: 12px; }
.domain-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 12px; background: #e2e8f0; font-size: 21px; font-weight: 800; }
.active .domain-icon { background: #2563eb; color: white; }
.search-card :deep(.body) { padding: 16px; }
.search-wrap { position: relative; display: flex; align-items: center; }
.search-wrap > span { position: absolute; left: 15px; color: #64748b; font-size: 18px; }
.search-wrap input { width: 100%; min-height: 54px; padding: 12px 76px 12px 42px; border: 1px solid #dbe3ee; border-radius: 14px; background: #f8fafc; color: #0f172a; font-size: 15px; box-sizing: border-box; }
.clear-btn { position: absolute; right: 12px; border: 0; background: transparent; color: #64748b; cursor: pointer; }
.keyword-row { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
.keyword-row span { margin-right: 3px; font-size: 11px; font-weight: 700; color: #64748b; }
.keyword-row button { border: 1px solid #dbe3ee; border-radius: 999px; padding: 6px 10px; background: white; color: #475569; font-size: 11px; cursor: pointer; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.document-layout, .law-layout { display: grid; grid-template-columns: minmax(250px, 300px) minmax(0, 1fr); gap: 18px; align-items: start; }
aside { display: flex; flex-direction: column; gap: 16px; }
.card-title { margin: 0; font-size: 16px; color: #0f172a; }
.card-title.light { color: white; }
.filter-stack { display: flex; flex-direction: column; gap: 18px; }
.filter-stack > div { display: flex; flex-direction: column; gap: 9px; }
.filter-label { display: block; margin-bottom: 8px; font-size: 12px; font-weight: 800; color: #475569; }
.check-row { display: flex; gap: 8px; align-items: center; font-size: 13px; color: #334155; }
select { width: 100%; min-height: 42px; padding: 9px 12px; border: 1px solid #dbe3ee; border-radius: 11px; background: #fff; color: #334155; }
.recent-card { background: linear-gradient(160deg, #153a74, #0f2d5c); color: white; }
.recent-card :deep(.body) { display: flex; flex-direction: column; gap: 12px; }
.recent-item { display: flex; flex-direction: column; gap: 3px; border: 0; padding: 0; background: transparent; color: white; text-align: left; cursor: pointer; }
.recent-item strong { font-size: 13px; }
.recent-item span, .empty-light { color: rgba(255,255,255,.7); font-size: 11px; }
.result-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.result-head > span { white-space: nowrap; font-size: 12px; color: #64748b; }
.result-head p { margin: 5px 0 0; font-size: 12px; color: #64748b; }
.sub-tabs { display: flex; flex-wrap: wrap; gap: 12px; }
.sub-tabs button { border: 0; border-bottom: 2px solid transparent; padding: 7px 1px; background: transparent; color: #64748b; font-size: 12px; font-weight: 700; cursor: pointer; }
.sub-tabs button.active { border-bottom-color: #2563eb; color: #0f172a; }
.document-list { display: flex; flex-direction: column; }
.document-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 2px; border-bottom: 1px solid #e8edf4; }
.document-main { min-width: 0; }
.document-main > strong { display: block; margin-top: 7px; color: #0f172a; font-size: 14px; word-break: break-all; }
.badge-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.category-badge, .content-badge, .metadata-badge, .law-type, .relevance { display: inline-flex; padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 800; }
.category-template { background: #ede9fe; color: #6d28d9; }
.category-general { background: #e0f2fe; color: #0369a1; }
.category-field { background: #dcfce7; color: #15803d; }
.content-badge { background: #fff7ed; color: #c2410c; }
.metadata-badge { background: #f1f5f9; color: #475569; }
.snippet { margin: 7px 0 0; padding: 8px 10px; border-left: 3px solid #93c5fd; background: #f8fafc; color: #475569; font-size: 12px; line-height: 1.55; }
.document-meta { margin: 6px 0 0; color: #94a3b8; font-size: 11px; word-break: break-all; }
.actions { display: flex; gap: 7px; flex-shrink: 0; }
.actions button, .more-btn { border: 1px solid #cbd5e1; border-radius: 9px; padding: 8px 11px; background: white; color: #334155; font-size: 11px; font-weight: 700; cursor: pointer; }
.actions .primary { border-color: #2563eb; background: #2563eb; color: white; }
.state { margin: 0; padding: 28px 4px; color: #64748b; }
.state.error { color: #b91c1c; }
.empty, .law-empty { display: flex; min-height: 220px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; color: #64748b; }
.empty strong, .law-empty strong { color: #334155; }
.empty span, .law-empty p { margin: 0; font-size: 12px; }
.pagination { display: flex; justify-content: center; flex-wrap: wrap; gap: 6px; margin-top: 18px; }
.pagination button { min-width: 32px; height: 32px; border: 1px solid #dbe3ee; border-radius: 8px; background: white; color: #475569; cursor: pointer; }
.pagination button.active { border-color: #2563eb; background: #2563eb; color: white; }
.law-filter-list { display: flex; flex-direction: column; gap: 7px; }
.law-filter-list button { display: flex; flex-direction: column; gap: 3px; border: 1px solid transparent; border-radius: 11px; padding: 10px 12px; background: #f8fafc; color: #475569; text-align: left; cursor: pointer; }
.law-filter-list button.active { border-color: #93c5fd; background: #eff6ff; color: #1d4ed8; }
.law-filter-list span { font-size: 13px; font-weight: 800; }
.law-filter-list small { color: #64748b; }
.law-guide { padding: 16px; border-radius: 15px; background: #0f2d5c; color: white; }
.law-guide p { margin: 8px 0 0; color: rgba(255,255,255,.75); font-size: 12px; line-height: 1.55; }
.law-symbol { display: grid; place-items: center; width: 52px; height: 52px; border-radius: 16px; background: #dbeafe; color: #1d4ed8; font-size: 28px; font-weight: 800; }
.law-list { display: flex; flex-direction: column; gap: 12px; }
.law-item { padding: 17px; border: 1px solid #dfe6ef; border-radius: 15px; background: #fff; }
.law-top { display: flex; justify-content: space-between; gap: 15px; }
.law-top > div > strong { display: block; margin-top: 7px; color: #0f172a; font-size: 15px; }
.law-type { background: #dbeafe; color: #1d4ed8; }
.relevance { background: #f1f5f9; color: #64748b; }
.article-label { color: #475569; font-size: 12px; white-space: nowrap; }
.law-item h3 { margin: 13px 0 0; color: #334155; font-size: 14px; }
.law-action { display: grid; grid-template-columns: 62px 1fr; gap: 10px; margin-top: 12px; padding: 12px; border-radius: 11px; background: #f8fafc; }
.law-action span { color: #1d4ed8; font-size: 11px; font-weight: 800; }
.law-action p { margin: 0; color: #334155; font-size: 12px; line-height: 1.55; }
details { margin-top: 10px; color: #475569; font-size: 12px; }
details summary { cursor: pointer; font-weight: 700; }
details div { margin-top: 10px; padding-left: 10px; border-left: 2px solid #cbd5e1; }
details p { margin: 4px 0 0; line-height: 1.55; }
.more-btn { display: block; margin: 16px auto 0; }
@media (max-width: 900px) {
  .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .document-layout, .law-layout { grid-template-columns: 1fr; }
  aside { order: 0; }
}
@media (max-width: 640px) {
  .explorer-page { gap: 14px; }
  .domain-switch { grid-template-columns: 1fr; }
  .domain-switch button { padding: 14px; }
  .kpi-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
  .document-row { align-items: flex-start; flex-direction: column; }
  .actions { width: 100%; }
  .actions button { flex: 1; min-height: 40px; }
  .law-top { flex-direction: column; }
  .article-label { white-space: normal; }
  .law-action { grid-template-columns: 1fr; }
}
</style>
