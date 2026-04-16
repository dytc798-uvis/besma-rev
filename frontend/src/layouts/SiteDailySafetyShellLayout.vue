<template>
  <div class="daily-safety-shell">
    <nav v-if="showHubTabs" class="hub-tabs" aria-label="일일안전회의(일일위험성평가) 구역">
      <RouterLink class="hub-tab" :to="{ name: 'site-mobile-ops' }">작업계획·TBM·위험성평가</RouterLink>
      <RouterLink class="hub-tab" :to="{ name: 'site-mobile-daily-capture' }">일지·사진·문서</RouterLink>
    </nav>
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";

const route = useRoute();

const showHubTabs = computed(
  () => route.name === "site-mobile-ops" || route.name === "site-mobile-daily-capture",
);
</script>

<style scoped>
.daily-safety-shell {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}

.hub-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.hub-tab {
  flex: 1;
  min-width: 140px;
  text-align: center;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0f172a;
  font-weight: 600;
  font-size: 13px;
  text-decoration: none;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.hub-tab:hover {
  background: #eff6ff;
  border-color: #93c5fd;
}

.hub-tab.router-link-active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

/* SITE 레이아웃 모바일(≤768px)과 좁은 창: 탭 세로 스택·터치 영역 */
@media (max-width: 768px) {
  .hub-tabs {
    flex-direction: column;
    padding: 8px 10px 10px;
    gap: 6px;
  }

  .hub-tab {
    flex: none;
    min-width: 0;
    width: 100%;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
  }
}

/* 데스크톱에서 창만 좁은 경우: 탭은 가로 유지, 줄바꿈만 허용 */
@media (min-width: 769px) and (max-width: 900px) {
  .hub-tab {
    font-size: 12px;
    padding: 8px 10px;
    min-width: 120px;
  }
}
</style>
