<script setup lang="ts">
import ExplanationBox from "../components/ExplanationBox.vue";
import { documents } from "../data/mockData";

const lines = [
  "이 화면은 실제 현장명을 기준으로 문서 제출/반려 흐름을 시연하기 위한 화면입니다.",
  "문서 상태와 반려 사유는 보고용 예시 시나리오이며, 운영 연동 시 실제 문서 상태로 대체됩니다.",
];
</script>

<template>
  <section class="section">
    <ExplanationBox :lines="lines" />
    <div class="card">
      <h3 class="heading">문서 제출/반려 현황</h3>
      <table class="table">
        <thead>
          <tr>
            <th>현장명</th>
            <th>문서명</th>
            <th>상태</th>
            <th>반려사유</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in documents" :key="d.name">
            <td>{{ d.site }}</td>
            <td>{{ d.name }}</td>
            <td>{{ d.status }}</td>
            <td>{{ d.reason }}</td>
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
</style>
