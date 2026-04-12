<template>
  <div class="policy-page">
    <BaseCard title="안전보건 방침 및 목표">
      <template #actions>
        <button class="secondary" @click="load">새로고침</button>
      </template>

      <div class="view-toggle" v-if="isSiteUi">
        <button class="secondary" :class="{ active: viewScope === 'SITE' }" @click="switchScope('SITE')">현장 방침/목표</button>
        <button class="secondary" :class="{ active: viewScope === 'HQ' }" @click="switchScope('HQ')">본사 방침/목표</button>
      </div>

      <div class="panel-grid">
        <section class="panel-card">
          <h3>방침</h3>
          <p class="title">{{ payload.policy?.title || "등록된 방침이 없습니다." }}</p>
          <p class="meta">{{ formatDateTime(payload.policy?.uploaded_at) }}</p>
          <div v-if="payload.policy?.file_url" class="file-actions">
            <button type="button" class="secondary" @click="openPolicyFile(payload.policy)">파일 보기</button>
            <button type="button" class="secondary" @click="downloadPolicyFile(payload.policy)">다운로드</button>
          </div>
          <div v-if="isHqUi" class="upload-box">
            <input v-model="hqPolicyTitle" type="text" placeholder="본사 방침 제목" />
            <input type="file" accept="image/*,.pdf" @change="onFileChange($event, 'policy')" />
            <button class="primary" :disabled="!hqPolicyFile || !hqPolicyTitle.trim() || uploading" @click="uploadHq('POLICY')">
              업로드
            </button>
          </div>
        </section>

        <section class="panel-card">
          <h3>목표</h3>
          <p class="title">{{ payload.target?.title || "등록된 목표가 없습니다." }}</p>
          <p class="meta">{{ formatDateTime(payload.target?.uploaded_at) }}</p>
          <div v-if="payload.target?.file_url" class="file-actions">
            <button type="button" class="secondary" @click="openPolicyFile(payload.target)">파일 보기</button>
            <button type="button" class="secondary" @click="downloadPolicyFile(payload.target)">다운로드</button>
          </div>
          <div v-if="isHqUi" class="upload-box">
            <input v-model="hqTargetTitle" type="text" placeholder="본사 목표 제목" />
            <input type="file" accept="image/*,.pdf" @change="onFileChange($event, 'target')" />
            <button class="primary" :disabled="!hqTargetFile || !hqTargetTitle.trim() || uploading" @click="uploadHq('TARGET')">
              업로드
            </button>
          </div>
        </section>
      </div>
      <p v-if="uploadMessage" class="upload-message">{{ uploadMessage }}</p>
    </BaseCard>

    <div v-if="preview.open" class="preview-backdrop" @click.self="closePreview">
      <div class="preview-card">
        <div class="preview-head">
          <strong>{{ preview.title }}</strong>
          <button type="button" class="secondary" @click="closePreview">닫기</button>
        </div>
        <iframe v-if="preview.kind === 'pdf'" class="preview-frame" :src="preview.url || ''" title="policy-goal-preview" />
        <img v-else-if="preview.kind === 'image'" class="preview-image" :src="preview.url || ''" alt="policy-goal-preview" />
        <p v-else class="preview-fallback">이 형식은 미리보기를 지원하지 않습니다. 다운로드로 확인해 주세요.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { BaseCard } from "@/components/product";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { canPreviewInBrowser, isImageFile, isPdfFile } from "@/utils/filePreview";

interface UploadedDoc {
  title: string;
  uploaded_at: string;
  file_url: string;
  file_name?: string | null;
}

const auth = useAuthStore();
const viewScope = ref<"SITE" | "HQ">("SITE");
const payload = ref<{ policy: UploadedDoc | null; target: UploadedDoc | null }>({ policy: null, target: null });
const hqPolicyTitle = ref("");
const hqTargetTitle = ref("");
const hqPolicyFile = ref<File | null>(null);
const hqTargetFile = ref<File | null>(null);
const uploading = ref(false);
const uploadMessage = ref("");
const preview = ref<{ open: boolean; title: string; url: string | null; kind: "pdf" | "image" | "other" }>({
  open: false,
  title: "",
  url: null,
  kind: "other",
});

const isSiteUi = computed(() => auth.user?.ui_type === "SITE");
const isHqUi = computed(() => auth.user?.ui_type === "HQ_SAFE");

