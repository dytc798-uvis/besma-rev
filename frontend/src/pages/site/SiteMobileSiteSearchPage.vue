<template>
  <div class="mobile-wrap">
    <div class="card">
      <h1 class="title">현장 검색</h1>
      <input v-model="query" type="text" class="search-input" placeholder="현장명/주소 검색" />

      <div class="site-list">
        <article v-for="site in filteredSites" :key="site.id" class="site-card">
          <h2>{{ site.name }}</h2>
          <p>📍 {{ site.address || "주소 정보 없음" }}</p>
          <button
            type="button"
            class="primary large-btn"
            :disabled="!site.address"
            @click="openSiteMap(site)"
          >
            지도 보기
          </button>
        </article>
        <p v-if="filteredSites.length === 0" class="empty">검색 결과가 없습니다.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { openMap } from "@/utils/map";

interface SiteSearchItem {
  id: number;
  name: string;
  address: string | null;
}

const auth = useAuthStore();
const query = ref("");
const sites = ref<SiteSearchItem[]>([]);

const filteredSites = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return sites.value;
  return sites.value.filter(
    (site) => site.name.toLowerCase().includes(q) || (site.address || "").toLowerCase().includes(q),
  );
});

function openSiteMap(site: SiteSearchItem) {
  if (!site.address) return;
  const pref = auth.user?.map_preference === "TMAP" ? "TMAP" : "NAVER";
  openMap(site.address, pref);
}

async function loadSites() {
  const res = await api.get("/sites/search");
  sites.value = (res.data ?? []) as SiteSearchItem[];
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
.search-input {
  width: 100%;
  min-height: 44px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 12px;
  margin-bottom: 10px;
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
  min-height: 44px;
}
.empty {
  color: #64748b;
  font-size: 13px;
}
</style>

