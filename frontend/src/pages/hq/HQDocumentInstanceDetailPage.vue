<template>
  <div class="hq-doc-page inst-detail-page">
    <div class="inst-detail-toolbar">
      <button type="button" class="stitch-btn-secondary" @click="goBack">← 문서취합으로</button>
    </div>

    <p v-if="loadError" class="detail-error-banner">{{ loadError }}</p>
    <p v-else-if="loading" class="sub">불러오는 중...</p>

    <template v-else-if="currentRow">
      <BaseCard class="main-panel !p-[22px] inst-detail-header-card">
        <div class="inst-detail-header">
          <div>
            <h1 class="inst-detail-title">{{ currentRow.document_name }}</h1>
            <p class="sub m-0">{{ displaySiteName(currentRow.site_name) }}</p>
          </div>
          <span class="status-badge-lg" :class="headerBadgeClass(currentRow)">{{ headerStatusLabel(currentRow) }}</span>
        </div>
        <dl class="inst-meta-grid">
          <div><dt>주기 기준</dt><dd>{{ currentRow.period_basis }}</dd></div>
          <div><dt>회차</dt><dd>{{ currentRow.period_label }}</dd></div>
          <div><dt>문서 코드</dt><dd>{{ currentRow.document_type_code }}</dd></div>
        </dl>
      </BaseCard>

      <BaseCard class="main-panel !p-[22px] mt-4" title="현재 제출본">
        <template v-if="!currentRow.document_id">
          <p class="sub m-0">연결된 제출 문서가 없습니다.</p>
        </template>
        <template v-else>
          <dl class="inst-meta-grid">
            <div><dt>파일명</dt><dd>{{ currentRow.current_file_name || "—" }}</dd></div>
            <div><dt>업로드 시각</dt><dd>{{ formatDateTime(currentRow.submitted_at) }}</dd></div>
            <div><dt>업로더</dt><dd>{{ currentRow.uploaded_by_name || "—" }}</dd></div>
          </dl>
          <div class="inst-actions-row">
            <button
              type="button"
              class="stitch-btn-secondary"
              :disabled="!canPreviewFile"
              @click="openPreview"
            >
              보기
            </button>
            <button type="button" class="stitch-btn-primary" @click="downloadFile">다운로드</button>
          </div>
        </template>
      </BaseCard>

      <BaseCard class="main-panel !p-[22px] mt-4" title="검토 / 결재">
        <dl class="inst-meta-grid">
          <div><dt>현재 상태</dt><dd>{{ workflowUiLabel(currentRow.workflow_status, currentRow.is_missing) }}</dd></div>
          <div><dt>검토자</dt><dd>—</dd></div>
          <div><dt>검토 시각</dt><dd>{{ formatDateTime(currentRow.reviewed_at) }}</dd></div>
          <div class="span-2"><dt>반려 사유</dt><dd>{{ currentRow.review_note || "—" }}</dd></div>
        </dl>
        <div v-if="currentRow.document_id" class="review-form">
          <label class="review-label">검토 의견 (반려 시 필수)</label>
          <textarea v-model="reviewComment" class="review-textarea" rows="3" placeholder="의견을 입력하세요" />
          <p v-if="reviewError" class="detail-error-banner">{{ reviewError }}</p>
          <div class="inst-actions-row">
            <button
              type="button"
              class="stitch-btn-primary"
              :disabled="!canApplyReview || reviewSubmitting"
              @click="submitReview('approve')"
            >
              승인
            </button>
            <button
              type="button"
              class="stitch-btn-secondary"
              :disabled="!canApplyReview || reviewSubmitting || !reviewComment.trim()"
              @click="submitReview('reject')"
            >
              반려
            </button>
          </div>
        </div>
        <p v-else class="sub m-0">제출된 문서가 없어 검토할 수 없습니다.</p>
      </BaseCard>

      <BaseCard class="main-panel !p-[22px] mt-4" title="회차 히스토리">
        <p v-if="historyLoading" class="sub m-0 mb-2">히스토리를 불러오는 중...</p>
        <p v-else-if="historyLoadError" class="detail-error-banner m-0 mb-2">{{ historyLoadError }}</p>
        <div class="stitch-table-shell">
          <table class="stitch-table">
            <thead>
              <tr>
                <th>회차</th>
                <th>제출일</th>
                <th>검토일</th>
                <th>상태</th>
                <th>재업로드</th>
                <th>반려사유</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in historyItems" :key="r.instance_id">
                <td>{{ r.period_label }}</td>
                <td>{{ formatDateTime(r.submitted_at) }}</td>
                <td>{{ formatDateTime(r.reviewed_at) }}</td>
                <td>{{ workflowUiLabel(r.workflow_status, r.is_missing) }}</td>
                <td>{{ r.reupload_count }}</td>
                <td class="cell-note">{{ r.review_note || "—" }}</td>
              </tr>
              <tr v-if="!historyLoading && !historyLoadError && historyItems.length === 0">
                <td colspan="6" class="sub">히스토리가 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </BaseCard>
    </template>

    <div v-if="previewOpen" class="modal-backdrop" @click.self="closePreview">
      <div class="preview-card stitch-data-card">
        <div class="preview-head">
          <strong>파일 미리보기</strong>
          <button type="button" class="stitch-btn-secondary" @click="closePreview">닫기</button>
        </div>
        <iframe v-if="previewKind === 'pdf'" :src="previewUrl || ''" class="preview-frame" title="preview" />
        <div v-else-if="previewKind === 'image'" class="preview-img-wrap">
          <img v-if="previewUrl" :src="previewUrl" alt="preview" class="preview-img" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import { BaseCard } from "@/components/product";
