<template>
  <section class="important-files-page">
    <header class="page-header">
      <div>
        <h1>중요파일</h1>
        <p>Safety Workbench에서 직접 선택해 올린 파일만 표시됩니다.</p>
      </div>
      <button type="button" class="refresh-button" :disabled="loading" @click="loadFiles">
        {{ loading ? "불러오는 중" : "새로고침" }}
      </button>
    </header>

    <div class="read-only-notice">
      이 화면은 읽기 전용입니다. 중요파일 지정과 보관 해제는 Safety Workbench에서만 할 수 있습니다.
    </div>

    <p v-if="message" class="state-message" role="status">{{ message }}</p>

    <template v-else>
      <div v-if="!isMobileViewport" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>파일명</th>
              <th>폴더</th>
              <th>구분</th>
              <th>크기</th>
              <th>등록일</th>
              <th><span class="sr-only">열기</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.important_file_id">
              <td class="file-name"><span class="important-dot" aria-hidden="true" />{{ item.file_name }}</td>
              <td class="path-cell" :title="item.relative_path">{{ folderOf(item.relative_path) }}</td>
              <td>{{ scopeLabel(item.scope) }}</td>
              <td>{{ formatBytes(item.content_size) }}</td>
              <td>{{ formatDate(item.created_at) }}</td>
              <td>
                <button type="button" class="open-button" @click="download(item)">열기</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <ul v-else class="mobile-list">
        <li v-for="item in items" :key="item.important_file_id" class="mobile-card">
          <div class="mobile-card-title">
            <span class="important-dot" aria-hidden="true" />
            <strong>{{ item.file_name }}</strong>
          </div>
          <p>{{ folderOf(item.relative_path) }}</p>
          <div class="mobile-card-meta">
            <span>{{ scopeLabel(item.scope) }}</span>
            <span>{{ formatBytes(item.content_size) }}</span>
            <span>{{ formatDate(item.created_at) }}</span>
          </div>
          <button type="button" class="open-button mobile-open" @click="download(item)">파일 열기</button>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { useMobileViewport } from "@/composables/useMobileViewport";

interface ImportantFileItem {
  important_file_id: string;
  scope: "PERSONAL" | "TEAM_SAFETY_NAS";
  relative_path: string;
  file_name: string;
  extension: string;
  content_size: number;
  created_at: string;
  content_path: string;
  is_important: boolean;
  mobile_view_available: boolean;
}

const { isMobileViewport } = useMobileViewport();
const items = ref<ImportantFileItem[]>([]);
const loading = ref(false);
const error = ref("");
const message = computed(() => {
  if (loading.value) return "중요파일 목록을 불러오고 있습니다.";
  if (error.value) return error.value;
  if (!items.value.length) return "현재 모바일에서 열 수 있는 중요파일이 없습니다.";
  return "";
});

function currentSurface(): "PC" | "MOBILE" {
  return isMobileViewport.value ? "MOBILE" : "PC";
}

async function loadFiles() {
  loading.value = true;
  error.value = "";
  try {
    const capability = await api.get("/file-access/v1/important-files/capabilities", {
      params: { surface: currentSurface() },
    });
    if (capability.data?.can_read !== true) {
      items.value = [];
      error.value = "중요파일 열람 권한이 없습니다.";
      return;
    }
    const response = await api.get("/file-access/v1/important-files", {
      params: { surface: currentSurface(), limit: 500 },
    });
    const rows = Array.isArray(response.data?.items) ? response.data.items : [];
    items.value = rows.filter(
      (row: ImportantFileItem) =>
        row?.is_important === true &&
        row?.mobile_view_available === true &&
        /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(
          row?.important_file_id || "",
        ),
    );
  } catch (requestError: any) {
    items.value = [];
    error.value =
      requestError?.response?.status === 404
        ? "중요파일 모바일 열람 기능은 아직 활성화되지 않았습니다."
        : requestError?.response?.status === 403
          ? "중요파일 열람 권한이 없습니다."
          : "중요파일 목록을 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

async function download(item: ImportantFileItem) {
  if (!item.mobile_view_available) return;
  try {
    const response = await api.get(item.content_path, { responseType: "blob" });
    const objectUrl = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.rel = "noopener";
    if ([".pdf", ".png", ".jpg", ".jpeg", ".webp"].includes(item.extension)) {
      anchor.target = "_blank";
    } else {
      anchor.download = item.file_name;
    }
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch {
    error.value = "파일을 열지 못했습니다. 목록을 새로고침한 뒤 다시 시도해 주세요.";
  }
}

function folderOf(relativePath: string): string {
  const normalized = relativePath.replace(/\\/g, "/");
  const index = normalized.lastIndexOf("/");
  return index > 0 ? normalized.slice(0, index) : "최상위 폴더";
}

function scopeLabel(scope: ImportantFileItem["scope"]): string {
  return scope === "TEAM_SAFETY_NAS" ? "안전보건실 공용" : "개인 폴더";
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "-" : parsed.toLocaleString("ko-KR");
}

onMounted(loadFiles);
</script>

<style scoped>
.important-files-page {
  max-width: 1200px;
  margin: 0 auto;
  color: #172033;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

h1 {
  margin: 0;
  font-size: 26px;
}

.page-header p {
  margin: 7px 0 0;
  color: #64748b;
}

.read-only-notice {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: 14px;
}

.refresh-button,
.open-button {
  min-height: 38px;
  border: 1px solid #2563eb;
  border-radius: 7px;
  background: #fff;
  color: #1d4ed8;
  font-weight: 700;
  cursor: pointer;
}

.refresh-button {
  padding: 0 14px;
}

.refresh-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #dbe2ea;
  border-radius: 9px;
  background: #fff;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 12px 14px;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
  font-size: 13px;
}

th {
  background: #f8fafc;
  color: #475569;
  font-weight: 700;
}

tbody tr:last-child td {
  border-bottom: 0;
}

.file-name {
  min-width: 230px;
  color: #1d4ed8;
  font-weight: 700;
}

.important-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 8px;
  border-radius: 50%;
  background: #2563eb;
}

.path-cell {
  max-width: 380px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.open-button {
  padding: 0 13px;
}

.state-message {
  margin: 0;
  padding: 28px 18px;
  border: 1px solid #dbe2ea;
  border-radius: 9px;
  background: #fff;
  color: #475569;
  text-align: center;
}

.mobile-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.mobile-card {
  padding: 15px;
  border: 1px solid #bfdbfe;
  border-left: 5px solid #2563eb;
  border-radius: 9px;
  background: #fff;
}

.mobile-card-title {
  display: flex;
  align-items: center;
  word-break: break-all;
}

.mobile-card p {
  margin: 10px 0;
  color: #64748b;
  font-size: 13px;
  word-break: break-all;
}

.mobile-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: #475569;
  font-size: 12px;
}

.mobile-open {
  width: 100%;
  margin-top: 14px;
  min-height: 44px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 768px) {
  .page-header {
    align-items: center;
  }

  h1 {
    font-size: 21px;
  }

  .page-header p {
    font-size: 13px;
  }
}
</style>
