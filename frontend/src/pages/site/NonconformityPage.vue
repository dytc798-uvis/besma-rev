<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">부적합사항</div>
      <button class="secondary" @click="loadLedgers">새로고침</button>
    </div>
    <div class="upload-row">
      <input v-model="ledgerTitle" type="text" placeholder="대장 제목" />
      <input type="file" @change="onLedgerFileChange" />
      <button class="primary" :disabled="!ledgerFile || !ledgerTitle.trim() || uploadingLedger" @click="uploadLedger">
        {{ uploadingLedger ? "업로드 중..." : "대장 업로드" }}
      </button>
    </div>
    <table class="basic-table">
      <thead><tr><th>제목</th><th>업로드시각</th><th>다운로드</th><th>보기(PDF)</th></tr></thead>
      <tbody>
        <tr v-for="l in ledgers" :key="l.id">
          <td><button class="secondary" @click="selectLedger(l.id)">{{ l.title }}</button></td>
          <td>{{ formatDateTime(l.uploaded_at) }}</td>
          <td><a :href="resolveUrl(l.download_url)" target="_blank" rel="noopener">다운로드</a></td>
          <td><a :href="resolveUrl(l.pdf_view_url)" target="_blank" rel="noopener">보기</a></td>
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
              <a v-if="it.improvement_photo_url" :href="resolveUrl(it.improvement_photo_url)" target="_blank" rel="noopener">보기</a>
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
const ledgerTitle = ref("");
const ledgerFile = ref<File | null>(null);
const uploadingLedger = ref(false);
const draftItems = ref<Record<number, { improvement_action: string; improvement_date: string; improvement_owner: string }>>({});
const itemPhotos = ref<Record<number, File | null>>({});

function resolveUrl(path: string) { return `${api.defaults.baseURL}${path}`; }
function formatDateTime(v?: string) {
  if (!v) return "-";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
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
  if (!ledgerFile.value || !ledgerTitle.value.trim()) return;
  uploadingLedger.value = true;
  try {
    const form = new FormData();
    form.append("title", ledgerTitle.value.trim());
    form.append("file", ledgerFile.value);
    await api.post("/safety-features/nonconformities/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    ledgerTitle.value = "";
    ledgerFile.value = null;
    await loadLedgers();
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
  if (selectedLedger.value?.ledger?.id) await selectLedger(selectedLedger.value.ledger.id);
}

void loadLedgers();
</script>

