<template>
  <div class="nonconf-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">부적합사항 관리대장</h1>
        <p class="page-sub">현장 row를 누적 관리하고, 업로드 파일은 초기 적재 또는 참고 이력으로만 유지합니다.</p>
      </div>
      <button class="stitch-btn-secondary" type="button" @click="load">새로고침</button>
    </div>

    <template v-if="isSite">
      <section class="summary-grid">
        <article class="summary-card">
          <span class="summary-label">현재 대장</span>
          <strong>{{ currentLedger?.ledger?.title || "자동 생성 대장" }}</strong>
          <span class="summary-meta">{{ currentLedger?.ledger ? sourceLabel(currentLedger.ledger.source_type) : "수기 관리 준비됨" }}</span>
        </article>
        <article class="summary-card">
          <span class="summary-label">누적 row</span>
          <strong>{{ currentItems.length }}</strong>
          <span class="summary-meta">현재 조치 관리 기준</span>
        </article>
        <article class="summary-card">
          <span class="summary-label">최근 반영</span>
          <strong>{{ formatDateTimeKst(currentLedger?.ledger?.uploaded_at, "—") }}</strong>
          <span class="summary-meta">KST 기준</span>
        </article>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">새 부적합 row 추가</h2>
            <p class="panel-sub">부적합 내용, 조치 전/후, 상태, 기한, 완료일을 같은 row에서 관리합니다.</p>
          </div>
        </div>
        <div class="form-grid">
          <label class="span-2">
            <span>부적합 내용</span>
            <textarea v-model="createDraft.issue_text" rows="3" />
          </label>
          <label class="span-2">
            <span>조치 전</span>
            <textarea v-model="createDraft.action_before" rows="2" />
          </label>
          <label class="span-2">
            <span>조치 후</span>
            <textarea v-model="createDraft.action_after" rows="2" />
          </label>
          <label>
            <span>상태</span>
            <select v-model="createDraft.action_status">
              <option value="">선택</option>
              <option value="OPEN">접수</option>
              <option value="IN_PROGRESS">조치중</option>
              <option value="DONE">완료</option>
              <option value="HOLD">보류</option>
            </select>
          </label>
          <label>
            <span>담당자</span>
            <input v-model="createDraft.action_owner" type="text" />
          </label>
          <label>
            <span>조치 기한</span>
            <input v-model="createDraft.action_due_date" type="date" />
          </label>
          <label>
            <span>완료일</span>
            <input v-model="createDraft.completed_at" type="date" />
          </label>
        </div>
        <div class="panel-actions">
          <button class="stitch-btn-primary" type="button" :disabled="savingCreate" @click="createItem">
            {{ savingCreate ? "추가 중..." : "row 추가" }}
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">초기 가져오기 / 이력</h2>
            <p class="panel-sub">엑셀 업로드는 기존 대장 초기 적재용으로만 사용합니다.</p>
          </div>
        </div>
        <div class="import-row">
          <input ref="ledgerFileInput" type="file" @change="onLedgerFileChange" />
          <button class="stitch-btn-secondary" type="button" :disabled="!ledgerFile || uploadingLedger" @click="uploadLedger">
            {{ uploadingLedger ? "가져오는 중..." : "엑셀 가져오기" }}
          </button>
        </div>
        <ul class="import-list">
          <li v-for="item in currentLedger?.imports || []" :key="item.id">
            <strong>{{ item.title }}</strong>
            <span>{{ formatDateTimeKst(item.uploaded_at, "-") }}</span>
            <div class="import-actions">
              <button v-if="item.download_url" class="link-btn" type="button" @click="downloadLedger(item.download_url, item.file_name)">원본</button>
              <button class="link-btn" type="button" @click="openLedgerPdf(item.pdf_view_url, `${item.title || 'nonconformity'}.pdf`)">PDF</button>
            </div>
          </li>
          <li v-if="(currentLedger?.imports || []).length === 0" class="empty-inline">가져온 이력이 없습니다.</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">누적 row 관리</h2>
            <p class="panel-sub">저장 후 현재 목록이 즉시 다시 조회됩니다.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table class="ledger-table">
            <thead>
              <tr>
                <th>No</th>
                <th>부적합 내용</th>
                <th>조치 전/후</th>
                <th>상태/담당</th>
                <th>기한/완료</th>
                <th>사진</th>
                <th>저장</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in currentItems" :key="item.id">
                <td>{{ item.row_no }}</td>
                <td>
                  <textarea v-model="draftItems[item.id].issue_text" rows="3" />
                </td>
                <td>
                  <div class="cell-stack">
                    <textarea v-model="draftItems[item.id].action_before" rows="2" placeholder="조치 전" />
                    <textarea v-model="draftItems[item.id].action_after" rows="2" placeholder="조치 후" />
                  </div>
                </td>
                <td>
                  <div class="cell-stack">
                    <select v-model="draftItems[item.id].action_status">
                      <option value="">선택</option>
                      <option value="OPEN">접수</option>
                      <option value="IN_PROGRESS">조치중</option>
                      <option value="DONE">완료</option>
                      <option value="HOLD">보류</option>
                    </select>
                    <input v-model="draftItems[item.id].action_owner" type="text" placeholder="담당자" />
                    <span class="mini-badge">{{ actionStatusLabel(item.action_status) }}</span>
                  </div>
                </td>
                <td>
                  <div class="cell-stack">
                    <input v-model="draftItems[item.id].action_due_date" type="date" />
                    <input v-model="draftItems[item.id].completed_at" type="date" />
                  </div>
                </td>
                <td>
                  <div class="photo-col">
                    <button v-if="item.before_photo_url" class="link-btn" type="button" @click="openFile(item.before_photo_url, `nonconf-before-${item.id}.jpg`)">전 사진</button>
                    <input type="file" accept="image/*" @change="onBeforePhotoChange($event, item.id)" />
                    <button v-if="item.after_photo_url" class="link-btn" type="button" @click="openFile(item.after_photo_url, `nonconf-after-${item.id}.jpg`)">후 사진</button>
                    <input type="file" accept="image/*" @change="onAfterPhotoChange($event, item.id)" />
                  </div>
                </td>
                <td>
                  <button class="stitch-btn-primary btn-sm" type="button" @click="saveItem(item.id)">저장</button>
                </td>
              </tr>
              <tr v-if="currentItems.length === 0">
                <td colspan="7" class="empty-cell">등록된 row가 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <section v-else class="panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">대장 이력</h2>
          <p class="panel-sub">본사에서는 업로드 이력과 PDF 출력 상태를 확인합니다.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table class="ledger-table">
          <thead>
            <tr>
              <th>제목</th>
              <th>업로드 시각</th>
              <th>원본</th>
              <th>PDF</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in ledgers" :key="l.id">
              <td>{{ l.title }}</td>
              <td>{{ formatDateTimeKst(l.uploaded_at, "-") }}</td>
              <td><button v-if="l.download_url" class="link-btn" type="button" @click="downloadLedger(l.download_url, l.file_name)">다운로드</button></td>
              <td><button class="link-btn" type="button" @click="openLedgerPdf(l.pdf_view_url, `${l.title || 'nonconformity'}.pdf`)">보기</button></td>
            </tr>
            <tr v-if="ledgers.length === 0">
              <td colspan="4" class="empty-cell">이력이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { canPreviewInBrowser } from "@/utils/filePreview";
