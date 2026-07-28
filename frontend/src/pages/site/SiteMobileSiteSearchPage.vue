<template>
  <div class="mobile-wrap">
    <div class="card">
      <h1 class="title">현장 검색</h1>
      <p class="description">전 현장을 현장명 또는 주소로 검색합니다.</p>
      <input
        v-model="query"
        type="search"
        class="search-input"
        placeholder="현장명 또는 주소를 입력하세요"
        autocomplete="off"
        autofocus
      />

      <div class="site-list">
        <p v-if="loading" class="empty">현장 목록을 불러오는 중입니다.</p>
        <p v-else-if="error" class="error">{{ error }}</p>
        <p v-else-if="!normalizedQuery" class="empty">검색어를 입력하면 일치하는 현장만 표시됩니다.</p>
        <p v-else-if="rankedSites.length" class="result-count">관련 현장 {{ rankedSites.length }}개 · 유사도순</p>
        <article v-for="site in rankedSites" :key="site.id" class="site-card">
          <h2>{{ site.name }}</h2>
          <p class="match-reason">{{ site.matchReason }}</p>
          <p>📍 {{ baseAddress(site.address) || "주소 정보 없음" }}</p>
          <div class="site-actions">
            <button
              type="button"
              class="primary"
              :disabled="!canOpenDirections(site)"
              @click="openSiteDirections(site)"
            >
              네이버지도
            </button>
            <button
              type="button"
              class="secondary"
              :disabled="!site.address"
              @click="copyBaseAddress(site)"
            >
              {{ copiedSiteId === site.id ? "복사됨" : "주소 복사" }}
            </button>
            <button type="button" class="secondary" @click="toggleDetail(site.id)">
              {{ expandedSiteIds.has(site.id) ? "접기" : "상세" }}
            </button>
          </div>
          <div v-if="expandedSiteIds.has(site.id)" class="site-detail">
            <dl>
              <div><dt>현장코드</dt><dd>{{ site.site_code }}</dd></div>
              <div><dt>전체 주소</dt><dd>{{ site.address || "주소 정보 없음" }}</dd></div>
            </dl>
          </div>
        </article>
        <p v-if="normalizedQuery && !loading && rankedSites.length === 0" class="empty">관련 현장을 찾지 못했습니다.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { openDirections } from "@/utils/map";

interface SiteSearchItem {
  id: number;
  site_code: string;
  name: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
}

interface RankedSite extends SiteSearchItem {
  score: number;
  matchReason: string;
}

const query = ref("");
const sites = ref<SiteSearchItem[]>([]);
const loading = ref(true);
const error = ref("");
const copiedSiteId = ref<number | null>(null);
const expandedSiteIds = ref(new Set<number>());
const normalizedQuery = computed(() => query.value.trim().toLowerCase());

const rankedSites = computed<RankedSite[]>(() => {
  const q = normalizedQuery.value;
  if (!q) return [];
  return sites.value
    .map((site) => ({ ...site, ...siteMatch(site, q) }))
    .filter((site) => site.score >= 180)
    .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, "ko"));
});

