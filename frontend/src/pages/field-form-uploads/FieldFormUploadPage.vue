<template>
  <section class="field-form-page">
    <aside v-if="!isHqView && rightRankItems.length > 0" class="rank-rail rank-rail-right" aria-label="제출 현장 순위">
      <h3>제출 현장</h3>
      <ol>
        <li v-for="item in rightRankItems" :key="`right-${item.rank}`">
          <span class="rank-no">{{ item.rank }}위</span>
          <span class="rank-site">{{ item.site_name }}</span>
        </li>
      </ol>
    </aside>
    <aside v-if="!isHqView && leftRankItems.length > 0" class="rank-rail rank-rail-left" aria-label="제출 현장 순위 추가 목록">
      <h3>제출 현장</h3>
      <ol>
        <li v-for="item in leftRankItems" :key="`left-${item.rank}`">
          <span class="rank-no">{{ item.rank }}위</span>
          <span class="rank-site">{{ item.site_name }}</span>
        </li>
      </ol>
    </aside>
    <div class="page-heading">
      <p class="deadline">업로드 기한: 2026년 7월 13일까지</p>
      <h2>현장 양식 업로드</h2>
    </div>

    <template v-if="isHqView">
      <div class="hq-panel">
        <div class="hq-panel-header">
          <h3>현장 업로드 파일</h3>
          <button type="button" class="secondary" :disabled="loading" @click="loadUploads">새로고침</button>
        </div>
        <div v-if="loading" class="empty-state">목록을 불러오는 중입니다.</div>
        <div v-else-if="uploads.length === 0" class="empty-state">아직 업로드된 파일이 없습니다.</div>
        <div v-else class="upload-table-wrap">
          <table class="upload-table">
            <thead>
              <tr>
                <th>현장명</th>
                <th>파일명</th>
                <th>문서수</th>
                <th>업로드</th>
                <th>다운로드</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in uploads" :key="item.id">
                <td>{{ item.site_name || "-" }}</td>
                <td>{{ item.stored_filename }}</td>
                <td>{{ item.document_count }}개</td>
                <td>{{ formatDate(item.uploaded_at) }}</td>
                <td>
                  <button type="button" class="download-btn" @click="downloadUpload(item)">다운로드</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="upload-stage">
        <div class="zip-animation" aria-hidden="true">
          <span class="doc doc-a"></span>
          <span class="doc doc-b"></span>
          <span class="doc doc-c"></span>
          <span class="doc doc-d"></span>
          <span class="zip-box">ZIP</span>
        </div>

        <label
          class="drop-zone"
          :class="{ 'drop-zone-active': isDragging, 'drop-zone-disabled': !uploadOpen || uploading }"
          @dragenter.prevent="handleDragEnter"
          @dragover.prevent="handleDragEnter"
          @dragleave.prevent="handleDragLeave"
          @drop.prevent="handleDrop"
        >
          <input type="file" accept=".zip,application/zip" :disabled="!uploadOpen || uploading" @change="handleFileInput" />
          <strong>드래그 앤 드롭</strong>
          <span>또는 파일 선택 버튼으로 zip 파일을 업로드하세요.</span>
          <span class="upload-policy">현장별 최대 2개, 파일당 20MB 이하만 업로드 가능합니다.</span>
          <span class="select-file-btn" aria-hidden="true">{{ uploading ? "업로드 중" : "파일 선택" }}</span>
          <p v-if="!uploadOpen" class="deadline-ended">현장 양식 업로드 기한이 종료되었습니다.</p>
          <p v-if="message" class="upload-message">{{ message }}</p>
          <p v-if="warning" class="upload-warning">{{ warning }}</p>
        </label>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";

interface FieldFormUpload {
  id: number;
  site_name: string;
  stored_filename: string;
  document_count: number;
  uploaded_at: string;
  download_url: string;
}

const ZIP_ONLY_MESSAGE = "압축하여 업로드 바랍니다. zip 확장자만 업로드 가능합니다.";
const MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024;
const UPLOAD_SIZE_MESSAGE = "파일 크기는 20MB 이하만 업로드할 수 있습니다.";

