<template>
  <div class="policy-page">
    <BaseCard :title="pageTitle">
      <template #actions>
        <button type="button" class="secondary" @click="refresh">새로고침</button>
      </template>

      <p v-if="isSiteUi" class="scope-note">
        기본 화면은 <strong>현장</strong>에 등록된 방침(왼쪽)과 목표(오른쪽)입니다. 아래에서 제목·파일을 올려 등록할 수 있습니다. PDF·PNG·JPEG·WEBP 등 브라우저에서 볼 수 있는 형식을 권장합니다.
      </p>

      <div v-if="isSiteUi" class="hq-access-row">
        <button type="button" class="hq-modal-trigger" @click="openHqModal">본사 방침·목표 보기</button>
      </div>

      <div v-if="isHqUi" class="view-toggle">
        <button type="button" class="secondary" :class="{ active: viewScope === 'HQ' }" @click="switchScope('HQ')">본사 방침/목표</button>
        <button
          v-if="hqCanViewSiteScope"
          type="button"
          class="secondary"
          :class="{ active: viewScope === 'SITE' }"
          @click="switchScope('SITE')"
        >
          현장 방침/목표
        </button>
      </div>

      <div v-if="mainPreviewLoading" class="loading-bar">미리보기를 불러오는 중…</div>

      <div class="panel-grid">
        <section class="panel-card">
          <h3>방침</h3>
          <p class="title">{{ payload.policy?.title || "등록된 방침이 없습니다." }}</p>
          <p class="meta">{{ formatDateTime(payload.policy?.uploaded_at) }}</p>
          <div v-if="payload.policy?.file_url" class="file-actions">
            <button type="button" class="secondary" @click="downloadPolicyFile(payload.policy)">다운로드</button>
            <button type="button" class="secondary" @click="openPolicyFile(payload.policy)">새 창에서 보기</button>
          </div>
          <div class="preview-pane">
            <iframe
              v-if="mainPolicyPreview?.kind === 'pdf'"
              class="preview-frame"
              :src="mainPolicyPreview.url"
              title="방침 미리보기"
            />
            <img
              v-else-if="mainPolicyPreview?.kind === 'image'"
              class="preview-image"
              :src="mainPolicyPreview.url"
              alt="방침 미리보기"
            />
            <p v-else-if="payload.policy?.file_url && mainPolicyPreview?.kind === 'other'" class="preview-fallback">
              이 파일 형식은 여기서 미리보기할 수 없습니다. 위에서 다운로드하거나 새 창에서 여세요.
            </p>
            <p v-else-if="payload.policy?.file_url && !mainPreviewLoading && !mainPolicyPreview" class="preview-fallback">
              미리보기를 불러오지 못했습니다. 네트워크·권한을 확인해 주세요.
            </p>
            <p v-else-if="!payload.policy?.file_url" class="preview-empty">등록된 파일이 없습니다.</p>
          </div>
          <div v-if="isSiteUi" class="upload-box">
            <span class="upload-label">현장 방침 등록·갱신</span>
            <input v-model="sitePolicyTitle" type="text" placeholder="현장 방침 제목" />
            <input type="file" accept="image/*,.pdf,application/pdf" @change="onSiteFileChange($event, 'policy')" />
            <button
              class="primary"
              type="button"
              :disabled="!sitePolicyFile || !sitePolicyTitle.trim() || uploading || !siteId"
              @click="uploadSite('POLICY')"
            >
              {{ uploading ? "처리 중…" : "현장 방침 업로드" }}
            </button>
          </div>
          <div v-if="isHqUi" class="upload-box">
            <input v-model="hqPolicyTitle" type="text" placeholder="본사 방침 제목" />
            <input type="file" accept="image/*,.pdf,application/pdf" @change="onFileChange($event, 'policy')" />
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
            <button type="button" class="secondary" @click="downloadPolicyFile(payload.target)">다운로드</button>
            <button type="button" class="secondary" @click="openPolicyFile(payload.target)">새 창에서 보기</button>
          </div>
          <div class="preview-pane">
            <iframe
              v-if="mainTargetPreview?.kind === 'pdf'"
              class="preview-frame"
              :src="mainTargetPreview.url"
              title="목표 미리보기"
            />
            <img
              v-else-if="mainTargetPreview?.kind === 'image'"
              class="preview-image"
              :src="mainTargetPreview.url"
              alt="목표 미리보기"
            />
            <p v-else-if="payload.target?.file_url && mainTargetPreview?.kind === 'other'" class="preview-fallback">
              이 파일 형식은 여기서 미리보기할 수 없습니다. 위에서 다운로드하거나 새 창에서 여세요.
            </p>
            <p v-else-if="payload.target?.file_url && !mainPreviewLoading && !mainTargetPreview" class="preview-fallback">
              미리보기를 불러오지 못했습니다. 네트워크·권한을 확인해 주세요.
            </p>
            <p v-else-if="!payload.target?.file_url" class="preview-empty">등록된 파일이 없습니다.</p>
          </div>
          <div v-if="isSiteUi" class="upload-box">
            <span class="upload-label">현장 목표 등록·갱신</span>
            <input v-model="siteTargetTitle" type="text" placeholder="현장 목표 제목" />
            <input type="file" accept="image/*,.pdf,application/pdf" @change="onSiteFileChange($event, 'target')" />
            <button
              class="primary"
              type="button"
              :disabled="!siteTargetFile || !siteTargetTitle.trim() || uploading || !siteId"
              @click="uploadSite('TARGET')"
            >
              {{ uploading ? "처리 중…" : "현장 목표 업로드" }}
            </button>
          </div>
          <div v-if="isHqUi" class="upload-box">
            <input v-model="hqTargetTitle" type="text" placeholder="본사 목표 제목" />
            <input type="file" accept="image/*,.pdf,application/pdf" @change="onFileChange($event, 'target')" />
            <button class="primary" :disabled="!hqTargetFile || !hqTargetTitle.trim() || uploading" @click="uploadHq('TARGET')">
              업로드
            </button>
          </div>
        </section>
      </div>
      <p v-if="uploadMessage" class="upload-message">{{ uploadMessage }}</p>
    </BaseCard>

    <div v-if="hqModalOpen" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="hq-modal-title" @click.self="closeHqModal">
      <div class="hq-modal card-like">
        <div class="hq-modal-head">
          <h2 id="hq-modal-title" class="hq-modal-title">본사 안전보건 방침 및 목표</h2>
          <button type="button" class="secondary" @click="closeHqModal">닫기</button>
        </div>
        <p v-if="hqModalLoading" class="loading-bar">불러오는 중…</p>
        <div class="panel-grid modal-grid">
          <section class="panel-card flat">
            <h3>방침</h3>
            <p class="title">{{ hqPayload.policy?.title || "등록된 본사 방침이 없습니다." }}</p>
            <p class="meta">{{ formatDateTime(hqPayload.policy?.uploaded_at) }}</p>
            <div v-if="hqPayload.policy?.file_url" class="file-actions">
              <button type="button" class="secondary" @click="downloadPolicyFile(hqPayload.policy)">다운로드</button>
            </div>
            <div class="preview-pane preview-pane--modal">
              <iframe
                v-if="hqPolicyPreview?.kind === 'pdf'"
                class="preview-frame"
                :src="hqPolicyPreview.url"
                title="본사 방침"
              />
              <img
                v-else-if="hqPolicyPreview?.kind === 'image'"
                class="preview-image"
                :src="hqPolicyPreview.url"
                alt="본사 방침"
              />
              <p v-else-if="hqPayload.policy?.file_url && hqPolicyPreview?.kind === 'other'" class="preview-fallback">
                미리보기 불가 형식입니다. 다운로드 해 주세요.
              </p>
              <p v-else-if="!hqPayload.policy?.file_url" class="preview-empty">파일 없음</p>
            </div>
          </section>
          <section class="panel-card flat">
            <h3>목표</h3>
            <p class="title">{{ hqPayload.target?.title || "등록된 본사 목표가 없습니다." }}</p>
            <p class="meta">{{ formatDateTime(hqPayload.target?.uploaded_at) }}</p>
            <div v-if="hqPayload.target?.file_url" class="file-actions">
              <button type="button" class="secondary" @click="downloadPolicyFile(hqPayload.target)">다운로드</button>
            </div>
            <div class="preview-pane preview-pane--modal">
              <iframe
                v-if="hqTargetPreview?.kind === 'pdf'"
                class="preview-frame"
                :src="hqTargetPreview.url"
                title="본사 목표"
              />
              <img
                v-else-if="hqTargetPreview?.kind === 'image'"
                class="preview-image"
                :src="hqTargetPreview.url"
                alt="본사 목표"
              />
              <p v-else-if="hqPayload.target?.file_url && hqTargetPreview?.kind === 'other'" class="preview-fallback">
                미리보기 불가 형식입니다. 다운로드 해 주세요.
              </p>
              <p v-else-if="!hqPayload.target?.file_url" class="preview-empty">파일 없음</p>
            </div>
          </section>
        </div>
      </div>
    </div>

    <div v-if="preview.open" class="preview-backdrop" @click.self="closePreview">
      <div class="preview-card">
        <div class="preview-head">
          <strong>{{ preview.title }}</strong>
          <button type="button" class="secondary" @click="closePreview">닫기</button>
        </div>
        <iframe v-if="preview.kind === 'pdf'" class="preview-frame-legacy" :src="preview.url || ''" title="policy-goal-preview" />
        <img v-else-if="preview.kind === 'image'" class="preview-image-legacy" :src="preview.url || ''" alt="policy-goal-preview" />
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
import { formatDateTimeKst } from "@/utils/datetime";

