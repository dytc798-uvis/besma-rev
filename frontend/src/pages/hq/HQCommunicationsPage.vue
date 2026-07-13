<template>
  <div class="card comm-page">
    <div class="header-row">
      <div>
        <div class="card-title">본사-현장 소통</div>
        <p class="helper">본사와 현장이 주고받은 모든 문서 코멘트와 승인 의견을 최신순으로 확인합니다.</p>
      </div>
      <button type="button" class="secondary" @click="loadItems">새로고침</button>
    </div>

    <div v-if="loading" class="empty">불러오는 중...</div>
    <div v-else-if="rows.length === 0" class="empty">표시할 소통 항목이 없습니다.</div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>시각</th>
            <th>현장</th>
            <th>작성자</th>
            <th>구분</th>
            <th>개선루프</th>
            <th>내용</th>
            <th>문서</th>
            <th>확인</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.item_key" :class="{ unread: !row.is_read }">
            <td>{{ formatDate(row.created_at) }}</td>
            <td>{{ row.site_name }}</td>
            <td>{{ row.user_name }}</td>
            <td><span class="document-type">{{ documentTypeLabel(row.document_type) }}</span></td>
            <td>
              <span class="loop-pill">{{ row.loop_status_label || loopLabel(row.loop_status) }}</span>
            </td>
            <td class="comment">{{ row.comment_text || "-" }}</td>
            <td>
              <button type="button" class="secondary" @click="goDetail(row.document_id)">문서보기</button>
            </td>
            <td>
              <span class="confirm-pill" :class="{ pending: !row.is_read }">
                {{ row.is_read ? "확인됨" : "미확인" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { feedbackLoopLabelKo } from "@/utils/feedbackLoopLabels";
import { formatDateTimeKst } from "@/utils/datetime";

interface CommunicationItemRow {
  item_key: string;
  source: "comment" | "approval";
  document_id: number;
  document_type: string;
  site_name: string;
  user_name: string;
  comment_text: string | null;
  created_at: string;
  is_read: boolean;
  loop_status: string;
  loop_status_label: string;
}

const router = useRouter();
const loading = ref(false);
const rows = ref<CommunicationItemRow[]>([]);

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  DAILY_TBM: "TBM",
  DAILY_RISK_ASSESSMENT: "위험성평가",
  ADHOC_RISK_ASSESSMENT: "수시위험성평가",
  DAILY_SAFETY_MEETING_LOG: "안전회의",
  SUPERVISOR_CHECKLIST: "관리감독자점검",
  SITE_MANAGER_CHECKLIST: "소장점검",
  SAFETY_MANAGER_DAILY_LOG: "안전일지",
  AUTO_WORKER_OPINION_LOG: "근로자의견",
  REGULAR_EDUCATION: "정기교육",
  SPECIAL_EDUCATION: "특별교육",
  MSDS_EDUCATION: "MSDS교육",
  EMERGENCY_DRILL_REPORT: "비상훈련",
  NONCONFORMITY_ACTION_REPORT: "부적합조치",
  DAILY_DOC: "일일문서",
  INSPECTION: "점검",
  ACCIDENT: "사고",
  BUDGET: "예산",
};

function formatDate(value: string) {
  return formatDateTimeKst(value, value);
}

function documentTypeLabel(code: string) {
  return DOCUMENT_TYPE_LABELS[(code || "").trim().toUpperCase()] ?? "기타문서";
}

function loopLabel(status: string) {
  return feedbackLoopLabelKo(status);
}

function goDetail(documentId: number) {
  void router.push({ name: "hq-safe-document-detail", params: { id: String(documentId) } });
}

async function loadItems() {
  loading.value = true;
  try {
    const res = await api.get("/documents/hq-communications", { params: { limit: 1000 } });
    rows.value = (res.data?.items ?? []) as CommunicationItemRow[];
  } finally {
    loading.value = false;
  }
}

onMounted(loadItems);
</script>

<style scoped>
.comm-page {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.helper {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}
.table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}
.table th,
.table td {
  border: 1px solid #e2e8f0;
  padding: 8px;
  font-size: 13px;
  text-align: left;
  vertical-align: top;
}
.table thead th {
  background: #f8fafc;
  font-weight: 700;
}
.table tr.unread {
  background: #fff7ed;
  box-shadow: inset 4px 0 #f97316;
  font-weight: 600;
}
.comment {
  white-space: pre-wrap;
}
.empty {
  color: #64748b;
}
.loop-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
.document-type,
.confirm-pill {
  display: inline-block;
  white-space: nowrap;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 8px;
}
.document-type {
  background: #e0f2fe;
  color: #075985;
}
.confirm-pill {
  background: #ecfdf5;
  color: #047857;
}
.confirm-pill.pending {
  background: #ffedd5;
  color: #c2410c;
}
</style>