function formatDateTime(value: string | null | undefined) {
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

function resolveFileUrl(path: string) {
  return `${api.defaults.baseURL}${path}`;
}

function revokePreviewUrl() {
  if (preview.value.url) {
    window.URL.revokeObjectURL(preview.value.url);
  }
  preview.value.url = null;
}

function closePreview() {
  revokePreviewUrl();
  preview.value.open = false;
  preview.value.title = "";
  preview.value.kind = "other";
}

async function fetchPolicyBlob(doc: UploadedDoc) {
  const path = doc.file_url;
  const previewable = canPreviewInBrowser(doc.file_name);
  const res = await api.get(path, {
    params: { disposition: previewable ? "inline" : "attachment" },
    responseType: "blob",
  });
  const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
  return new Blob([res.data], { type: contentType });
}

async function openPolicyFile(doc: UploadedDoc) {
  uploadMessage.value = "";
  try {
    const blob = await fetchPolicyBlob(doc);
    revokePreviewUrl();
    const url = window.URL.createObjectURL(blob);
    const fileName = doc.file_name || doc.title || "file";
    if (isPdfFile(fileName)) {
      preview.value = { open: true, title: doc.title || "방침/목표", url, kind: "pdf" };
      return;
    }
    if (isImageFile(fileName)) {
      preview.value = { open: true, title: doc.title || "방침/목표", url, kind: "image" };
      return;
    }
    if (canPreviewInBrowser(fileName)) {
      window.open(url, "_blank", "noopener");
      setTimeout(() => window.URL.revokeObjectURL(url), 5000);
      return;
    }
    window.URL.revokeObjectURL(url);
    preview.value = { open: true, title: doc.title || "방침/목표", url: null, kind: "other" };
  } catch {
    uploadMessage.value = "파일을 열 수 없습니다. 권한/네트워크를 확인해주세요.";
  }
}

async function downloadPolicyFile(doc: UploadedDoc) {
  uploadMessage.value = "";
  try {
    const blob = await fetchPolicyBlob(doc);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = doc.file_name || `${doc.title || "download"}.bin`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch {
    uploadMessage.value = "다운로드에 실패했습니다. 잠시 후 다시 시도해주세요.";
  }
}

function onFileChange(event: Event, key: "policy" | "target") {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  if (key === "policy") hqPolicyFile.value = file;
  else hqTargetFile.value = file;
}

function switchScope(scope: "SITE" | "HQ") {
  viewScope.value = scope;
  void load();
}

async function load() {
  uploadMessage.value = "";
  try {
    const params: Record<string, unknown> = { scope: viewScope.value };
    if (viewScope.value === "SITE" && auth.user?.site_id) {
      params.site_id = auth.user.site_id;
    }
    const res = await api.get("/safety-policy-goals/view", { params });
    payload.value = { policy: res.data.policy, target: res.data.target };
  } catch (error: unknown) {
    const statusCode = (error as { response?: { status?: number } })?.response?.status;
    if (statusCode === 404) {
      uploadMessage.value = "서버에 안전보건 방침/목표 API가 배포되지 않았습니다. 백엔드 최신 배포가 필요합니다.";
    } else {
      uploadMessage.value = "조회에 실패했습니다. 잠시 후 다시 시도해주세요.";
    }
    payload.value = { policy: null, target: null };
  }
}

async function uploadHq(kind: "POLICY" | "TARGET") {
  const file = kind === "POLICY" ? hqPolicyFile.value : hqTargetFile.value;
  const title = kind === "POLICY" ? hqPolicyTitle.value : hqTargetTitle.value;
  if (!file || !title.trim()) return;
  uploadMessage.value = "";
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("scope", "HQ");
    form.append("kind", kind);
    form.append("title", title.trim());
    form.append("file", file);
    await api.post("/safety-policy-goals/upload", form);
    if (kind === "POLICY") {
      hqPolicyFile.value = null;
      hqPolicyTitle.value = "";
    } else {
      hqTargetFile.value = null;
      hqTargetTitle.value = "";
    }
    viewScope.value = "HQ";
    await load();
    uploadMessage.value = "업로드가 완료되었습니다.";
  } catch (error: unknown) {
    const responseData = (error as { response?: { data?: { detail?: string } } })?.response?.data;
    uploadMessage.value = responseData?.detail || "업로드에 실패했습니다. 파일 크기(최대 10MB)와 형식을 확인해주세요.";
  } finally {
    uploading.value = false;
  }
}

onMounted(() => {
  viewScope.value = isSiteUi.value ? "SITE" : "HQ";
  void load();
});

onBeforeUnmount(() => {
  closePreview();
});
</script>

<style scoped>
.view-toggle { display: flex; gap: 8px; margin-bottom: 12px; }
.view-toggle .active { background: #0f172a; color: #fff; }
.panel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.panel-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.title { font-weight: 700; margin: 0; }
.meta { margin: 0; color: #64748b; font-size: 12px; }
.file-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.upload-box { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
.upload-message { margin-top: 12px; color: #b91c1c; font-weight: 600; }
.preview-backdrop { position: fixed; inset: 0; background: rgba(17, 24, 39, 0.45); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 16px; }
.preview-card { width: min(960px, calc(100vw - 32px)); height: min(720px, calc(100vh - 64px)); background: #fff; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25); }
.preview-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.preview-frame { flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; width: 100%; min-height: 0; }
.preview-image { flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; width: 100%; object-fit: contain; min-height: 0; background: #f8fafc; }
.preview-fallback { margin: 0; color: #64748b; font-size: 13px; }
@media (max-width: 920px) { .panel-grid { grid-template-columns: 1fr; } }
</style>
