<script setup lang="ts">
import ExplanationBox from "../components/ExplanationBox.vue";
import { siteSummary } from "../data/mockData";

const lines = [
  "이 화면은 DB에 적재된 실제 현장명을 기준으로 오늘 운영 상태를 요약해 보여줍니다.",
  "제출률/미완료는 보고용 시나리오 값이며, 연결 인원은 현재 DB의 site_code 연계 건수를 반영합니다.",
];

const rateClass = (rate: number) => {
  if (rate < 80) return "rate-low";
  if (rate < 90) return "rate-mid";
  return "rate-high";
};
</script>

<template>
  <section class="section">
    <ExplanationBox :lines="lines" />
    <div class="kpi-grid">
      <div class="card kpi-card">
        <p class="label">오늘 출역 인원</p>
        <p class="kpi kpi-main">126명</p>
      </div>
      <div class="card kpi-card">
        <p class="label">제출 완료 문서</p>
        <p class="kpi kpi-good">43건</p>
      </div>
      <div class="card kpi-card">
        <p class="label">반려 건수</p>
        <p class="kpi kpi-bad">5건</p>
      </div>
    </div>

    <div class="card">
      <h3 class="heading">현장 요약</h3>
      <div class="site-grid">
        <article v-for="s in siteSummary" :key="s.name" class="site-card">
          <p class="site-name">{{ s.name }}</p>
          <div class="site-meta">
            <span>제출률:</span>
            <strong :class="rateClass(s.submitRate)">{{ s.submitRate }}%</strong>
          </div>
          <div class="site-meta">
            <span>미완료:</span>
            <strong class="pending">{{ s.pending }}건</strong>
          </div>
          <div class="site-meta">
            <span>인원:</span>
            <strong>{{ s.linkedWorkers }}명</strong>
          </div>
        </article>
      </div>
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 20px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
}

.label {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.kpi {
  margin: 8px 0 0;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.kpi-main {
  color: #0f172a;
}

.kpi-good {
  color: #15803d;
}

.kpi-bad {
  color: #b91c1c;
}

.heading {
  margin: 0 0 10px;
  font-size: 16px;
}

.site-grid {
  display: grid;
  gap: 12px;
}

.site-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  padding: 14px;
  display: grid;
  gap: 8px;
}

.site-name {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.site-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #334155;
}

.rate-low {
  color: #b91c1c;
}

.rate-mid {
  color: #c2410c;
}

.rate-high {
  color: #15803d;
}

.pending {
  color: #b91c1c;
}

@media (max-width: 980px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
