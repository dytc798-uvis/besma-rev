<template>
  <div class="site-dash-page">
    <BaseCard title="SITE 대시보드">
      <template #actions>
        <button type="button" class="stitch-btn-secondary" @click="load">새로고침</button>
      </template>
      <p class="mb-5 text-sm text-slate-500">내 현장 KPI</p>
      <section class="site-kpi-grid">
        <KpiCard label="전체 문서 수" :value="data?.total_documents ?? '—'" accent="blue" />
        <KpiCard label="제출/검토 중" :value="data?.pending_documents ?? '—'" accent="orange" />
        <KpiCard label="반려 문서" :value="data?.rejected_documents ?? '—'" accent="red" />
        <KpiCard label="현장 의견 접수" :value="data?.total_opinions ?? '—'" accent="slate" />
        <KpiCard label="미조치 의견" :value="data?.pending_opinions ?? '—'" accent="slate" />
      </section>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";
import { BaseCard, KpiCard } from "@/components/product";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
  rejected_documents: number;
  total_opinions: number;
  pending_opinions: number;
}

const data = ref<DashboardSummary | null>(null);

async function load() {
  const res = await api.get("/dashboard/summary");
  data.value = res.data;
}

onMounted(load);
</script>

<style scoped>
.site-dash-page {
  width: 100%;
}

/* 기존 SITE 대시보드: 3열 그리드, gap 12px 유지 */
.site-kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 900px) {
  .site-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .site-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
