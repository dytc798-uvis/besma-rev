<script setup lang="ts">
import ExplanationBox from "../components/ExplanationBox.vue";
import { siteSummary } from "../data/mockData";

const lines = [
  "이 화면은 DB의 실제 현장명을 기반으로 본사 통합 모니터링 흐름을 보여줍니다.",
  "제출률/미완료는 시연용 예시 값이며, 연계 인원은 현재 DB 연계 상태를 반영합니다.",
];
</script>

<template>
  <section class="section">
    <ExplanationBox :lines="lines" />
    <div class="card">
      <h3 class="heading">본사 통합 모니터링</h3>
      <ul class="list">
        <li v-for="s in siteSummary" :key="s.name" class="list-item">
          <p class="site">{{ s.name }}</p>
          <p class="meta">제출률 {{ s.submitRate }}% / 미완료 {{ s.pending }}건</p>
          <p class="meta">연계 인원(DB): {{ s.linkedWorkers }}명</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.section {
  display: grid;
  gap: 24px;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 18px 20px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
}

.heading {
  margin: 0 0 10px;
  font-size: 15px;
}

.list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 12px;
}

.list-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: inset 0 0 0 1px #f8fafc;
}

.site {
  margin: 0;
  font-weight: 700;
}

.meta {
  margin: 6px 0 0;
  color: #334155;
}
</style>
