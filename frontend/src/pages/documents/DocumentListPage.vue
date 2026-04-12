<template>
  <div class="card">
    <div class="card-title">문서 목록</div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <select v-model="queueFilter">
          <option value="">전체 큐</option>
          <option value="PENDING">미결재</option>
          <option value="HISTORY">승인/반려 이력</option>
        </select>
        <select v-model="statusFilter">
          <option value="">전체 상태</option>
          <option value="DRAFT">임시저장</option>
          <option value="SUBMITTED">제출</option>
          <option value="UNDER_REVIEW">검토중</option>
          <option value="APPROVED">승인</option>
          <option value="REJECTED">반려</option>
          <option value="RESUBMITTED">재제출</option>
        </select>
        <select v-model="documentTypeFilter">
          <option value="">전체 종류</option>
          <option value="LEGAL_DOC">법정서류</option>
          <option value="DAILY_DOC">일상점검</option>
          <option value="INSPECTION">점검</option>
          <option value="OPINION_RELATED">의견 관련</option>
          <option value="BUDGET">예산</option>
          <option value="ACCIDENT">사고</option>
          <option value="ETC">기타</option>
        </select>
      </div>
      <div class="toolbar-actions">
        <button class="secondary" @click="load">조회</button>
        <button v-if="isSite" class="primary" @click="goUpload">신규 문서등록</button>
      </div>
    </div>
    <table class="basic-table">
      <thead>
        <tr>
          <th>문서번호</th>
          <th>제목</th>
          <th>카테고리</th>
          <th>현장</th>
          <th>상태</th>
          <th>코멘트</th>
          <th>제출자</th>
          <th>제출일</th>
          <th>액션</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in filteredDocuments" :key="doc.id">
          <td>{{ doc.document_no }}</td>
          <td>
            <button type="button" class="link-btn" @click="goDetail(doc.id)">{{ doc.title }}</button>
          </td>
          <td>{{ categoryLabel(doc.document_type) }}</td>
          <td>{{ doc.site_id }}</td>
          <td>
            <span class="badge" :class="`badge-status-${doc.current_status}`">
              {{ statusLabel(doc.current_status) }}
            </span>
          </td>
          <td>{{ doc.rejection_reason || "-" }}</td>
          <td>{{ doc.submitter_user_id }}</td>
          <td>{{ doc.submitted_at ? doc.submitted_at.slice(0, 10) : "-" }}</td>
          <td>
            <button type="button" class="secondary" @click="goDetail(doc.id)">상세</button>
          </td>
        </tr>
        <tr v-if="filteredDocuments.length === 0">
          <td colspan="9" style="text-align: center; color: #6b7280">데이터가 없습니다.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface DocumentListItem {
  id: number;
  document_no: string;
  title: string;
  site_id: number;
  submitter_user_id: number;
  current_status: string;
  document_type: string;
  submitted_at: string | null;
  rejection_reason: string | null;
}

const documents = ref<DocumentListItem[]>([]);
const queueFilter = ref("");
const statusFilter = ref("");
const documentTypeFilter = ref("");

const auth = useAuthStore();
const router = useRouter();

const isSite = computed(() => auth.effectiveUiType === "SITE");
const filteredDocuments = computed(() => {
  const q = queueFilter.value;
  if (q === "PENDING") {
    return documents.value.filter((doc) => ["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED"].includes(doc.current_status));
  }
  if (q === "HISTORY") {
    return documents.value.filter((doc) => ["APPROVED", "REJECTED"].includes(doc.current_status));
  }
  return documents.value;
});

async function load() {
  const res = await api.get("/documents", {
    params: {
      status_filter: statusFilter.value || undefined,
      document_type: documentTypeFilter.value || undefined,
    },
  });
  documents.value = res.data;
}

function goDetail(id: number) {
  if (auth.effectiveUiType === "SITE") {
    router.push({ name: "site-document-detail", params: { id } });
    return;
  }
  if (auth.effectiveUiType === "HQ_OTHER") {
    router.push({ name: "hq-other-document-detail", params: { id } });
    return;
  }
  router.push({ name: "hq-safe-document-detail", params: { id } });
}

function goUpload() {
  router.push({ name: "site-document-upload" });
}

onMounted(load);

function statusLabel(status: string) {
  const map: Record<string, string> = {
    DRAFT: "임시저장",
    SUBMITTED: "제출됨",
    UNDER_REVIEW: "검토중",
    APPROVED: "승인",
    REJECTED: "반려",
    RESUBMITTED: "재제출",
  };
  return map[status] ?? status;
}

function categoryLabel(type: string) {
  const map: Record<string, string> = {
    LEGAL_DOC: "법적 서류",
    DAILY_DOC: "일상점검",
    INSPECTION: "점검",
    OPINION_RELATED: "의견 관련",
    BUDGET: "예산",
    ACCIDENT: "사고",
    ETC: "기타",
  };
  return map[type] ?? type;
}
</script>

<style scoped>
.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: #1d4ed8;
  cursor: pointer;
  text-align: left;
}
</style>

