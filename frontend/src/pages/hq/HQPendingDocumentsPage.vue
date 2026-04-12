<template>
  <div class="pending-page">
    <header class="page-head">
      <h1 class="page-title">미결재 문서</h1>
      <p class="page-sub">검토가 필요한 제출 문서를 표로 확인하고 파일 확인 후 검토합니다.</p>
    </header>

    <BaseCard class="panel !p-[16px]">
      <template #head>
        <div class="panel-head">
          <div class="panel-head-left">
            <span class="count-badge">총 {{ filteredRows.length }}건</span>
            <div class="summary-inline">
              <span class="summary-pill">금일 {{ pendingSummary.day }}</span>
              <span class="summary-pill">7일 {{ pendingSummary.week }}</span>
              <span class="summary-pill">30일 {{ pendingSummary.month }}</span>
            </div>
          </div>
          <div class="panel-head-right">
            <input v-model="siteFilter" type="text" class="site-filter-input" placeholder="현장명 검색" />
            <button type="button" class="stitch-btn-secondary" @click="load">새로고침</button>
          </div>
        </div>
      </template>

      <div class="table-wrap">
        <table class="pending-table">
          <thead>
            <tr>
              <th>현장명</th>
              <th>문서명</th>
              <th>파일명</th>
              <th>상태</th>
              <th>제출일시</th>
              <th>제출자</th>
              <th>파일보기</th>
              <th>검토하기</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="`pending-${row.document_id}`">
              <td>{{ row.site_name }}</td>
              <td>{{ row.requirement_name }}</td>
              <td>{{ row.file_name || "-" }}</td>
              <td>{{ statusLabel(row.status) }}</td>
              <td>{{ formatDateTime(row.submitted_at || row.uploaded_at) }}</td>
              <td>{{ row.submitted_by || "-" }}</td>
              <td>
                <button
                  type="button"
                  class="link-btn"
                  :disabled="!row.document_id"
                  @click="openFile(row.document_id, row.file_name)"
                >
                  {{ canPreviewInBrowser(row.file_name) ? "파일열기" : "다운로드" }}
                </button>
                <p v-if="!canPreviewInBrowser(row.file_name)" class="hint">미리보기 미지원 형식</p>
              </td>
              <td>
                <button
                  type="button"
                  class="stitch-btn-secondary review-btn"
                  @click="goReview(row.site_id, row.requirement_id)"
                >
                  검토하기
                </button>
              </td>
            </tr>
            <tr v-if="filteredRows.length === 0">
              <td colspan="8" class="empty-cell">미결재 문서가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { BaseCard } from "@/components/product";
import { api } from "@/services/api";
import { canPreviewInBrowser } from "@/utils/filePreview";
import { formatDateTimeKst, toKstDateKey, todayKst } from "@/utils/datetime";

interface PendingRow {
  site_name: string;
  site_id: number;
  requirement_name: string;
  requirement_id: number | null;
  document_id: number;
  file_name: string | null;
  status: string;
  submitted_at: string | null;
  uploaded_at: string | null;
  submitted_by: string | null;
}

const router = useRouter();
const rows = ref<PendingRow[]>([]);
const siteFilter = ref("");
const HQ_DOCUMENT_REFRESH_EVENT = "besma-hq-documents-refresh";

const filteredRows = computed(() => {
  const query = siteFilter.value.trim().toLowerCase();
  if (!query) return rows.value;
  return rows.value.filter((row) => row.site_name.toLowerCase().includes(query));
});

const pendingSummary = computed(() => {
  const today = todayKst();
  const todayDate = new Date(`${today}T00:00:00+09:00`);
  let day = 0;
  let week = 0;
  let month = 0;
  for (const row of rows.value) {
    const raw = row.submitted_at || row.uploaded_at;
    if (!raw) continue;
    const key = toKstDateKey(raw);
    if (!key) continue;
    const targetDate = new Date(`${key}T00:00:00+09:00`);
    const diffDays = Math.floor((todayDate.getTime() - targetDate.getTime()) / 86400000);
    if (key === today) day += 1;
    if (diffDays >= 0 && diffDays <= 6) week += 1;
    if (diffDays >= 0 && diffDays <= 29) month += 1;
  }
  return { day, week, month };
});

function statusLabel(status: string) {
  if (status === "SUBMITTED") return "검토대기";
  if (status === "UNDER_REVIEW") return "검토중";
  return status;
}

function formatDateTime(value: string | null) {
  return formatDateTimeKst(value, "-");
}

async function load() {
  const res = await api.get("/documents/hq-pending");
  rows.value = res.data.items ?? [];
}

function handleHqDocumentRefresh() {
  void load();
}

function handleVisibilityChange() {
  if (document.visibilityState === "visible") {
    void load();
  }
}

function handleStorage(event: StorageEvent) {
  if (event.key === HQ_DOCUMENT_REFRESH_EVENT) {
    void load();
  }
}

function downloadBlob(blob: Blob, fallbackName: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fallbackName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

async function openFile(documentId: number, fileName: string | null) {
  const previewable = canPreviewInBrowser(fileName);
  const res = await api.get(`/documents/${documentId}/file`, {
    params: { disposition: previewable ? "inline" : "attachment" },
    responseType: "blob",
  });
  const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
  const blob = new Blob([res.data], { type: contentType });
  if (!previewable) {
    downloadBlob(blob, fileName || `document-${documentId}.bin`);
    return;
  }
  const url = window.URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => window.URL.revokeObjectURL(url), 5000);
}

function goReview(siteId: number, requirementId: number | null) {
  if (!requirementId) return;
  router.push({
    name: "hq-safe-documents",
    query: {
      site_id: String(siteId),
      review_site_id: String(siteId),
      review_requirement_id: String(requirementId),
    },
  });
}

onMounted(() => {
  void load();
  window.addEventListener("focus", handleHqDocumentRefresh);
  window.addEventListener(HQ_DOCUMENT_REFRESH_EVENT, handleHqDocumentRefresh as EventListener);
  window.addEventListener("storage", handleStorage);
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onUnmounted(() => {
  window.removeEventListener("focus", handleHqDocumentRefresh);
  window.removeEventListener(HQ_DOCUMENT_REFRESH_EVENT, handleHqDocumentRefresh as EventListener);
  window.removeEventListener("storage", handleStorage);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
});
</script>

<style scoped>
.page-head { margin-bottom: 12px; }
.page-title { margin: 0; font-size: 22px; font-weight: 700; color: #0f172a; }
.page-sub { margin: 4px 0 0; font-size: 13px; color: #64748b; }
.panel-head { display: flex; justify-content: space-between; align-items: center; width: 100%; gap: 10px; flex-wrap: wrap; }
.panel-head-left, .panel-head-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.count-badge { font-size: 12px; color: #334155; font-weight: 700; }
.summary-inline { display: flex; gap: 6px; flex-wrap: wrap; }
.summary-pill { background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 4px 8px; font-size: 12px; font-weight: 700; }
.site-filter-input { border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 10px; font-size: 12px; }
.table-wrap { overflow: auto; border: 1px solid #e2e8f0; border-radius: 10px; }
.pending-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.pending-table th, .pending-table td { border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }
.pending-table th { background: #f8fafc; font-weight: 700; white-space: nowrap; }
.empty-cell { text-align: center !important; color: #64748b; }
.link-btn { border: 0; background: transparent; color: #1d4ed8; cursor: pointer; padding: 0; }
.review-btn { padding: 4px 8px; font-size: 12px; }
.hint { margin: 2px 0 0; color: #64748b; font-size: 11px; }
</style>
