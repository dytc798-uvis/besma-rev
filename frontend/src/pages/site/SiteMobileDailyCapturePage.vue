<template>
  <div class="capture-page">
    <div class="hero">
      <h1>TBM · 일일안전회의 사진</h1>
      <p class="lead">
        현장 사진을 먼저 저장해 두었다가, 같은 날 PDF 일지를 올리면 <strong>일지 뒤에</strong> 자동으로 붙습니다. 순서는 자유롭습니다.
        임시 사진은 이 브라우저(기기)에만 저장되며, 다른 기기와 공유되지 않습니다.
      </p>
    </div>

    <div v-if="!siteId" class="card warn">현장 정보를 확인할 수 없습니다. 다시 로그인해 주세요.</div>

    <template v-else>
      <div class="card field-row">
        <label>작업일 (KST)</label>
        <input v-model="workDate" type="date" class="date-input" />
      </div>

      <div class="card">
        <div class="seg">
          <button type="button" :class="{ on: docCode === 'DAILY_TBM' }" @click="docCode = 'DAILY_TBM'">TBM</button>
          <button
            type="button"
            :class="{ on: docCode === 'DAILY_SAFETY_MEETING_LOG' }"
            @click="docCode = 'DAILY_SAFETY_MEETING_LOG'"
          >
            일일안전회의 일지
          </button>
        </div>

        <p class="hint">
          {{ docTitle }} · 임시 사진 {{ draftPhotos.length }}장
          <span v-if="!requirementRow">(요구사항이 없으면 업로드할 수 없습니다)</span>
        </p>

        <div class="actions">
          <label class="btn primary">
            사진 추가
            <input type="file" accept="image/*" multiple class="hidden-input" @change="onPickPhotos" />
          </label>
          <button type="button" class="btn secondary" :disabled="!draftPhotos.length" @click="clearDraft">임시 사진 비우기</button>
        </div>

        <ul v-if="draftPhotos.length" class="thumbs">
          <li v-for="p in draftPhotos" :key="p.id" class="thumb">
            <img :src="p.dataUrl" alt="" />
            <button type="button" class="thumb-remove" @click="removeOne(p.id)">삭제</button>
          </li>
        </ul>
      </div>

      <div class="card">
        <h2>일지 PDF 업로드 (임시 사진 자동 병합)</h2>
        <p class="hint">본문은 PDF여야 사진을 뒤에 붙일 수 있습니다. HWP 등은 병합되지 않습니다.</p>
        <div class="actions">
          <label class="btn primary">
            PDF 선택
            <input type="file" accept=".pdf,application/pdf" class="hidden-input" @change="onPickLogPdf" />
          </label>
          <span v-if="logPdf" class="file-name">{{ logPdf.name }}</span>
        </div>
        <p v-if="uploadMessage" class="msg" :class="{ err: uploadError }">{{ uploadMessage }}</p>
        <button type="button" class="btn primary wide" :disabled="!canUploadLog || uploading" @click="submitLogWithDraft">
          {{ uploading ? "업로드 중…" : "제출" }}
        </button>
      </div>

      <div v-if="requirementRow?.current_cycle_instance_id" class="card">
        <h2>이미 올린 일지에 사진만 덧붙이기</h2>
        <p class="hint">제출·검토 중인 PDF 뒤에만 추가됩니다. 승인 완료 문서는 추가할 수 없습니다.</p>
        <div class="actions">
          <label class="btn secondary">
            사진/PDF 선택
            <input type="file" accept="image/*,.pdf,application/pdf" multiple class="hidden-input" @change="onPickAppend" />
          </label>
        </div>
        <p v-if="appendFiles.length" class="file-name">{{ appendFiles.length }}개 파일</p>
        <p v-if="appendMessage" class="msg" :class="{ err: appendError }">{{ appendMessage }}</p>
        <button type="button" class="btn secondary wide" :disabled="!canAppend || appending" @click="submitAppendOnly">
          {{ appending ? "처리 중…" : "기존 일지 뒤에 붙이기" }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { todayKst } from "@/utils/datetime";
import {
  addDraftPhotosFromFiles,
  clearDraftPhotos,
  dataUrlToBlob,
  listDraftPhotos,
  removeDraftPhoto,
} from "@/utils/dailyAttachmentDraft";

type StatusItem = {
  requirement_id: number;
  title: string;
  document_type_code: string;
  current_cycle_instance_id: number | null;
  current_cycle_status?: string | null;
};

const auth = useAuthStore();
const siteId = computed(() => auth.effectiveSiteId ?? auth.user?.site_id ?? null);
const workDate = ref(todayKst());
const docCode = ref<"DAILY_TBM" | "DAILY_SAFETY_MEETING_LOG">("DAILY_TBM");
const items = ref<StatusItem[]>([]);
const draftPhotos = ref(listDraftPhotos(0, workDate.value, docCode.value));

const requirementRow = computed(() => items.value.find((r) => r.document_type_code === docCode.value) ?? null);

const docTitle = computed(() => (docCode.value === "DAILY_TBM" ? "TBM" : "일일안전회의 일지"));

const logPdf = ref<File | null>(null);
const uploadMessage = ref("");
const uploadError = ref(false);
const uploading = ref(false);

const appendFiles = ref<File[]>([]);
const appendMessage = ref("");
const appendError = ref(false);
const appending = ref(false);

const canUploadLog = computed(
  () =>
    !!siteId.value &&
    !!requirementRow.value &&
    !!logPdf.value &&
    requirementRow.value.document_type_code === docCode.value,
);

const canAppend = computed(
  () =>
    !!siteId.value &&
    !!requirementRow.value?.current_cycle_instance_id &&
    appendFiles.value.length > 0 &&
    ["SUBMITTED", "IN_REVIEW"].includes(String(requirementRow.value?.current_cycle_status || "")),
);

function refreshDraftList() {
  if (!siteId.value) {
    draftPhotos.value = [];
    return;
  }
  draftPhotos.value = listDraftPhotos(siteId.value, workDate.value, docCode.value);
}

async function loadStatus() {
  if (!siteId.value) return;
  uploadMessage.value = "";
  appendMessage.value = "";
  try {
    const res = await api.get("/documents/requirements/status", {
      params: { site_id: siteId.value, period: "all", date: workDate.value },
    });
    items.value = res.data.items ?? [];
  } catch {
    items.value = [];
  }
  refreshDraftList();
}

watch([siteId, workDate, docCode], () => {
  void loadStatus();
  refreshDraftList();
});

void loadStatus();
refreshDraftList();

async function onPickPhotos(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files?.length || !siteId.value) return;
  await addDraftPhotosFromFiles(siteId.value, workDate.value, docCode.value, files);
  input.value = "";
  refreshDraftList();
}