interface UploadedDoc {
  title: string;
  uploaded_at: string;
  file_url: string;
  file_name?: string | null;
}

type BlobPreview = { url: string; kind: "pdf" | "image" | "other" } | null;

const auth = useAuthStore();
const viewScope = ref<"SITE" | "HQ">("SITE");
const payload = ref<{ policy: UploadedDoc | null; target: UploadedDoc | null }>({ policy: null, target: null });
const hqPayload = ref<{ policy: UploadedDoc | null; target: UploadedDoc | null }>({ policy: null, target: null });

const mainPolicyPreview = ref<BlobPreview>(null);
const mainTargetPreview = ref<BlobPreview>(null);
const hqPolicyPreview = ref<BlobPreview>(null);
const hqTargetPreview = ref<BlobPreview>(null);

const mainPreviewLoading = ref(false);
const hqModalOpen = ref(false);
const hqModalLoading = ref(false);

const hqPolicyTitle = ref("");
const hqTargetTitle = ref("");
const hqPolicyFile = ref<File | null>(null);
const hqTargetFile = ref<File | null>(null);
const sitePolicyTitle = ref("");
const siteTargetTitle = ref("");
const sitePolicyFile = ref<File | null>(null);
const siteTargetFile = ref<File | null>(null);
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

const siteId = computed(() => auth.effectiveSiteId ?? auth.user?.site_id ?? null);

