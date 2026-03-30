<script setup lang="ts">
import { computed, ref } from "vue";
import ExplanationBox from "../components/ExplanationBox.vue";
import { workers } from "../data/mockData";

const lines = [
  "이 화면은 실제 등록 근로자명을 기준으로 전체 인원 현황을 운영 관점에서 조회하는 데모입니다.",
  "필터 바와 상태 배지는 관리 흐름 설명용 UI이며, 작업 상태는 보고 시나리오 예시 값을 포함합니다.",
];

const badgeClass = (status: string) => {
  if (status === "작업가능") return "status-ok";
  if (status === "미교육") return "status-warn";
  return "status-danger";
};

const linkedWorkers = computed(() => workers.filter((w) => w.affiliationType === "DB 연계"));
const unlinkedWorkers = computed(() => workers.filter((w) => w.affiliationType !== "DB 연계"));
const educationPendingCount = computed(() => workers.filter((w) => w.status === "미교육").length);
const unconfirmedCount = computed(() => workers.filter((w) => w.status === "미확인").length);

const selectedSite = ref("전체 현장");
const selectedStatus = ref("전체 상태");
const nameKeyword = ref("");
const unlinkedOnly = ref(false);
</script>

<template>
  <section class="section">
    <ExplanationBox :lines="lines" />

    <div class="summary-grid">
      <article class="summary-card">
        <p class="summary-label">전체 근로자 수</p>
        <p class="summary-value">{{ workers.length }}명</p>
      </article>
      <article class="summary-card">
        <p class="summary-label">DB 연계 완료 수</p>
        <p class="summary-value good">{{ linkedWorkers.length }}명</p>
      </article>
      <article class="summary-card">
        <p class="summary-label">소속 미연결 수</p>
        <p class="summary-value warn">{{ unlinkedWorkers.length }}명</p>
      </article>
      <article class="summary-card">
        <p class="summary-label">미교육 수</p>
        <p class="summary-value warn">{{ educationPendingCount }}명</p>
      </article>
      <article class="summary-card">
        <p class="summary-label">미확인 수</p>
        <p class="summary-value bad">{{ unconfirmedCount }}명</p>
      </article>
    </div>

    <div class="card">
      <h3 class="heading">조회 필터</h3>
      <div class="filter-grid">
        <label class="filter-item">
          <span>현장 선택</span>
          <select v-model="selectedSite">
            <option>전체 현장</option>
            <option>부현전기 서울 현장</option>
            <option>부현전기 부산 현장</option>
            <option>[1.DL건설] 전도관구역 주택재개발 정비사업조합(01공구)</option>
            <option>[1.대우건설] 강릉비행장현장 특고압 전력 및 통신 지장물 이설공사</option>
            <option>소속 미연결</option>
          </select>
        </label>
        <label class="filter-item">
          <span>상태 선택</span>
          <select v-model="selectedStatus">
            <option>전체 상태</option>
            <option>작업가능</option>
            <option>미교육</option>
            <option>미확인</option>
          </select>
        </label>
        <label class="filter-item">
          <span>이름 검색</span>
          <input v-model="nameKeyword" type="text" placeholder="근로자명 입력" />
        </label>
        <label class="filter-check">
          <input v-model="unlinkedOnly" type="checkbox" />
          <span>미연결만 보기</span>
        </label>
      </div>
    </div>

    <div class="card">
      <h3 class="heading">근로자 상태</h3>
      <table class="table">
        <thead>
          <tr>
            <th>이름</th>
            <th>소속 현장</th>
            <th>소속 연계 상태</th>
            <th>작업 상태</th>
            <th>비고</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in linkedWorkers" :key="`${w.name}-${w.site}`">
            <td>{{ w.name }}</td>
            <td>{{ w.site }}</td>
            <td>{{ w.affiliationType }}</td>
            <td>
              <span class="status-badge" :class="badgeClass(w.status)">
                {{ w.status }}
              </span>
            </td>
            <td>{{ w.note }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card warning-card">
      <h3 class="heading warning-title">소속 미연결 인원 (조치 필요)</h3>
      <table class="table">
        <thead>
          <tr>
            <th>이름</th>
            <th>소속 현장</th>
            <th>소속 연계 상태</th>
            <th>작업 상태</th>
            <th>비고</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in unlinkedWorkers" :key="`unlinked-${w.name}-${w.site}`">
            <td>{{ w.name }}</td>
            <td>{{ w.site }}</td>
            <td>
              <span class="link-badge">{{ w.affiliationType }}</span>
            </td>
            <td>
              <span class="status-badge" :class="badgeClass(w.status)">
                {{ w.status }}
              </span>
            </td>
            <td>{{ w.note }}</td>
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  padding: 14px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.summary-label {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.summary-value {
  margin: 8px 0 0;
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
}

.summary-value.good {
  color: #15803d;
}

.summary-value.warn {
  color: #b45309;
}

.summary-value.bad {
  color: #b91c1c;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1.2fr auto;
  gap: 10px;
  align-items: end;
}

.filter-item {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: #475569;
}

.filter-item select,
.filter-item input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 14px;
  background: #fff;
}

.filter-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #334155;
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

.status-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 5px 11px;
  font-size: 12px;
  font-weight: 700;
}

.status-ok {
  background: #dcfce7;
  color: #166534;
}

.status-warn {
  background: #fef3c7;
  color: #92400e;
}

.status-danger {
  background: #fee2e2;
  color: #991b1b;
}

.warning-card {
  border-color: #fdba74;
  background: #fffaf0;
}

.warning-title {
  color: #9a3412;
}

.link-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
  background: #ffedd5;
  color: #9a3412;
}

@media (max-width: 1080px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
