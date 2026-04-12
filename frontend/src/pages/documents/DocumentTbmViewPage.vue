<template>
  <div class="tbm-view-page" v-if="summary">
    <div class="tbm-toolbar no-print">
      <button class="primary" @click="printPage">출력</button>
    </div>

    <section class="tbm-paper">
      <header class="tbm-header">
        <h1>TBM(작업 전 안전점검) 회의록</h1>
        <div class="tbm-meta-grid">
          <div><strong>교육일시</strong> {{ summary.work_date }}</div>
          <div><strong>현장명</strong> {{ summary.site_name || "-" }}</div>
          <div><strong>TBM 리더</strong> {{ summary.tbm_leader_name || "-" }}</div>
          <div><strong>교육인원</strong> {{ summary.education_count }}명</div>
        </div>
      </header>

      <section class="tbm-section">
        <h2>작업/위험 정보</h2>
        <table class="basic-table">
          <thead>
            <tr>
              <th>금일작업내용</th>
              <th>위험요인</th>
              <th>감소방안</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in summary.table_rows" :key="idx">
              <td>{{ row.work_description || "-" }}</td>
              <td>{{ row.risk_factor }}</td>
              <td>{{ row.counterplan }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="tbm-section">
        <h2>중점위험요인 (상위 5)</h2>
        <ol class="tbm-top-risks">
          <li v-for="risk in summary.top_risks" :key="risk.risk_revision_id">
            {{ risk.risk_factor }} (위험도: {{ risk.risk_level }}) - {{ risk.counterplan }}
          </li>
        </ol>
      </section>

      <section class="tbm-section">
        <h2>참석자 서명</h2>
        <table class="basic-table">
          <thead>
            <tr>
              <th>이름</th>
              <th>시작 서명</th>
              <th>종료 서명</th>
              <th>종료 상태</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="person in sortedParticipants" :key="person.person_id">
              <td>{{ person.name }}</td>
              <td>
                <img
                  v-if="person.start_signature_data"
                  :src="person.start_signature_data"
                  alt="start-signature"
                  class="signature-image"
                />
                <span v-else class="empty-sign">미서명</span>
              </td>
              <td>
                <img
                  v-if="person.end_signature_data"
                  :src="person.end_signature_data"
                  alt="end-signature"
                  class="signature-image"
                />
                <span v-else class="empty-sign">미서명</span>
              </td>
              <td>
                <span v-if="person.end_status === 'NORMAL'">정상</span>
                <span v-else-if="person.end_status === 'ISSUE'">이상</span>
                <span v-else>-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </section>
  </div>

  <div v-else class="card">TBM 데이터를 불러오는 중입니다...</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";
import { toDate } from "@/utils/datetime";

interface TbmTableRow {
  work_description: string | null;
  risk_factor: string;
  counterplan: string;
  risk_level: number | null;
}

interface TbmTopRisk {
  risk_revision_id: number;
  risk_factor: string;
  counterplan: string;
  risk_level: number;
}

interface TbmParticipant {
  person_id: number;
  name: string;
  ack_status: string;
  start_signed_at: string | null;
  end_signed_at: string | null;
  end_status: "NORMAL" | "ISSUE" | null;
  issue_flag: boolean;
  start_signature_data: string | null;
  end_signature_data: string | null;
}

interface TbmSummary {
  document_id: number;
  instance_id: number;
  site_id: number;
  site_name: string | null;
  work_date: string;
  tbm_leader_name: string | null;
  education_count: number;
  table_rows: TbmTableRow[];
  top_risks: TbmTopRisk[];
  participants: TbmParticipant[];
}

const route = useRoute();
const summary = ref<TbmSummary | null>(null);

const sortedParticipants = computed(() => {
  if (!summary.value) return [];
  return [...summary.value.participants].sort((a, b) => {
    const aTs = a.start_signed_at ? toDate(a.start_signed_at)?.getTime() ?? Number.MAX_SAFE_INTEGER : Number.MAX_SAFE_INTEGER;
    const bTs = b.start_signed_at ? toDate(b.start_signed_at)?.getTime() ?? Number.MAX_SAFE_INTEGER : Number.MAX_SAFE_INTEGER;
    return aTs - bTs;
  });
});

async function load() {
  const documentId = route.params.id;
  const res = await api.get(`/documents/${documentId}/tbm-summary`);
  summary.value = res.data;
}

function printPage() {
  window.print();
}

onMounted(load);
</script>

<style scoped>
.tbm-view-page {
  width: 100%;
}

.tbm-toolbar {
  margin-bottom: 12px;
}

.tbm-paper {
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 16px;
}

.tbm-header h1 {
  margin: 0 0 12px;
  font-size: 20px;
}

.tbm-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
}

.tbm-section {
  margin-top: 16px;
}

.tbm-section h2 {
  margin: 0 0 8px;
  font-size: 16px;
}

.tbm-top-risks {
  margin: 0;
  padding-left: 20px;
}

.signature-image {
  width: 140px;
  max-height: 60px;
  object-fit: contain;
  border: 1px solid #d1d5db;
  background: #fff;
}

.empty-sign {
  color: #6b7280;
}

@media (max-width: 768px) {
  .tbm-meta-grid {
    grid-template-columns: 1fr;
  }
  .signature-image {
    width: 100px;
  }
}

@media print {
  .no-print {
    display: none !important;
  }
  .tbm-paper {
    border: none;
    border-radius: 0;
    padding: 0;
  }
  .tbm-view-page {
    background: #fff;
  }
  @page {
    size: A4;
    margin: 12mm;
  }
}
</style>