const pageTitle = computed(() => (isSiteUi.value ? "안전보건 방침 및 목표 (현장)" : "안전보건 방침 및 목표"));

const hqCanViewSiteScope = computed(() => isHqUi.value && siteId.value != null);

function formatDateTime(value: string | null | undefined) {
  return formatDateTimeKst(value, "-");
}

function classifyKind(fileName: string | null | undefined, contentType: string | undefined): "pdf" | "image" | "other" {
  if (isPdfFile(fileName)) return "pdf";
  if (isImageFile(fileName)) return "image";
  const ct = (contentType || "").toLowerCase();
  if (ct.includes("pdf")) return "pdf";
  if (ct.startsWith("image/")) return "image";
  return "other";
}

function revokeBlobPreview(p: BlobPreview) {
  if (p?.url && (p.kind === "pdf" || p.kind === "image")) {
    try {
      window.URL.revokeObjectURL(p.url);
    } catch {
      /* noop */
    }
  }
}

async function fetchBlobPreview(doc: UploadedDoc | null): Promise<BlobPreview> {
  if (!doc?.file_url) return null;
  try {
    const res = await api.get(doc.file_url, { responseType: "blob" });
    const blob = res.data as Blob;
    const ct = (res.headers["content-type"] as string | undefined) || blob.type;
    const kind = classifyKind(doc.file_name, ct);
    if (kind === "other") {
      return { url: "", kind: "other" };
    }
    const url = window.URL.createObjectURL(blob);
    return { url, kind };
  } catch {
    return null;
  }
}

