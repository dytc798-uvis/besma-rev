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
    <div v-else class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>시각</th>
            <th>현장</th>
            <th>구분</th>
            <th>본사 코멘트</th>
            <th>현장 코멘트</th>
            <th>문서</th>
            <th>확인</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="group in groupedRows" :key="group.group_key" :class="{ unread: !group.is_read }">
            <td class="time-cell">{{ formatDate(group.created_at) }}</td>
            <td class="site-cell">{{ group.site_name }}</td>
            <td><span class="document-type">{{ documentTypeLabel(group.document_type) }}</span></td>
            <td class="comment-cell">
              <div v-if="group.hq_comments.length" class="comment-list">
                <div v-for="item in group.hq_comments" :key="item.item_key" class="comment-entry">
                  <div class="comment-meta">{{ item.user_name }} · {{ formatDate(item.created_at) }}</div>
                  <div class="comment-text" :title="item.comment_text || '-'">{{ item.comment_text || "-" }}</div>
                </div>
              </div>
              <span v-else class="empty-comment">-</span>
            </td>
            <td class="comment-cell">
              <div v-if="group.site_comments.length" class="comment-list">
                <div v-for="item in group.site_comments" :key="item.item_key" class="comment-entry">
                  <div class="comment-meta">{{ item.user_name }} · {{ formatDate(item.created_at) }}</div>
                  <div class="comment-text" :title="item.comment_text || '-'">{{ item.comment_text || "-" }}</div>
                </div>
              </div>
              <span v-else class="empty-comment">-</span>
            </td>
            <td class="document-cell">
              <button type="button" class="secondary document-button" @click="goDetail(group.document_id)">문서보기</button>
            </td>
            <td>
              <span class="confirm-pill" :class="{ pending: !group.is_read }">
                {{ group.is_read ? "확인됨" : "미확인" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
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
}

interface CommunicationGroupRow {
  group_key: string;
  document_id: number;
  document_type: string;
  site_name: string;
  created_at: string;
  is_read: boolean;
  hq_comments: CommunicationItemRow[];
  site_comments: CommunicationItemRow[];
}

const router = useRouter();
const loading = ref(false);
const rows = ref<CommunicationItemRow[]>([]);

const groupedRows = computed<CommunicationGroupRow[]>(() => {
  const groups = new Map<number, CommunicationGroupRow>();
  for (const row of rows.value) {
    let group = groups.get(row.document_id);
    if (!group) {
      group = {
        group_key: `document:${row.document_id}`,
        document_id: row.document_id,
        document_type: row.document_type,
        site_name: row.site_name,
        created_at: row.created_at,
        is_read: row.is_read,
        hq_comments: [],
        site_comments: [],
      };
      groups.set(row.document_id, group);
    } else if (!row.is_read) {
      group.is_read = false;
    }

    const target = row.user_role === "SITE" ? group.site_comments : group.hq_comments;
    if (target.length < 2) target.push(row);
  }
  return [...groups.values()];
});

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
  min-width: 1080px;
  table-layout: fixed;
  border-collapse: collapse;
  background: #fff;
}
.table-wrap {
  overflow-x: auto;
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
.table th:nth-child(1) {
  width: 132px;
}
.table th:nth-child(2) {
  width: 120px;
}
.table th:nth-child(3) {
  width: 112px;
}
.table th:nth-child(6) {
  width: 92px;
}
.table th:nth-child(7) {
  width: 76px;
}
.time-cell,
.site-cell {
  word-break: keep-all;
}
.comment-cell {
  min-width: 0;
}
.comment-list {
  display: grid;
  gap: 7px;
}
.comment-entry + .comment-entry {
  padding-top: 7px;
  border-top: 1px dashed #cbd5e1;
}
.comment-meta {
  margin-bottom: 2px;
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.comment-text {
  display: -webkit-box;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.empty-comment {
  color: #94a3b8;
}
.document-cell {
  text-align: center !important;
}
.document-button {
  min-width: 70px;
  padding-right: 9px;
  padding-left: 9px;
  white-space: nowrap;
}
.empty {
  color: #64748b;
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
