<script setup lang="ts">
import { computed } from "vue";
import ExplanationBox from "../components/ExplanationBox.vue";
import { works } from "../data/mockData";

const lines = [
  "이 화면은 TBM 운영 관점에서 오늘 작업 위험을 요약하고 조치 우선순위를 확인하기 위한 데모입니다.",
];

const todayWorkCount = computed(() => works.length);
const riskCount = computed(() => new Set(works.map((w) => w.risk)).size);
const actionRequiredCount = computed(() =>
  works.filter((w) => ["감전", "아크 발생"].includes(w.risk)).length
);
const uncheckedCount = computed(() => 1);
</script>

<template>
  <section class="section">
    <ExplanationBox :lines="lines" />
    <div class="kpi-grid">
      <article class="kpi-card">
        <p class="kpi-label">오늘 작업 수</p>
        <p class="kpi-value">{{ todayWorkCount }}건</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">위험요인 수</p>
        <p class="kpi-value">{{ riskCount }}건</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">조치 필요 건수</p>
        <p class="kpi-value danger">{{ actionRequiredCount }}건</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">미확인 건수</p>
        <p class="kpi-value warn">{{ uncheckedCount }}건</p>
      </article>
    </div>
    <p class="tbm-note">작업/위험/대응 항목은 실데이터 기반 화면 시연을 위한 예시 상태입니다.</p>
    <div class="card">
      <h3 class="heading">작업 + 위험요인(TBM)</h3>
      <table class="table">
        <thead>
          <tr>
            <th>현장</th>
            <th>근로자</th>
            <th>작업명</th>
            <th>위험요인</th>
            <th>대응대책</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in works" :key="w.task">
            <td>{{ w.site }}</td>
            <td>{{ w.worker }}</td>
            <td>{{ w.task }}</td>
            <td class="risk">{{ w.risk }}</td>
            <td>{{ w.countermeasure }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.section {
  display: grid;
  gap: 24px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  padding: 16px;
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
}

.kpi-label {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.kpi-value {
  margin: 8px 0 0;
  font-size: 30px;
  font-weight: 700;
  color: #0f172a;
}

.kpi-value.warn {
  color: #b45309;
}

.kpi-value.danger {
  color: #b91c1c;
}

.tbm-note {
  margin: -12px 0 0;
  font-size: 13px;
  color: #64748b;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 18px 20px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
}

.heading {
  margin: 0 0 14px;
  font-size: 18px;
  font-weight: 700;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th,
.table td {
  border: 1px solid #e2e8f0;
  padding: 10px 12px;
  text-align: left;
  font-size: 14px;
}

.table thead th {
  background: #f8fafc;
}

.table tbody tr {
  transition: background-color 0.15s ease;
}

.table tbody tr:hover {
  background: #f8fafc;
}

.risk {
  color: #b91c1c;
  font-weight: 600;
}

@media (max-width: 980px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