import { canPreviewInBrowser, isImageFile, isPdfFile } from "@/utils/filePreview";

interface HistoryRow {
  instance_id: number;
  site_id: number;
  site_name: string;
  document_type_code: string;
  document_name: string;
  period_basis: string;
  period_start: string;
  period_end: string;
  period_label: string;
  instance_status: string;
  workflow_status: string;
  is_missing: boolean;
  document_id: number | null;
  current_file_name?: string | null;
  uploaded_by_name?: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  review_result: string | null;
  submission_count: number;
  reupload_count: number;
}

interface DocumentRecord {
  id: number;
  current_status: string;
  document_no: string;
  title: string;
  file_path: string | null;
}

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const loadError = ref("");
const historyLoading = ref(false);
const historyLoadError = ref("");
const historyItems = ref<HistoryRow[]>([]);
const currentRow = ref<HistoryRow | null>(null);
const documentRecord = ref<DocumentRecord | null>(null);
const reviewComment = ref("");
const reviewError = ref("");
const reviewSubmitting = ref(false);

const previewOpen = ref(false);
const previewUrl = ref<string | null>(null);
const previewKind = ref<"pdf" | "image" | null>(null);
const HQ_DOCUMENT_REFRESH_EVENT = "besma-hq-documents-refresh";

const instanceIdNum = computed(() => Number(route.params.instanceId));
const querySiteId = computed(() => {
  const raw = route.query.site_id;
  if (typeof raw !== "string") return null;
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
});
const queryDocType = computed(() => {
  const raw = route.query.document_type_code;
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
});

const canPreviewFile = computed(() =>
  Boolean(currentRow.value?.document_id && canPreviewInBrowser(currentRow.value?.current_file_name)),
);

const canApplyReview = computed(() => {
  const st = documentRecord.value?.current_status;
  return Boolean(currentRow.value?.document_id && st && (st === "SUBMITTED" || st === "IN_REVIEW"));
});

function displaySiteName(siteName: string) {
  if (siteName.includes("청라C18") || siteName.includes("C18BL")) {
    return `(삼성인정제) ${siteName}`;
  }
  return siteName;
}

function formatDateTime(value: string | null) {
  if (!value) return "—";
  return value.slice(0, 16).replace("T", " ");
}

function workflowUiLabel(workflow: string, isMissing: boolean) {
  if (isMissing) return "누락";
  if (workflow === "NOT_SUBMITTED") return "제출대기";
  if (workflow === "UNDER_REVIEW" || workflow === "SUBMITTED") return "검토중";
  if (workflow === "APPROVED") return "승인";
  if (workflow === "REJECTED") return "반려";
  return workflow;
}

function headerStatusLabel(row: HistoryRow) {
  return workflowUiLabel(row.workflow_status, row.is_missing);
}

function headerBadgeClass(row: HistoryRow) {
  if (row.is_missing) return "badge-missing";
  const w = row.workflow_status;
  if (w === "APPROVED") return "badge-approved";
  if (w === "REJECTED") return "badge-rejected";
  if (w === "UNDER_REVIEW" || w === "SUBMITTED") return "badge-review";
  return "badge-pending";
}

function goBack() {
  const sid = currentRow.value?.site_id ?? querySiteId.value;
  if (sid != null) {
    router.push({ name: "hq-safe-documents", query: { site_id: String(sid) } });
  } else {
    router.push({ name: "hq-safe-documents" });
  }
}

function notifyHqDocumentRefresh() {
  window.dispatchEvent(new CustomEvent(HQ_DOCUMENT_REFRESH_EVENT));
  try {
    localStorage.setItem(HQ_DOCUMENT_REFRESH_EVENT, String(Date.now()));
  } catch {
    // localStorage unavailable environments can ignore cross-tab sync.
  }
}

async function loadDocumentMeta(documentId: number) {
  try {
    const res = await api.get<DocumentRecord>(`/documents/${documentId}`);
    documentRecord.value = res.data;
  } catch {
    documentRecord.value = null;
  }
}

