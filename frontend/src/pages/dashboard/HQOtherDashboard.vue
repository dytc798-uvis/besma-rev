<template>
  <div class="card">
    <div class="card-title">HQ_OTHER 대시보드</div>
    <div class="toolbar">
      <div>조회 중심 요약</div>
      <button class="secondary" @click="load">새로고침</button>
    </div>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px">
      <div class="card">
        <div class="card-title">조회 가능 문서 수</div>
        <div>{{ data?.total_documents ?? "-" }}</div>
      </div>
      <div class="card">
        <div class="card-title">최근 요청 문서 (수)</div>
        <div>{{ data?.pending_documents ?? "-" }}</div>
      </div>
      <div class="card">
        <div class="card-title">알림 (placeholder)</div>
        <div>-</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
}

const data = ref<DashboardSummary | null>(null);

async function load() {
  const res = await api.get("/dashboard/summary");
  data.value = res.data;
}

onMounted(load);
</script>

<style scoped></style>