import { formatDateTimeKst } from "@/utils/datetime";

interface LedgerRow {
  id: number;
  title: string;
  source_type?: string;
  uploaded_at: string | null;
  file_name: string | null;
  download_url?: string | null;
  pdf_view_url: string;
}

interface NonconformityItemRow {
  id: number;
  row_no: number;
  issue_text: string;
  action_before?: string | null;
  action_after?: string | null;
  action_status?: string | null;
  action_due_date?: string | null;
  completed_at?: string | null;
  action_owner?: string | null;
  before_photo_url?: string | null;
  after_photo_url?: string | null;
}

interface CurrentLedgerPayload {
  ledger: LedgerRow | null;
  items: NonconformityItemRow[];
  imports: LedgerRow[];
}

interface DraftItem {
  issue_text: string;
  action_before: string;
  action_after: string;
  action_status: string;
  action_due_date: string;
  completed_at: string;
  action_owner: string;
}

const auth = useAuthStore();
const ledgers = ref<LedgerRow[]>([]);
const currentLedger = ref<CurrentLedgerPayload | null>(null);
const ledgerFile = ref<File | null>(null);
const ledgerFileInput = ref<HTMLInputElement | null>(null);
const uploadingLedger = ref(false);
const savingCreate = ref(false);
const draftItems = ref<Record<number, DraftItem>>({});
const beforePhotos = ref<Record<number, File | null>>({});
const afterPhotos = ref<Record<number, File | null>>({});
const createDraft = ref<DraftItem>({
  issue_text: "",
  action_before: "",
  action_after: "",
  action_status: "",
  action_due_date: "",
  completed_at: "",
  action_owner: "",
});

const isSite = computed(() => auth.user?.role === "SITE");
const currentItems = computed(() => currentLedger.value?.items ?? []);

function emptyDraft(): DraftItem {
  return {
    issue_text: "",
    action_before: "",
    action_after: "",
    action_status: "",
    action_due_date: "",
    completed_at: "",
    action_owner: "",
  };
}

function draftFromItem(item: NonconformityItemRow): DraftItem {
  return {
    issue_text: item.issue_text || "",
    action_before: item.action_before || "",
    action_after: item.action_after || "",
    action_status: item.action_status || "",
    action_due_date: item.action_due_date || "",
    completed_at: item.completed_at || "",
    action_owner: item.action_owner || "",
  };
}