function normalized(value: string | null | undefined) {
  return (value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\[\](){}.,\/\\:_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function bigrams(value: string) {
  const compact = value.replace(/\s/g, "");
  if (compact.length < 2) return new Set(compact ? [compact] : []);
  return new Set(Array.from({ length: compact.length - 1 }, (_, index) => compact.slice(index, index + 2)));
}

function diceSimilarity(left: string, right: string) {
  const a = bigrams(left);
  const b = bigrams(right);
  if (!a.size || !b.size) return 0;
  let common = 0;
  a.forEach((part) => {
    if (b.has(part)) common += 1;
  });
  return (2 * common) / (a.size + b.size);
}

function siteMatch(site: SiteSearchItem, rawQuery: string) {
  const q = normalized(rawQuery);
  const name = normalized(site.name);
  const address = normalized(site.address);
  const code = normalized(site.site_code);
  const tokens = q.split(" ").filter(Boolean);
  const nameTokenCoverage = tokens.length
    ? tokens.filter((token) => name.includes(token)).length / tokens.length
    : 0;
  const addressTokenCoverage = tokens.length
    ? tokens.filter((token) => address.includes(token)).length / tokens.length
    : 0;

  if (name === q) return { score: 1000, matchReason: "현장명 정확 일치" };
  if (code === q) return { score: 980, matchReason: "현장코드 정확 일치" };
  if (name.startsWith(q)) return { score: 920, matchReason: "현장명 시작 일치" };
  if (name.includes(q)) return { score: 880, matchReason: "현장명 포함" };
  if (address.includes(q)) return { score: 840, matchReason: "주소 포함" };
  if (code.includes(q)) return { score: 820, matchReason: "현장코드 포함" };
  if (nameTokenCoverage === 1) return { score: 780, matchReason: "검색 단어 모두 일치" };
  if (addressTokenCoverage === 1) return { score: 740, matchReason: "주소 단어 모두 일치" };

  const nameSimilarity = diceSimilarity(q, name);
  const addressSimilarity = diceSimilarity(q, address);
  const partialScore = Math.max(
    nameSimilarity * 600,
    addressSimilarity * 520,
    nameTokenCoverage * 560,
    addressTokenCoverage * 480,
  );
  return {
    score: Math.round(partialScore),
    matchReason: partialScore >= 180 ? "유사 검색어 일치" : "",
  };
}

function canOpenDirections(site: SiteSearchItem) {
  return Boolean(site.address || (site.latitude != null && site.longitude != null));
}

function openSiteDirections(site: SiteSearchItem) {
  if (!canOpenDirections(site)) return;
  openDirections(site, "NAVER");
}

function baseAddress(address: string | null) {
  return (address || "")
    .replace(/[,，]?\s*(?:제?\s*)?\d{1,4}\s*동(?:\s*(?:제?\s*)?\d{1,5}\s*호)?(?:\s.*)?$/u, "")
    .replace(/[,，]?\s*(?:제?\s*)?\d{1,5}\s*호(?:\s.*)?$/u, "")
    .replace(/[,，]?\s*(?:지하|지상)?\s*\d{1,3}\s*층(?:\s.*)?$/u, "")
    .trim();
}

async function copyBaseAddress(site: SiteSearchItem) {
  const value = baseAddress(site.address);
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  copiedSiteId.value = site.id;
  window.setTimeout(() => {
    if (copiedSiteId.value === site.id) copiedSiteId.value = null;
  }, 1600);
}

function toggleDetail(siteId: number) {
  const next = new Set(expandedSiteIds.value);
  if (next.has(siteId)) next.delete(siteId);
  else next.add(siteId);
  expandedSiteIds.value = next;
}

async function loadSites() {
  loading.value = true;
  error.value = "";
  try {
    const res = await api.get("/sites/search");
    sites.value = (res.data ?? []) as SiteSearchItem[];
  } catch {
    error.value = "현장 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  } finally {
    loading.value = false;
  }
}

onMounted(loadSites);
</script>

<style scoped>
.mobile-wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 8px;
}
.title {
  margin: 0 0 10px;
  font-size: 20px;
}
.description {
  margin: -4px 0 12px;
  color: #64748b;
  font-size: 13px;
}
.search-input {
  width: 100%;
  min-height: 52px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 12px;
  margin-bottom: 14px;
  box-sizing: border-box;
  font-size: 16px;
}
.site-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.site-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}
.site-card h2 {
  margin: 0 0 6px;
  font-size: 16px;
}
.site-card p {
  margin: 0 0 10px;
  color: #475569;
  font-size: 13px;
}
.match-reason {
  color: #0f6b6d !important;
  font-weight: 800;
}
.result-count {
  margin: 0;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
}
.site-actions {
  display: grid;
  grid-template-columns: 1.25fr 1fr .8fr;
  gap: 7px;
}
.site-actions button {
  min-height: 48px;
  border-radius: 9px;
  font-weight: 800;
  cursor: pointer;
}
.site-actions button:disabled {
  cursor: not-allowed;
  opacity: .45;
}
.secondary {
  border: 1px solid #9fb1bd;
  background: #fff;
  color: #334155;
}
.site-detail {
  margin-top: 10px;
  padding: 11px;
  border-radius: 9px;
  background: #f8fafc;
}
.site-detail dl {
  display: grid;
  gap: 8px;
  margin: 0;
}
.site-detail dl div {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 8px;
}
.site-detail dt {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}
.site-detail dd {
  margin: 0;
  color: #1e293b;
  font-size: 13px;
  word-break: keep-all;
}
.empty {
  margin: 0;
  padding: 24px 12px;
  border-radius: 10px;
  background: #f8fafc;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}
.error {
  margin: 0;
  padding: 14px;
  border-radius: 10px;
  color: #a43d2d;
  background: #fff0ed;
  font-size: 13px;
  font-weight: 700;
}
</style>