async function loadAll() {
  loadError.value = "";
  historyLoadError.value = "";
  currentRow.value = null;
  historyItems.value = [];
  documentRecord.value = null;

  const id = instanceIdNum.value;
  if (!Number.isInteger(id) || id <= 0) {
    loadError.value = "잘못된 인스턴스 ID입니다.";
    loading.value = false;
    return;
  }

  loading.value = true;
  try {
    const res = await api.get<HistoryRow>(`/document-instances/${id}`);
    currentRow.value = res.data;
    if (res.data.document_id) {
      await loadDocumentMeta(res.data.document_id);
    }
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) {
      loadError.value = "인스턴스를 찾을 수 없습니다.";
    } else {
      loadError.value = "인스턴스 정보를 불러오지 못했습니다.";
    }
    return;
  } finally {
    loading.value = false;
  }

  const row = currentRow.value;
  if (!row) return;

  historyLoading.value = true;
  try {
    const sid = querySiteId.value ?? row.site_id;
    const code = (queryDocType.value ?? row.document_type_code).trim();
    if (!code) {
      historyLoadError.value = "문서 유형 코드를 알 수 없어 히스토리를 조회할 수 없습니다.";
      return;
    }
    const hres = await api.get<{ items: HistoryRow[] }>("/document-instances/history", {
      params: { site_id: sid, document_type_code: code, limit: 500 },
    });
    historyItems.value = hres.data.items ?? [];
  } catch {
    historyLoadError.value = "히스토리 목록을 불러오지 못했습니다.";
  } finally {
    historyLoading.value = false;
  }
}

async function submitReview(action: "approve" | "reject") {
  const docId = currentRow.value?.document_id;
  if (!docId || !canApplyReview.value) return;
  reviewError.value = "";
  const comment =
    reviewComment.value.trim() || (action === "approve" ? "HQ 승인" : "HQ 반려");
  reviewSubmitting.value = true;
  try {
    await api.post(`/documents/${docId}/review`, { action, comment });
    reviewComment.value = "";
    await loadAll();
    notifyHqDocumentRefresh();
  } catch {
    try {
      await api.post(`/documents/${docId}/review`, {
        action: "start_review",
        comment: "HQ 검토 시작",
      });
      await api.post(`/documents/${docId}/review`, { action, comment });
      reviewComment.value = "";
      await loadAll();
      notifyHqDocumentRefresh();
    } catch {
      reviewError.value = "승인/반려 처리에 실패했습니다. 잠시 후 다시 시도해 주세요.";
    }
  } finally {
    reviewSubmitting.value = false;
  }
}

async function openPreview() {
  const docId = currentRow.value?.document_id;
  const name = currentRow.value?.current_file_name;
  if (!docId || !canPreviewInBrowser(name)) return;
  const res = await api.get(`/documents/${docId}/file`, {
    params: { disposition: "inline" },
    responseType: "blob",
  });
  const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
  const blob = new Blob([res.data], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  if (isPdfFile(name)) {
    previewKind.value = "pdf";
    previewUrl.value = url;
    previewOpen.value = true;
    return;
  }
  if (isImageFile(name)) {
    previewKind.value = "image";
    previewUrl.value = url;
    previewOpen.value = true;
    return;
  }
  window.open(url, "_blank", "noopener");
  setTimeout(() => window.URL.revokeObjectURL(url), 5000);
}

function closePreview() {
  previewOpen.value = false;
  previewKind.value = null;
  if (previewUrl.value) {
    window.URL.revokeObjectURL(previewUrl.value);
  }
  previewUrl.value = null;
}

async function downloadFile() {
  const docId = currentRow.value?.document_id;
  if (!docId) return;
  const res = await api.get(`/documents/${docId}/file`, {
    params: { disposition: "attachment" },
    responseType: "blob",
  });
  const blob = new Blob([res.data]);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = currentRow.value?.current_file_name || "document.bin";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

onMounted(loadAll);

watch(
  () => [route.params.instanceId, route.query.site_id, route.query.document_type_code],
  () => {
    void loadAll();
  },
);
</script>

<style scoped>
.inst-detail-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px 20px 32px;
}

.inst-detail-toolbar {
  margin-bottom: 16px;
}

.inst-detail-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.inst-detail-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.inst-meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px 20px;
  margin: 16px 0 0;
}

.inst-meta-grid .span-2 {
  grid-column: 1 / -1;
}

.inst-meta-grid dt {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin: 0 0 4px;
}

.inst-meta-grid dd {
  margin: 0;
  color: #334155;
  font-size: 14px;
}

.status-badge-lg {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.badge-approved {
  background: #dcfce7;
  color: #166534;
}
.badge-rejected,
.badge-missing {
  background: #fee2e2;
  color: #b91c1c;
}
.badge-review {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge-pending {
  background: #f1f5f9;
  color: #475569;
}

.inst-actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.review-form {
  margin-top: 16px;
}

.review-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}

.review-textarea {
  width: 100%;
  max-width: 560px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  resize: vertical;
}

.detail-error-banner {
  color: #b91c1c;
  font-size: 14px;
  margin: 8px 0;
}

.cell-note {
  max-width: 240px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mt-4 {
  margin-top: 16px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 80;
  padding: 16px;
}

.preview-card {
  width: 100%;
  max-width: 960px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preview-frame {
  width: 100%;
  height: 72vh;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.preview-img-wrap {
  display: flex;
  justify-content: center;
  max-height: 72vh;
}

.preview-img {
  max-width: 100%;
  max-height: 72vh;
  object-fit: contain;
}
</style>
