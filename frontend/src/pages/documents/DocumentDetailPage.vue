<template>
  <div class="card" v-if="doc">
    <div class="card-title">문서 상세</div>
    <p v-if="isLedgerManagedDoc" class="ledger-doc-banner">{{ ledgerManagedUxMessage }}</p>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; font-size: 13px">
      <div><strong>문서번호</strong> {{ doc.document_no }}</div>
      <div><strong>제목</strong> {{ doc.title }}</div>
      <div><strong>현장</strong> {{ doc.site_id }}</div>
      <div>
        <strong>상태</strong>
        <span class="badge" :class="`badge-status-${doc.current_status}`">
          {{ doc.current_status }}
        </span>
      </div>
      <div><strong>제출자</strong> {{ doc.submitter_user_id }}</div>
      <div><strong>버전</strong> v{{ doc.version_no }}</div>
      <div><strong>설명</strong> {{ doc.description || "-" }}</div>
      <div><strong>코멘트</strong> {{ doc.rejection_reason || "-" }}</div>
      <div>
        <strong>파일</strong>
        <button
          v-if="doc.file_path"
          type="button"
          class="secondary"
          :disabled="downloading"
          @click="downloadFile"
        >
          {{ downloading ? "다운로드 중..." : "다운로드" }}
        </button>
        <span v-else>-</span>
      </div>
    </div>
    <div style="margin-top: 16px" class="toolbar">
      <div></div>
      <div class="toolbar-actions">
        <button v-if="isLedgerManagedDoc" type="button" class="primary" @click="goLedgerFromDocumentDetail">관리대장에서 보기</button>
        <router-link
          v-if="doc && !isLedgerManagedDoc"
          class="secondary"
          :to="`/documents/${doc.id}/tbm-view`"
          style="display: inline-flex; align-items: center; text-decoration: none; padding: 6px 12px; border-radius: 4px; background-color: #e5e7eb; color: #111827;"
        >
          TBM 보기
        </router-link>
        <button
          v-if="canSubmit"
          class="primary"
          @click="submit('제출')"
          :disabled="loadingAction"
        >
          제출
        </button>
        <button
          v-if="canApprove"
          class="primary"
          @click="approve"
          :disabled="loadingAction"
        >
          승인
        </button>
        <button
          v-if="canApprove"
          class="secondary"
          @click="toggleReject"
          :disabled="loadingAction"
        >
          반려
        </button>
        <button
          v-if="canResubmit"
          class="primary"
          @click="resubmit"
          :disabled="loadingAction"
        >
          재제출
        </button>
      </div>
    </div>
    <div v-if="showReject && !isLedgerManagedDoc" style="margin-top: 12px">
      <label class="form-field">
        <span style="font-size: 12px">코멘트</span>
        <textarea v-model="rejectReason" rows="3"></textarea>
      </label>
      <div style="margin-top: 8px">
        <button class="primary" @click="reject" :disabled="loadingAction || !rejectReason">
          반려 확정
        </button>
      </div>
    </div>
    <DocumentCommentsPanel
      v-if="!isLedgerManagedDoc"
      :document-id="doc.id"
      :document-type-code="doc.document_type"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import DocumentCommentsPanel from "@/components/documents/DocumentCommentsPanel.vue";
import { useAuthStore } from "@/stores/auth";
import {
  hqLedgerRouteForDocumentType,
  isLedgerManagedDocumentType,
  LEDGER_MANAGED_UX_MESSAGE,
  siteLedgerRouteForDocumentType,
} from "@/utils/ledgerManagedDocument";

interface DocumentDetail {
  id: number;
  document_no: string;
  title: string;
  site_id: number;
  submitter_user_id: number;
  current_status: string;
  file_path: string | null;
  description: string | null;
  rejection_reason: string | null;
  version_no: number;
  document_type?: string | null;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const doc = ref<DocumentDetail | null>(null);
const loadingAction = ref(false);
const showReject = ref(false);
const rejectReason = ref("");
const downloading = ref(false);

const isLedgerManagedDoc = computed(() => isLedgerManagedDocumentType(doc.value?.document_type));
const ledgerManagedUxMessage = LEDGER_MANAGED_UX_MESSAGE;

const canApprove = computed(
  () => auth.user?.ui_type === "HQ_SAFE" && !isLedgerManagedDoc.value,
);
const canSubmit = computed(
  () => auth.user?.ui_type === "SITE" && doc.value?.current_status === "DRAFT" && !isLedgerManagedDoc.value,
);
const canResubmit = computed(
  () => auth.user?.ui_type === "SITE" && doc.value?.current_status === "REJECTED" && !isLedgerManagedDoc.value,
);

function goLedgerFromDocumentDetail() {
  const code = doc.value?.document_type;
  const isHq = auth.user?.ui_type === "HQ_SAFE";
  const name = isHq ? hqLedgerRouteForDocumentType(code || null) : siteLedgerRouteForDocumentType(code || null);
  const sid = doc.value?.site_id;
  if (!name) return;
  if (isHq && sid != null) void router.push({ name, query: { site_id: String(sid) } });
  else void router.push({ name });
}

async function load() {
  const res = await api.get(`/documents/${route.params.id}`);
  doc.value = res.data;
}

async function submit(comment: string) {
  if (!doc.value || isLedgerManagedDoc.value) return;
  loadingAction.value = true;
  try {
    await api.post(`/documents/${doc.value.id}/submit`, { comment });
    await load();
  } finally {
    loadingAction.value = false;
  }
}

async function approve() {
  if (!doc.value || isLedgerManagedDoc.value) return;
  loadingAction.value = true;
  try {
    await api.post(`/documents/${doc.value.id}/approve`, { comment: "" });
    await load();
  } finally {
    loadingAction.value = false;
  }
}

function toggleReject() {
  showReject.value = !showReject.value;
}

async function reject() {
  if (!doc.value || isLedgerManagedDoc.value) return;
  loadingAction.value = true;
  try {
    await api.post(`/documents/${doc.value.id}/reject`, { comment: rejectReason.value });
    await load();
    showReject.value = false;
  } finally {
    loadingAction.value = false;
  }
}

async function resubmit() {
  if (!doc.value || isLedgerManagedDoc.value) return;
  loadingAction.value = true;
  try {
    await api.post(`/documents/${doc.value.id}/resubmit`, { comment: "재제출" });
    await load();
  } finally {
    loadingAction.value = false;
  }
}

function resolveFilenameFromHeader(headerValue: string | undefined, fallback: string) {
  if (!headerValue) return fallback;
  const matchUtf = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (matchUtf?.[1]) {
    try {
      return decodeURIComponent(matchUtf[1]);
    } catch {
      return fallback;
    }
  }
  const matchPlain = headerValue.match(/filename=\"?([^\";]+)\"?/i);
  return matchPlain?.[1] ?? fallback;
}

async function downloadFile() {
  if (!doc.value?.file_path) return;
  downloading.value = true;
  try {
    const res = await api.get(`/documents/${doc.value.id}/file`, { responseType: "blob" });
    const blob = new Blob([res.data]);
    const contentDisposition = res.headers["content-disposition"] as string | undefined;
    const filename = resolveFilenameFromHeader(
      contentDisposition,
      `${doc.value.document_no || "document"}.bin`,
    );
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } finally {
    downloading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.ledger-doc-banner {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e3a8a;
  font-size: 13px;
  line-height: 1.45;
}
</style>