function clearDraft() {
  if (!siteId.value) return;
  clearDraftPhotos(siteId.value, workDate.value, docCode.value);
  refreshDraftList();
}

function removeOne(id: string) {
  if (!siteId.value) return;
  removeDraftPhoto(siteId.value, workDate.value, docCode.value, id);
  refreshDraftList();
}

function onPickLogPdf(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0] ?? null;
  logPdf.value = f;
  uploadMessage.value = "";
}

function onPickAppend(e: Event) {
  const fs = (e.target as HTMLInputElement).files;
  appendFiles.value = fs ? Array.from(fs) : [];
  appendMessage.value = "";
}

async function submitLogWithDraft() {
  if (!canUploadLog.value || !siteId.value || !requirementRow.value || !logPdf.value) return;
  uploading.value = true;
  uploadError.value = false;
  uploadMessage.value = "";
  try {
    const form = new FormData();
    form.append("site_id", String(siteId.value));
    form.append("requirement_id", String(requirementRow.value.requirement_id));
    form.append("document_type_code", docCode.value);
    form.append("work_date", workDate.value);
    form.append("file", logPdf.value);
    const shots = listDraftPhotos(siteId.value, workDate.value, docCode.value);
    for (const p of shots) {
      const blob = dataUrlToBlob(p.dataUrl);
      form.append("append_files", blob, p.name || "attach.jpg");
    }
    await api.post("/document-submissions/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    clearDraftPhotos(siteId.value, workDate.value, docCode.value);
    logPdf.value = null;
    refreshDraftList();
    uploadMessage.value = "업로드되었습니다.";
    await loadStatus();
  } catch (err: unknown) {
    uploadError.value = true;
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    uploadMessage.value = typeof detail === "string" ? detail : "업로드에 실패했습니다.";
  } finally {
    uploading.value = false;
  }
}

async function submitAppendOnly() {
  if (!canAppend.value || !siteId.value || !requirementRow.value?.current_cycle_instance_id) return;
  appending.value = true;
  appendError.value = false;
  appendMessage.value = "";
  try {
    const form = new FormData();
    form.append("instance_id", String(requirementRow.value.current_cycle_instance_id));
    form.append("append_only", "true");
    for (const f of appendFiles.value) {
      form.append("append_files", f);
    }
    await api.post("/document-submissions/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    appendFiles.value = [];
    appendMessage.value = "첨부가 반영되었습니다.";
    await loadStatus();
  } catch (err: unknown) {
    appendError.value = true;
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    appendMessage.value = typeof detail === "string" ? detail : "처리에 실패했습니다.";
  } finally {
    appending.value = false;
  }
}
</script>

<style scoped>
.capture-page {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 1.35rem;
}

.lead {
  margin: 0;
  color: #475569;
  font-size: 0.95rem;
  line-height: 1.5;
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px 16px;
}

.card.warn {
  border-color: #fdba74;
  background: #fff7ed;
}

.card h2 {
  margin: 0 0 8px;
  font-size: 1.05rem;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.date-input {
  max-width: 200px;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.seg {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.seg button {
  flex: 1;
  padding: 10px 8px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  font-weight: 600;
  cursor: pointer;
}

.seg button.on {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.hint {
  margin: 0 0 10px;
  font-size: 0.85rem;
  color: #64748b;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 14px;
  border-radius: 10px;
  border: none;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn.primary {
  background: #2563eb;
  color: #fff;
}

.btn.secondary {
  background: #e2e8f0;
  color: #0f172a;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn.wide {
  width: 100%;
}

.hidden-input {
  display: none;
}

.file-name {
  font-size: 0.85rem;
  color: #334155;
}

.thumbs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 8px;
}

.thumb {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.thumb img {
  width: 100%;
  height: 88px;
  object-fit: cover;
  display: block;
}

.thumb-remove {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  border: none;
  background: rgba(15, 23, 42, 0.75);
  color: #fff;
  font-size: 0.7rem;
  padding: 4px;
  cursor: pointer;
}

.msg {
  font-size: 0.88rem;
  color: #15803d;
  margin: 8px 0;
}

.msg.err {
  color: #b91c1c;
}
</style>