const auth = useAuthStore();
const uploads = ref<FieldFormUpload[]>([]);
const submittedSites = ref<Array<{ rank: number; site_name: string }>>([]);
const loading = ref(false);
const uploading = ref(false);
const isDragging = ref(false);
const message = ref("");
const warning = ref("");
const uploadOpen = ref(true);
const isHqView = computed(() => auth.user?.ui_type === "HQ_SAFE" || auth.user?.ui_type === "HQ_OTHER");
const rightRankItems = computed(() => submittedSites.value.slice(0, 31));
const leftRankItems = computed(() => submittedSites.value.slice(31, 62));

onMounted(() => {
  void loadSubmittedSites();
  if (isHqView.value) {
    void loadUploads();
  } else {
    void loadDeadline();
  }
});

async function loadDeadline() {
  try {
    const res = await api.get("/field-form-uploads/deadline", { skipAuthRedirect: true });
    uploadOpen.value = res.data?.upload_open !== false;
  } catch {
    uploadOpen.value = true;
  }
}

async function loadSubmittedSites() {
  try {
    const res = await api.get("/field-form-uploads/submitted-sites", { skipAuthRedirect: true });
    submittedSites.value = Array.isArray(res.data?.items) ? res.data.items : [];
  } catch {
    submittedSites.value = [];
  }
}

async function loadUploads() {
  loading.value = true;
  try {
    const res = await api.get("/field-form-uploads");
    uploads.value = Array.isArray(res.data?.items) ? res.data.items : [];
  } catch {
    uploads.value = [];
  } finally {
    loading.value = false;
  }
}

function handleDragEnter() {
  if (!uploadOpen.value || uploading.value) return;
  isDragging.value = true;
}

function handleDragLeave() {
  isDragging.value = false;
}

function handleDrop(event: DragEvent) {
  isDragging.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) void uploadFile(file);
}

function handleFileInput(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) void uploadFile(file);
  input.value = "";
}

async function uploadFile(file: File) {
  message.value = "";
  warning.value = "";
  if (!file.name.toLowerCase().endsWith(".zip")) {
    warning.value = ZIP_ONLY_MESSAGE;
    return;
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    warning.value = UPLOAD_SIZE_MESSAGE;
    return;
  }
  const form = new FormData();
  form.append("file", file);
  uploading.value = true;
  try {
    const res = await api.post("/field-form-uploads", form, {
      headers: { "Content-Type": "multipart/form-data" },
      skipAuthRedirect: true,
      timeout: 60_000,
    });
    const storedFilename = res.data?.stored_filename || file.name;
    message.value = `${storedFilename} 파일이 업로드 되었습니다.`;
    await loadSubmittedSites();
  } catch (err: any) {
    warning.value = err?.response?.data?.detail || ZIP_ONLY_MESSAGE;
  } finally {
    uploading.value = false;
  }
}