async function hydrateMainPreviews() {
  revokeBlobPreview(mainPolicyPreview.value);
  revokeBlobPreview(mainTargetPreview.value);
  mainPolicyPreview.value = null;
  mainTargetPreview.value = null;
  mainPreviewLoading.value = true;
  try {
    const [p, t] = await Promise.all([fetchBlobPreview(payload.value.policy), fetchBlobPreview(payload.value.target)]);
    mainPolicyPreview.value = p;
    mainTargetPreview.value = t;
  } finally {
    mainPreviewLoading.value = false;
  }
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

function onSiteFileChange(event: Event, key: "policy" | "target") {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  if (key === "policy") sitePolicyFile.value = file;
  else siteTargetFile.value = file;
}

function switchScope(scope: "SITE" | "HQ") {
  if (scope === "SITE" && !hqCanViewSiteScope.value) return;
  viewScope.value = scope;
  void load();
}

async function load() {
  uploadMessage.value = "";
  try {
    const params: Record<string, unknown> = {};
    if (isSiteUi.value) {
      params.scope = "SITE";
      if (!siteId.value) {
        uploadMessage.value = "현장 정보가 없어 조회할 수 없습니다.";
        payload.value = { policy: null, target: null };
        await hydrateMainPreviews();
        return;
      }
      params.site_id = siteId.value;
    } else {
      params.scope = viewScope.value;
      if (viewScope.value === "SITE") {
        if (!siteId.value) {
          uploadMessage.value = "현장 방침/목표를 보려면 계정에 현장이 연결되어 있어야 합니다.";
          payload.value = { policy: null, target: null };
          await hydrateMainPreviews();
          return;
        }
        params.site_id = siteId.value;
      }
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
  await hydrateMainPreviews();
}

async function refresh() {
  await load();
  if (hqModalOpen.value) {
    await loadHqModalContent();
  }
}

async function openHqModal() {
  hqModalOpen.value = true;
  await loadHqModalContent();
}

async function loadHqModalContent() {
  revokeBlobPreview(hqPolicyPreview.value);
  revokeBlobPreview(hqTargetPreview.value);
  hqPolicyPreview.value = null;
  hqTargetPreview.value = null;
  hqModalLoading.value = true;
  uploadMessage.value = "";
  try {
    const res = await api.get("/safety-policy-goals/view", { params: { scope: "HQ" } });
    hqPayload.value = { policy: res.data.policy, target: res.data.target };
    const [p, t] = await Promise.all([fetchBlobPreview(res.data.policy), fetchBlobPreview(res.data.target)]);
    hqPolicyPreview.value = p;
    hqTargetPreview.value = t;
  } catch {
    hqPayload.value = { policy: null, target: null };
    uploadMessage.value = "본사 방침·목표를 불러오지 못했습니다.";
  } finally {
    hqModalLoading.value = false;
  }
}

function closeHqModal() {
  hqModalOpen.value = false;
  revokeBlobPreview(hqPolicyPreview.value);
  revokeBlobPreview(hqTargetPreview.value);
  hqPolicyPreview.value = null;
  hqTargetPreview.value = null;
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

async function uploadSite(kind: "POLICY" | "TARGET") {
  const file = kind === "POLICY" ? sitePolicyFile.value : siteTargetFile.value;
  const title = kind === "POLICY" ? sitePolicyTitle.value : siteTargetTitle.value;
  if (!file || !title.trim() || !siteId.value) return;
  uploadMessage.value = "";
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("scope", "SITE");
    form.append("kind", kind);
    form.append("title", title.trim());
    form.append("site_id", String(siteId.value));
    form.append("file", file);
    await api.post("/safety-policy-goals/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    if (kind === "POLICY") {
      sitePolicyFile.value = null;
      sitePolicyTitle.value = "";
    } else {
      siteTargetFile.value = null;
      siteTargetTitle.value = "";
    }
    await load();
    uploadMessage.value = "현장 자료가 등록되었습니다.";
  } catch (error: unknown) {
    const responseData = (error as { response?: { data?: { detail?: string } } })?.response?.data;
    uploadMessage.value = responseData?.detail || "업로드에 실패했습니다. 권한·파일 크기(최대 10MB)를 확인해주세요.";
  } finally {
    uploading.value = false;
  }
}

onMounted(() => {
  if (isSiteUi.value) {
    viewScope.value = "SITE";
  } else {
    viewScope.value = "HQ";
  }
  void load();
});

onBeforeUnmount(() => {
  closePreview();
  revokeBlobPreview(mainPolicyPreview.value);
  revokeBlobPreview(mainTargetPreview.value);
  revokeBlobPreview(hqPolicyPreview.value);
  revokeBlobPreview(hqTargetPreview.value);
});
</script>

<style scoped>
.scope-note {
  margin: 0 0 12px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.hq-access-row {
  margin-bottom: 14px;
}

.hq-modal-trigger {
  background: #fff;
  color: #1d4ed8;
  border: 2px solid #2563eb;
  border-radius: 8px;
  padding: 10px 16px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
}
.hq-modal-trigger:hover {
  background: #eff6ff;
}

.view-toggle {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.view-toggle .active {
  background: #0f172a;
  color: #fff;
}

.loading-bar {
  margin-bottom: 10px;
  font-size: 13px;
  color: #64748b;
}

.panel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: stretch;
}

.panel-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.panel-card.flat {
  border-style: dashed;
}

.panel-card h3 {
  margin: 0;
  font-size: 14px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.title {
  font-weight: 700;
  margin: 0;
}

.meta {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}

.file-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-pane {
  flex: 1;
  min-height: 52vh;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f1f5f9;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.preview-pane--modal {
  min-height: 38vh;
}

.preview-frame {
  width: 100%;
  flex: 1;
  min-height: 480px;
  border: 0;
  background: #fff;
}

.preview-image {
  width: 100%;
  flex: 1;
  min-height: 280px;
  object-fit: contain;
  display: block;
  background: #fff;
}

.preview-fallback,
.preview-empty {
  margin: 0;
  padding: 16px;
  color: #64748b;
  font-size: 13px;
  align-self: center;
}

.upload-box {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.upload-message {
  margin-top: 12px;
  color: #b91c1c;
  font-weight: 600;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 80;
  padding: 16px;
}

.hq-modal {
  width: min(1100px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
}

.card-like {
  border: 1px solid #e2e8f0;
}

.hq-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.hq-modal-title {
  margin: 0;
  font-size: 1.15rem;
}

.modal-grid {
  margin-top: 4px;
}

.preview-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 90;
  padding: 16px;
}

.preview-card {
  width: min(960px, calc(100vw - 32px));
  height: min(720px, calc(100vh - 64px));
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
}

.preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.preview-frame-legacy {
  flex: 1;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  width: 100%;
  min-height: 0;
}

.preview-image-legacy {
  flex: 1;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  width: 100%;
  object-fit: contain;
  min-height: 0;
  background: #f8fafc;
}

@media (max-width: 920px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
  .preview-pane {
    min-height: 42vh;
  }
  .preview-frame {
    min-height: 360px;
  }
}
</style>
