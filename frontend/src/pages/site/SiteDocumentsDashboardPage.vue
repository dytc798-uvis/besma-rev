<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">현장 문서취합 (Requirement 기반)</div>
      <div class="controls">
        <button class="secondary" @click="load">새로고침</button>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-card">제출 대상 {{ summary.total_required }}</div>
      <div class="summary-card">미완료 {{ incompleteCount }}</div>
      <div class="summary-card">반려 {{ summary.rejected_count }}</div>
      <div class="summary-card">승인완료 {{ summary.approved_count }}</div>
    </div>

    <section class="section-card">
      <div class="section-head">
        <h3>전체 서류</h3>
      </div>
      <table class="basic-table">
      <thead>
        <tr>
          <th>Req ID</th>
          <th>문서명</th>
          <th>구분</th>
          <th>카테고리</th>
          <th>주기</th>
          <th>상태</th>
          <th>최근 제출</th>
          <th>액션</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="item in sortedItems" :key="item.requirement_id">
        <tr>
          <td><code>{{ item.requirement_id }}</code></td>
          <td>{{ item.title }}</td>
          <td>{{ sectionLabel(item.section) }}</td>
          <td>{{ categoryLabel(item.category) }}</td>
          <td>{{ frequencyLabel(item.frequency) }}</td>
          <td>
            <span class="badge" :class="statusClass(item.status)">
              {{ statusLabel(item.status) }}
            </span>
          </td>
          <td>{{ formatDateTime(item.latest_uploaded_at) }}</td>
          <td class="actions">
            <button class="secondary" :disabled="item.section === 'COMPLETION' && !completionUploadEnabled" @click="openUpload(item)">
              {{ item.status === "REJECTED" ? "수정 업로드" : "업로드" }}
            </button>
            <button
              v-if="item.latest_document_id"
              class="secondary"
              :class="{ danger: item.status === 'REJECTED' }"
              @click="toggleConversation(item)"
            >
              보기
            </button>
            <button class="secondary" @click="openHistory(item)">이력 보기</button>
          </td>
        </tr>
        <tr v-if="isConversationOpen(item.requirement_id)" class="conversation-row">
          <td colspan="8" class="conversation-cell">
            <p class="conversation-text">
              {{ item.review_note || "코멘트가 없습니다." }}
            </p>
          </td>
        </tr>
        </template>
        <tr v-if="sortedItems.length === 0">
          <td colspan="8" style="text-align: center; color: #6b7280">표시할 서류가 없습니다.</td>
        </tr>
      </tbody>
      </table>
    </section>
  </div>

  <div v-if="uploadTarget" class="modal-backdrop" @click.self="closeUpload">
    <div class="modal-card">
      <div class="card-title">{{ uploadTarget?.status === "REJECTED" ? "문서 수정 업로드" : "문서 업로드" }}</div>
      <p class="upload-title">{{ uploadTarget.title }}</p>
      <p class="upload-note">Req ID: {{ uploadTarget.requirement_id }} · {{ sectionLabel(uploadTarget.section) }}</p>
      <p v-if="uploadTarget.review_note" class="upload-reject-note">
        반려 사유: {{ uploadTarget.review_note }}
      </p>
      <input type="file" @change="onFileChange" />
      <div class="modal-actions">
        <button class="secondary" @click="closeUpload">취소</button>
        <button class="primary" :disabled="!selectedFile || uploading" @click="submitUpload">
          {{ uploading ? "업로드 중..." : uploadTarget?.status === "REJECTED" ? "수정 업로드" : "업로드" }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="historyTarget" class="modal-backdrop" @click.self="closeHistory">
    <div class="modal-card history-card">
      <div class="card-title">문서 이력 - {{ historyTarget.title }}</div>
      <table class="basic-table">
        <thead>
          <tr>
            <th>버전</th>
            <th>상태</th>
            <th>업로드시각</th>
            <th>review_note</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in historyItems" :key="row.history_id">
            <td>v{{ row.version_no }}</td>
            <td>{{ statusLabel(row.status) }}</td>
            <td>{{ formatDateTime(row.uploaded_at) }}</td>
            <td>{{ row.review_note || "-" }}</td>
          </tr>
        </tbody>
      </table>
      <div class="modal-actions">
        <button class="secondary" @click="closeHistory">닫기</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface RequirementStatusItem {
  requirement_id: number;
  document_type_code: string;
  title: string;
  frequency: string;
  is_required: boolean;
  status: string;
  latest_document_id: number | null;
  latest_uploaded_at: string | null;
  review_note: string | null;
  category: string | null;
  section: string | null;
  completion_upload_enabled: boolean;
}
interface HistoryItem {
  history_id: number;
  version_no: number;
  status: string;
  uploaded_at: string | null;
  review_note: string | null;
}

const auth = useAuthStore();

const targetDate = ref(new Date().toISOString().slice(0, 10));
const items = ref<RequirementStatusItem[]>([]);
const completionUploadEnabled = ref(false);
const summary = ref({
  total_required: 0,
  submitted_count: 0,
  approved_count: 0,
  not_submitted_count: 0,
  rejected_count: 0,
  in_review_count: 0,
});

const uploadTarget = ref<RequirementStatusItem | null>(null);
const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const historyTarget = ref<RequirementStatusItem | null>(null);
const historyItems = ref<HistoryItem[]>([]);
const openedConversationRequirementId = ref<number | null>(null);

const siteId = computed(() => auth.effectiveSiteId ?? auth.user?.site_id ?? null);
const incompleteCount = computed(() => summary.value.not_submitted_count + summary.value.in_review_count + summary.value.rejected_count);
const sortedItems = computed(() => {
  const validItems = items.value.filter((item) => isDisplayableRequirementId(item.requirement_id));
  const statusPriority: Record<string, number> = {
    REJECTED: 0,
    NOT_SUBMITTED: 1,
    IN_REVIEW: 2,
    SUBMITTED: 3,
    NOT_REQUIRED: 4,
    APPROVED: 99,
  };
  return [...validItems].sort((a, b) => {
    const pa = statusPriority[a.status] ?? 50;
    const pb = statusPriority[b.status] ?? 50;
    if (pa !== pb) return pa - pb;
    return a.requirement_id - b.requirement_id;
  });
});

function statusLabel(status: string) {
  const map: Record<string, string> = {
    NOT_REQUIRED: "비대상",
    NOT_SUBMITTED: "제출대기",
    SUBMITTED: "검토대기",
    IN_REVIEW: "검토중",
    APPROVED: "승인",
    REJECTED: "반려 (재업로드 필요)",
  };
  return map[status] ?? status;
}

function categoryLabel(category: string | null | undefined) {
  const map: Record<string, string> = {
    MOEL_GENERAL: "노동부 일반",
    MOEL_SAFETY: "노동부 안전",
    MIDDLE_LAW: "중처법",
    INTERNAL_RULE: "사규",
    GENERAL: "일반",
  };
  if (!category) return "-";
  return map[category] ?? category;
}

function sectionLabel(section: string | null | undefined) {
  if (section === "COMPLETION") return "준공서류";
  return "법적 서류";
}

function frequencyLabel(frequency: string | null | undefined) {
  const key = (frequency || "").toUpperCase();
  const map: Record<string, string> = {
    DAILY: "일별",
    WEEKLY: "주별",
    MONTHLY: "월별",
    HALF_YEARLY: "반기",
    YEARLY: "연간",
    QUARTERLY: "분기",
    ROLLING: "수시",
    ADHOC: "수시",
    EVENT: "이벤트",
    ONE_TIME: "1회",
  };
  return map[key] ?? frequency ?? "-";
}

function statusClass(status: string) {
  return `badge-status-${status}`;
}

function isDisplayableRequirementId(requirementId: unknown) {
  if (typeof requirementId !== "number") return false;
  if (!Number.isFinite(requirementId)) return false;
  return requirementId > 0;
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
}

async function load() {
  if (!siteId.value) return;
  const res = await api.get("/documents/requirements/status", {
    params: {
      site_id: siteId.value,
      period: "all",
      date: targetDate.value,
    },
  });
  items.value = res.data.items;
  summary.value = res.data.summary;
  completionUploadEnabled.value = !!res.data.completion_upload_enabled;
}

function toggleConversation(item: RequirementStatusItem) {
  const rid = item.requirement_id;
  openedConversationRequirementId.value = openedConversationRequirementId.value === rid ? null : rid;
}

function isConversationOpen(requirementId: number) {
  return openedConversationRequirementId.value === requirementId;
}

function openUpload(item: RequirementStatusItem) {
  uploadTarget.value = item;
  selectedFile.value = null;
}

function closeUpload() {
  uploadTarget.value = null;
  selectedFile.value = null;
}

async function openHistory(item: RequirementStatusItem) {
  if (!siteId.value) return;
  historyTarget.value = item;
  const res = await api.get("/documents/history", {
    params: {
      site_id: siteId.value,
      requirement_id: item.requirement_id,
    },
  });
  historyItems.value = res.data.items;
}

function closeHistory() {
  historyTarget.value = null;
  historyItems.value = [];
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
}

async function submitUpload() {
  if (!uploadTarget.value || !selectedFile.value || !siteId.value) return;
  if (uploadTarget.value.section === "COMPLETION" && !completionUploadEnabled.value) return;
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("site_id", String(siteId.value));
    form.append("requirement_id", String(uploadTarget.value.requirement_id));
    form.append("document_type_code", uploadTarget.value.document_type_code);
    form.append("work_date", targetDate.value);
    form.append("file", selectedFile.value);
    await api.post("/document-submissions/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    closeUpload();
    await load();
  } finally {
    uploading.value = false;
  }
}

onMounted(async () => {
  if (auth.token) {
    await auth.loadMe();
  }
  await load();
});
</script>

<style scoped>
.section-card { margin-top: 12px; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; background: #fff; }
.section-head h3 { margin: 0; font-size: 15px; }
.section-head p { margin: 4px 0 10px; color: #475569; font-size: 12px; }
.state-ok { color: #166534; margin-left: 8px; }
.state-off { color: #991b1b; margin-left: 8px; }
.completion-window-text { margin: 0 0 8px; font-size: 12px; color: #64748b; }
.review-note-cell { max-width: 280px; color: #334155; white-space: pre-wrap; word-break: break-word; }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.controls { display: flex; gap: 8px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
.summary-card { background: #f3f4f6; border-radius: 8px; padding: 10px; font-weight: 600; }
.actions { display: flex; gap: 6px; }
.secondary.danger { border-color: #ef4444; color: #b91c1c; background: #fef2f2; }
.conversation-row td { background: #fff; }
.conversation-cell { padding: 6px 10px 12px; }
.conversation-text { margin: 0; color: #b91c1c; font-weight: 700; white-space: pre-wrap; word-break: break-word; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(17, 24, 39, 0.4); display: flex; align-items: center; justify-content: center; }
.modal-card { width: 420px; background: #fff; border-radius: 8px; padding: 16px; }
.history-card { width: 760px; max-height: 80vh; overflow: auto; }
.upload-title { margin: 8px 0 12px; font-weight: 600; }
.upload-note { margin: -8px 0 10px; font-size: 12px; color: #64748b; }
.upload-reject-note { margin: 0 0 10px; font-size: 12px; color: #991b1b; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px; }
.modal-actions { margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px; }
</style>