function formatDate(value: string) {
  if (!value) return "-";
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

async function downloadUpload(item: FieldFormUpload) {
  const res = await api.get(item.download_url, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = item.stored_filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
</script>

<style scoped>
.field-form-page {
  position: relative;
  min-height: calc(100vh - 120px);
  color: #0f172a;
}

.rank-rail {
  position: fixed;
  top: 88px;
  z-index: 4;
  width: 220px;
  max-height: calc(100vh - 112px);
  overflow: auto;
  padding: 12px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: rgba(255, 247, 237, 0.96);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
}

.rank-rail-right {
  right: 16px;
}

.rank-rail-left {
  left: 256px;
}

.rank-rail h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #9a3412;
}

.rank-rail ol {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.rank-rail li {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  min-height: 26px;
  padding: 4px 6px;
  border-radius: 6px;
  background: #ffffff;
  font-size: 12px;
  line-height: 1.25;
}

.rank-no {
  color: #ea580c;
  font-weight: 800;
}

.rank-site {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
}

.page-heading {
  text-align: center;
  margin-bottom: 22px;
}

.deadline {
  margin: 0 0 6px;
  color: #b45309;
  font-weight: 700;
}

.page-heading h2 {
  margin: 0;
  font-size: 28px;
}

.upload-stage {
  display: grid;
  place-items: center;
  padding: 24px 0;
}

.zip-animation {
  position: relative;
  width: 220px;
  height: 110px;
  margin-bottom: 18px;
}

.doc {
  position: absolute;
  width: 34px;
  height: 44px;
  border-radius: 5px;
  background: #ffffff;
  border: 2px solid #bfdbfe;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.14);
  animation: gather-docs 2.4s ease-in-out infinite;
}

.doc::after {
  content: "";
  position: absolute;
  left: 7px;
  right: 7px;
  top: 12px;
  height: 2px;
  background: #60a5fa;
  box-shadow: 0 8px 0 #93c5fd, 0 16px 0 #bfdbfe;
}

.doc-a { left: 6px; top: 10px; animation-delay: 0s; }
.doc-b { left: 48px; top: 52px; animation-delay: 0.2s; }
.doc-c { right: 48px; top: 8px; animation-delay: 0.35s; }
.doc-d { right: 8px; top: 50px; animation-delay: 0.5s; }

.zip-box {
  position: absolute;
  left: 80px;
  top: 30px;
  display: grid;
  place-items: center;
  width: 62px;
  height: 58px;
  border-radius: 8px;
  background: #f59e0b;
  color: #111827;
  font-weight: 900;
  box-shadow: 0 0 0 4px #fde68a inset, 0 16px 34px rgba(245, 158, 11, 0.28);
  animation: zip-pulse 1.2s ease-in-out infinite;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: min(520px, 100%);
  min-height: 280px;
  padding: 28px;
  border: 2px dashed #2563eb;
  border-radius: 8px;
  background: #ffffff;
  text-align: center;
  box-shadow: 0 16px 45px rgba(15, 23, 42, 0.08);
  cursor: pointer;
}

.drop-zone input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.drop-zone strong {
  font-size: 24px;
  margin-bottom: 8px;
}

.drop-zone span {
  color: #475569;
}

.drop-zone .upload-policy {
  margin-top: 6px;
  color: #b45309;
  font-size: 13px;
  font-weight: 700;
}

.drop-zone-active {
  background: #eff6ff;
  border-color: #1d4ed8;
}

.drop-zone-disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.select-file-btn,
.download-btn {
  margin-top: 18px;
  border: 0;
  border-radius: 8px;
  background: #2563eb;
  color: #ffffff;
  font-weight: 700;
  padding: 10px 16px;
}

.drop-zone .select-file-btn {
  color: #ffffff;
}

.download-btn {
  margin-top: 0;
  padding: 8px 12px;
  cursor: pointer;
}

.upload-message,
.upload-warning,
.deadline-ended {
  width: 100%;
  margin: 18px 0 0;
  padding: 12px;
  border-radius: 8px;
  font-weight: 700;
}

.upload-message {
  background: #ecfdf5;
  color: #047857;
}

.upload-warning,
.deadline-ended {
  background: #fef2f2;
  color: #b91c1c;
}

.hq-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.hq-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid #e2e8f0;
}

.hq-panel-header h3 {
  margin: 0;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: #64748b;
}

.upload-table-wrap {
  overflow-x: auto;
}

.upload-table {
  width: 100%;
  border-collapse: collapse;
}

.upload-table th,
.upload-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  white-space: nowrap;
}

.upload-table th {
  background: #f8fafc;
  color: #334155;
}

@keyframes gather-docs {
  0%, 100% {
    opacity: 0.35;
    transform: translate(0, 0) scale(0.9) rotate(-8deg);
  }
  45%, 65% {
    opacity: 1;
    transform: translate(76px, 16px) scale(0.55) rotate(4deg);
  }
}

@keyframes zip-pulse {
  0%, 100% { transform: scale(1); filter: brightness(1); }
  50% { transform: scale(1.08); filter: brightness(1.1); }
}

@media (max-width: 768px) {
  .page-heading h2 {
    font-size: 24px;
  }

  .drop-zone {
    min-height: 240px;
  }
}

@media (max-width: 1279px) {
  .rank-rail {
    position: static;
    width: auto;
    max-height: none;
    margin: 0 auto 14px;
  }

  .rank-rail-left {
    margin-top: -6px;
  }
}
</style>
