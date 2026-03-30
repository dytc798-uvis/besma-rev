<script setup lang="ts">
import { computed, ref } from "vue";
import SiteDashboardDemo from "./pages/SiteDashboardDemo.vue";
import WorkersStatusDemo from "./pages/WorkersStatusDemo.vue";
import WorkRiskTbmDemo from "./pages/WorkRiskTbmDemo.vue";
import DocumentStatusDemo from "./pages/DocumentStatusDemo.vue";
import HqMonitoringDemo from "./pages/HqMonitoringDemo.vue";

type ScreenKey = "site" | "workers" | "tbm" | "docs" | "hq";

const current = ref<ScreenKey>("site");

const menus: { key: ScreenKey; label: string }[] = [
  { key: "site", label: "1. 현장 대시보드" },
  { key: "workers", label: "2. 근로자 리스트 + 상태" },
  { key: "tbm", label: "3. 작업 + 위험요인(TBM)" },
  { key: "docs", label: "4. 문서 제출/반려 상태" },
  { key: "hq", label: "5. 본사 통합 모니터링" },
];

const currentComponent = computed(() => {
  if (current.value === "workers") return WorkersStatusDemo;
  if (current.value === "tbm") return WorkRiskTbmDemo;
  if (current.value === "docs") return DocumentStatusDemo;
  if (current.value === "hq") return HqMonitoringDemo;
  return SiteDashboardDemo;
});
</script>

<template>
  <div class="demo-wrap">
    <header class="panel">
      <h1 class="title">BESMA 데모용 UI 시나리오 (임시)</h1>
      <p class="sub">
        실제 운영 연동 전, 보고/흐름 설명을 위한 샘플 화면입니다.
      </p>
    </header>

    <nav class="menu-grid">
      <button
        v-for="m in menus"
        :key="m.key"
        type="button"
        class="menu-btn"
        :class="{ active: current === m.key }"
        @click="current = m.key"
      >
        {{ m.label }}
      </button>
    </nav>

    <component :is="currentComponent" />
  </div>
</template>

<style scoped>
.demo-wrap {
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px 24px 32px;
  display: grid;
  gap: 24px;
  background: #f1f5f9;
  min-height: 100vh;
}

.panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
  min-height: 0;
  height: auto;
}

.title {
  margin: 0;
  font-size: 34px;
  font-weight: 700;
}

.sub {
  margin: 8px 0 0;
  color: #334155;
  font-size: 15px;
}

.menu-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.menu-btn {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 8px 10px;
  background: #ffffff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  line-height: 1.3;
}

.menu-btn.active {
  background: #334155;
  border-color: #334155;
  color: #ffffff;
  font-weight: 700;
  box-shadow: 0 3px 8px rgba(30, 41, 59, 0.18);
}

.menu-btn:hover {
  border-color: #64748b;
  background: #f8fafc;
}

.menu-btn.active:hover {
  background: #0f172a;
}

@media (max-width: 980px) {
  .menu-grid {
    grid-template-columns: 1fr;
  }
}
</style>
