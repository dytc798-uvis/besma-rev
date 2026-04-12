<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">부적합사항</div>
      <button class="secondary" @click="loadLedgers">새로고침</button>
    </div>
    <div class="upload-row">
      <input ref="ledgerFileInput" type="file" @change="onLedgerFileChange" />
      <button class="primary" :disabled="!ledgerFile || uploadingLedger" @click="uploadLedger">
        {{ uploadingLedger ? "업로드 중..." : "대장 업로드" }}
      </button>
    </div>
    <table class="basic-table">
      <thead><tr><th>제목</th><th>업로드시각</th><th>다운로드</th><th>보기(PDF)</th></tr></thead>
      <tbody>
        <tr v-for="l in ledgers" :key="l.id">
          <td><button class="secondary" @click="selectLedger(l.id)">{{ l.title }}</button></td>
          <td>{{ formatDateTime(l.uploaded_at) }}</td>
          <td><button class="link-btn" type="button" @click="downloadLedger(l.download_url, l.file_name)">다운로드</button></td>
          <td><button class="link-btn" type="button" @click="openLedgerPdf(l.pdf_view_url, `${l.title || 'nonconformity'}.pdf`)">보기</button></td>
        </tr>
      </tbody>
    </table>

    <div v-if="selectedLedger" style="margin-top: 12px">
      <h3>{{ selectedLedger.ledger.title }}</h3>
      <table class="basic-table">
        <thead><tr><th>부적합사항</th><th>개선조치</th><th>일자</th><th>담당자</th><th>사진</th><th>저장</th></tr></thead>
        <tbody>
          <tr v-for="it in selectedLedger.items" :key="it.id">
            <td>{{ it.issue_text }}</td>
            <td><textarea v-model="draftItems[it.id].improvement_action" rows="2" /></td>
            <td><input v-model="draftItems[it.id].improvement_date" type="date" /></td>
            <td><input v-model="draftItems[it.id].improvement_owner" type="text" /></td>
            <td>
              <button v-if="it.improvement_photo_url" class="link-btn" type="button" @click="openFile(it.improvement_photo_url, `nonconformity-photo-${it.id}.jpg`)">보기</button>
              <input type="file" @change="onItemPhotoChange($event, it.id)" />
            </td>
            <td><button class="secondary" @click="saveItem(it.id)">저장</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/services/api";

const ledgers = ref<any[]>([]);
const selectedLedger = ref<any | null>(null);
const ledgerFile = ref<File | null>(null);
const ledgerFileInput = ref<HTMLInputElement | null>(null);
const uploadingLedger = ref(false);
const draftItems = ref<Record<number, { improvement_action: string; improvement_date: string; improvement_owner: string }>>({});
const itemPhotos = ref<Record<number, File | null>>({});

function formatDateTime(v?: string) {
  if (!v) return "-";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
}

function canPreviewInBrowser(fileName: string | null) {
  const ext = (fileName || "").split(".").pop()?.toLowerCase() || "";
  return ["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"].includes(ext);
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

async function openFile(path: string, fileName: string | null) {
  const previewable = canPreviewInBrowser(fileName);
  const res = await api.get(path, {
    params: { disposition: previewable ? "inline" : "attachment" },
    responseType: "blob",
  });
  const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
  const blob = new Blob([res.data], { type: contentType });
  if (!previewable) {
    downloadBlob(blob, fileName || "download.bin");
    return;
  }
  const url = window.URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => window.URL.revokeObjectURL(url), 5000);
}

async function downloadLedger(path: string, fileName: string | null) {
  const res = await api.get(path, {
    params: { disposition: "attachment" },
    responseType: "blob",
  });
  const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
  downloadBlob(new Blob([res.data], { type: contentType }), fileName || "nonconformity-ledger.bin");
}

async function openLedgerPdf(path: string, fileName: string | null) {
  await openFile(path, fileName);
}

function onLedgerFileChange(e: Event) { ledgerFile.value = (e.target as HTMLInputElement).files?.[0] ?? null; }
function onItemPhotoChange(e: Event, itemId: number) { itemPhotos.value[itemId] = (e.target as HTMLInputElement).files?.[0] ?? null; }

async function loadLedgers() { const res = await api.get("/safety-features/nonconformities"); ledgers.value = res.data.items ?? []; }
async function selectLedger(id: number) {
  const res = await api.get(`/safety-features/nonconformities/${id}`);
  selectedLedger.value = res.data;
  const next: Record<number, { improvement_action: string; improvement_date: string; improvement_owner: string }> = {};
  for (const it of selectedLedger.value.items) {
    next[it.id] = {
      improvement_action: it.improvement_action || "",
      improvement_date: it.improvement_date || "",
      improvement_owner: it.improvement_owner || "",
    };
  }
  draftItems.value = next;
}
async function uploadLedger() {
  if (!ledgerFile.value) return;
  uploadingLedger.value = true;
  try {
    const form = new FormData();
    form.append("file", ledgerFile.value);
    const res = await api.post("/safety-features/nonconformities/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    ledgerFile.value = null;
    if (ledgerFileInput.value) {
      ledgerFileInput.value.value = "";
    }
    await loadLedgers();
    if (res.data?.id) {
      await selectLedger(res.data.id);
    }
  } finally { uploadingLedger.value = false; }
}
async function saveItem(itemId: number) {
  const draft = draftItems.value[itemId];
  const form = new FormData();
  form.append("improvement_action", draft.improvement_action || "");
  form.append("improvement_date", draft.improvement_date || "");
  form.append("improvement_owner", draft.improvement_owner || "");
  await api.post(`/safety-features/nonconformities/items/${itemId}`, form, { headers: { "Content-Type": "multipart/form-data" } });
  if (itemPhotos.value[itemId]) {
    const p = new FormData();
    p.append("file", itemPhotos.value[itemId] as File);
    await api.post(`/safety-features/nonconformities/items/${itemId}/photo`, p, { headers: { "Content-Type": "multipart/form-data" } });
  }
  itemPhotos.value[itemId] = null;
  if (selectedLedger.value?.ledger?.id) {
    await Promise.all([loadLedgers(), selectLedger(selectedLedger.value.ledger.id)]);
  }
}

void loadLedgers();
</script>

<style scoped>
.link-btn {
  border: 0;
  background: transparent;
  color: #1d4ed8;
  cursor: pointer;
  padding: 0;
}
</style>