function syncDrafts(items: NonconformityItemRow[]) {
  draftItems.value = Object.fromEntries(items.map((item) => [item.id, draftFromItem(item)]));
}

function sourceLabel(sourceType?: string) {
  return sourceType === "IMPORT" ? "초기 가져오기 대장" : "수기 관리 대장";
}

function actionStatusLabel(value?: string | null) {
  if (value === "OPEN") return "접수";
  if (value === "IN_PROGRESS") return "조치중";
  if (value === "DONE") return "완료";
  if (value === "HOLD") return "보류";
  return "미설정";
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

function onLedgerFileChange(e: Event) {
  ledgerFile.value = (e.target as HTMLInputElement).files?.[0] ?? null;
}

function onBeforePhotoChange(e: Event, itemId: number) {
  beforePhotos.value[itemId] = (e.target as HTMLInputElement).files?.[0] ?? null;
}

function onAfterPhotoChange(e: Event, itemId: number) {
  afterPhotos.value[itemId] = (e.target as HTMLInputElement).files?.[0] ?? null;
}

async function load() {
  if (isSite.value) {
    const res = await api.get<CurrentLedgerPayload>("/safety-features/nonconformities/overview/current");
    currentLedger.value = res.data;
    ledgers.value = res.data.imports ?? [];
    syncDrafts(res.data.items ?? []);
    return;
  }
  const res = await api.get<{ items: LedgerRow[] }>("/safety-features/nonconformities");
  ledgers.value = res.data.items ?? [];
}

function buildItemForm(draft: DraftItem) {
  const form = new FormData();
  form.append("issue_text", draft.issue_text || "");
  form.append("action_before", draft.action_before || "");
  form.append("action_after", draft.action_after || "");
  form.append("action_status", draft.action_status || "");
  form.append("action_due_date", draft.action_due_date || "");
  form.append("completed_at", draft.completed_at || "");
  form.append("action_owner", draft.action_owner || "");
  return form;
}

async function uploadLedger() {
  if (!ledgerFile.value) return;
  uploadingLedger.value = true;
  try {
    const form = new FormData();
    form.append("file", ledgerFile.value);
    await api.post("/safety-features/nonconformities/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    ledgerFile.value = null;
    if (ledgerFileInput.value) ledgerFileInput.value.value = "";
    await load();
  } finally {
    uploadingLedger.value = false;
  }
}

async function createItem() {
  if (!createDraft.value.issue_text.trim()) return;
  savingCreate.value = true;
  try {
    await api.post("/safety-features/nonconformities/items", buildItemForm(createDraft.value), {
      headers: { "Content-Type": "multipart/form-data" },
    });
    createDraft.value = emptyDraft();
    await load();
  } finally {
    savingCreate.value = false;
  }
}

async function saveItem(itemId: number) {
  const draft = draftItems.value[itemId];
  await api.post(`/safety-features/nonconformities/items/${itemId}`, buildItemForm(draft), {
    headers: { "Content-Type": "multipart/form-data" },
  });
  if (beforePhotos.value[itemId]) {
    const form = new FormData();
    form.append("file", beforePhotos.value[itemId] as File);
    await api.post(`/safety-features/nonconformities/items/${itemId}/before-photo`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
  if (afterPhotos.value[itemId]) {
    const form = new FormData();
    form.append("file", afterPhotos.value[itemId] as File);
    await api.post(`/safety-features/nonconformities/items/${itemId}/after-photo`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
  beforePhotos.value[itemId] = null;
  afterPhotos.value[itemId] = null;
  await load();
}

void load();
</script>

<style scoped>
.nonconf-page {
  display: grid;
  gap: 16px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.page-sub {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.summary-card,
.panel {
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  padding: 16px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-label,
.panel-sub {
  color: #64748b;
  font-size: 12px;
}

.summary-meta {
  color: #475569;
  font-size: 12px;
}

.panel-head {
  margin-bottom: 12px;
}

.panel-title {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-grid label,
.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-grid label span {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.span-2 {
  grid-column: 1 / -1;
}

input,
textarea,
select {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
}

.panel-actions {
  margin-top: 12px;
}

.import-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.import-list {
  margin: 12px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
}

.import-actions {
  display: inline-flex;
  gap: 8px;
  margin-left: 8px;
}

.table-wrap {
  overflow-x: auto;
}

.ledger-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 960px;
}

.ledger-table th,
.ledger-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px;
  vertical-align: top;
  text-align: left;
}

.ledger-table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
}

.photo-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mini-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #334155;
  font-size: 11px;
  font-weight: 700;
}

.btn-sm {
  padding: 6px 10px;
  font-size: 12px;
}

.link-btn {
  border: 0;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.empty-inline,
.empty-cell {
  color: #64748b;
}

.empty-cell {
  text-align: center;
}

@media (max-width: 960px) {
  .page-head {
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: auto;
  }
}
</style>
