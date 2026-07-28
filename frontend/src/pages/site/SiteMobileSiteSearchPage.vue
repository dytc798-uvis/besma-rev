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
        <article v-for="site in filteredSites" :key="site.id" class="site-card">
          <h2>{{ site.name }}</h2>
          <p>📍 {{ site.address || "주소 정보 없음" }}</p>
          <button
            type="button"
            class="primary large-btn"
            :disabled="!canOpenDirections(site)"
            @click="openSiteDirections(site)"
          >
            현재 위치에서 길찾기
          </button>
        </article>
        <p v-if="normalizedQuery && !loading && filteredSites.length === 0" class="empty">검색 결과가 없습니다.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { openDirections } from "@/utils/map";

interface SiteSearchItem {
  id: number;
  name: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
}

const auth = useAuthStore();
const query = ref("");
const sites = ref<SiteSearchItem[]>([]);
const loading = ref(true);
const error = ref("");
const normalizedQuery = computed(() => query.value.trim().toLowerCase());

const filteredSites = computed(() => {
  const q = normalizedQuery.value;
  if (!q) return [];
  return sites.value.filter(
    (site) => site.name.toLowerCase().includes(q) || (site.address || "").toLowerCase().includes(q),
  );
});

function canOpenDirections(site: SiteSearchItem) {
  return Boolean(site.address || (site.latitude != null && site.longitude != null));
}

function openSiteDirections(site: SiteSearchItem) {
  if (!canOpenDirections(site)) return;
  const pref = auth.user?.map_preference === "TMAP" ? "TMAP" : "NAVER";
  openDirections(site, pref);
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
.large-btn {
  width: 100%;
  min-height: 50px;
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

