<template>
  <div class="card safety-record-page">
    <div class="toolbar">
      <div class="toolbar-filters">
        <input v-model.number="personIdInput" type="number" min="1" placeholder="person_id 입력" />
      </div>
      <div class="toolbar-actions">
        <button class="secondary" @click="goBack">TBM 모니터</button>
        <button class="primary" :disabled="loading || !personIdInput" @click="loadRecord">개인 증빙 조회</button>
      </div>
    </div>

    <p v-if="message" class="record-message">{{ message }}</p>

    <template v-if="record">
      <section class="record-card">
        <h2>기본 정보</h2>
        <div class="info-grid">
          <div><strong>이름</strong><div>{{ record.person.name }}</div></div>
          <div><strong>person_id</strong><div>{{ record.person.person_id }}</div></div>
          <div><strong>현장</strong><div>{{ record.person.site_name ?? "-" }}</div></div>
          <div><strong>부서/직책</strong><div>{{ [record.person.department_name, record.person.position_name].filter(Boolean).join(" / ") || "-" }}</div></div>
          <div><strong>연락처</strong><div>{{ record.person.phone_mobile ?? "-" }}</div></div>
          <div><strong>배포 건수</strong><div>{{ record.distributions.length }}</div></div>
        </div>
      </section>

      <section class="record-card">
        <h2>작업 배포 및 서명 이력</h2>
        <div v-if="record.distributions.length === 0" class="empty-box">조회 기간 내 배포 이력이 없습니다.</div>
        <div v-for="entry in record.distributions" :key="entry.distribution_id" class="distribution-card">
          <div class="distribution-head">
            <strong>#{{ entry.distribution_id }}</strong>
            <span v-if="entry.is_reassignment" class="badge badge-warn">작업 변경 재지시</span>
          </div>
          <div class="distribution-meta">
            <span>배포일: {{ entry.target_date }}</span>
            <span>열람: {{ entry.viewed_at ?? "-" }}</span>
            <span>시작서명: {{ entry.start_signed_at ?? "-" }}</span>
            <span>종료서명: {{ entry.end_signed_at ?? "-" }}</span>
            <span>종료상태: {{ entry.end_status ?? "-" }}</span>
            <span>ISSUE: {{ entry.issue_flag ? "Y" : "N" }}</span>
          </div>
          <div v-if="entry.reassignment_reason" class="reason-box">
            <strong>변경 사유</strong> {{ entry.reassignment_reason }}
          </div>

          <table class="basic-table">
            <thead>
              <tr>
                <th>작업</th>
                <th>설명</th>
                <th>위험요인/대책</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in entry.items" :key="item.plan_item_id">
                <td>{{ item.work_name }}</td>
                <td>{{ item.work_description }}</td>
                <td>
                  <div v-if="item.risks.length === 0">-</div>
                  <div v-for="risk in item.risks" :key="risk.risk_revision_id" class="risk-row">
                    <strong>{{ risk.risk_factor }}</strong>
                    <div>{{ risk.counterplan }}</div>
                    <small>위험도 {{ risk.risk_level }}</small>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="record-card">
        <h2>근로자 피드백</h2>
        <table class="basic-table">
          <thead>
            <tr>
              <th>일시</th>
              <th>유형</th>
              <th>내용</th>
              <th>검토상태</th>
              <th>후보자산화</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="feedback in record.feedbacks" :key="feedback.id">
              <td>{{ feedback.created_at }}</td>
              <td>{{ feedback.feedback_type }}</td>
              <td>{{ feedback.content }}</td>
              <td>{{ feedback.status }}</td>
              <td>{{ feedback.candidate_status ?? "-" }}</td>
            </tr>
            <tr v-if="record.feedbacks.length === 0">
              <td colspan="5" style="text-align: center">등록된 피드백이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";

interface SafetyRecord {
  person: {
    person_id: number;
    name: string;
    phone_mobile: string | null;
    site_name: string | null;
    department_name: string | null;
    position_name: string | null;
  };
  distributions: Array<{
    distribution_id: number;
    is_reassignment: boolean;
    reassignment_reason: string | null;
    target_date: string;
    viewed_at: string | null;
    start_signed_at: string | null;
    end_signed_at: string | null;
    end_status: string | null;
    issue_flag: boolean;
    items: Array<{
      plan_item_id: number;
      work_name: string;
      work_description: string;
      risks: Array<{
        risk_revision_id: number;
        risk_factor: string;
        counterplan: string;
        risk_level: number;
      }>;
    }>;
  }>;
  feedbacks: Array<{
    id: number;
    created_at: string;
    feedback_type: string;
    content: string;
    status: string;
    candidate_status: string | null;
  }>;
}

const route = useRoute();
const router = useRouter();
const personIdInput = ref<number | null>(Number(route.params.personId) || null);
const loading = ref(false);
const message = ref("");
const record = ref<SafetyRecord | null>(null);

async function loadRecord() {
  if (!personIdInput.value) return;
  loading.value = true;
  message.value = "";
  try {
    const res = await api.get(`/hq-safe/workers/${personIdInput.value}/safety-record`);
    record.value = res.data;
    router.replace({
      name: "hq-safe-worker-safety-record",
      params: { personId: personIdInput.value },
    });
  } catch (err: any) {
    record.value = null;
    message.value = err?.response?.data?.detail ?? "개인 증빙 조회 실패";
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push({ name: "hq-safe-tbm-monitor" });
}

watch(
  () => route.params.personId,
  (value) => {
    const numericValue = Number(value);
    personIdInput.value = Number.isFinite(numericValue) && numericValue > 0 ? numericValue : null;
  },
);

onMounted(() => {
  if (personIdInput.value) {
    loadRecord();
  }
});
</script>

<style scoped>
.safety-record-page {
  display: grid;
  gap: 16px;
}

.record-message {
  color: #dc2626;
}

.record-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  background: #fff;
}

.record-card h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.distribution-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fafafa;
}

.distribution-head {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.distribution-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
  color: #475569;
}

.reason-box {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff7ed;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.badge-warn {
  background: #fef3c7;
  color: #92400e;
}

.risk-row {
  margin-bottom: 8px;
}

.empty-box {
  color: #64748b;
}

@media (max-width: 960px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
