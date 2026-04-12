<template>
  <div class="voice-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">근로자의견청취 관리대장</h1>
        <p class="page-sub">현재 대장을 기준으로 row를 누적 관리하고, 엑셀 업로드는 초기 가져오기 용도로만 사용합니다.</p>
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
          <span class="summary-label">row 수</span>
          <strong>{{ siteItems.length }}</strong>
          <span class="summary-meta">현장 의견 누적 관리 기준</span>
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
            <h2 class="panel-title">새 의견 row 추가</h2>
            <p class="panel-sub">현장에서 직접 입력하고 조치 전/후와 담당자를 같은 row에서 관리합니다.</p>
          </div>
        </div>
        <div class="form-grid">
          <label>
            <span>근로자명</span>
            <input v-model="createDraft.worker_name" type="text" />
          </label>
          <label>
            <span>생년월일</span>
            <input v-model="createDraft.worker_birth_date" type="text" placeholder="예: 1980-01-01" />
          </label>
          <label>
            <span>연락처</span>
            <input v-model="createDraft.worker_phone_number" type="text" />
          </label>
          <label>
            <span>의견 종류</span>
            <input v-model="createDraft.opinion_kind" type="text" placeholder="예: 대면청취" />
          </label>
          <label class="span-2">
            <span>의견 내용</span>
            <textarea v-model="createDraft.opinion_text" rows="3" />
          </label>
          <label class="span-2">
            <span>조치 전</span>
            <textarea v-model="createDraft.action_before" rows="2" placeholder="현장 상태나 문제 상황" />
          </label>
          <label class="span-2">
            <span>조치 후</span>
            <textarea v-model="createDraft.action_after" rows="2" placeholder="실행한 조치 또는 결과" />
          </label>
          <label>
            <span>조치 상태</span>
            <select v-model="createDraft.action_status">
              <option value="">선택</option>
              <option value="OPEN">접수</option>
              <option value="IN_PROGRESS">조치중</option>
              <option value="DONE">완료</option>
              <option value="SHARED">공유완료</option>
            </select>
          </label>
          <label>
            <span>담당자</span>
            <input v-model="createDraft.action_owner" type="text" />
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
            <h2 class="panel-title">초기 가져오기</h2>
            <p class="panel-sub">기존 엑셀 대장은 최초 적재용으로만 사용합니다. 이후에는 아래 row를 직접 수정합니다.</p>
          </div>
        </div>
        <div class="import-row">
          <input ref="ledgerFileInput" type="file" accept=".xlsx,.xls,.csv" @change="onFileChange" />
          <button class="stitch-btn-secondary" type="button" :disabled="!ledgerFile || uploading" @click="uploadLedger">
            {{ uploading ? "가져오는 중..." : "엑셀 가져오기" }}
          </button>
        </div>
        <ul class="import-list">
          <li v-for="item in currentLedger?.imports || []" :key="item.id">
            <strong>{{ item.title }}</strong>
            <span>{{ item.file_name || "파일명 없음" }}</span>
            <span>{{ formatDateTimeKst(item.uploaded_at, "-") }}</span>
          </li>
          <li v-if="(currentLedger?.imports || []).length === 0" class="empty-inline">가져온 이력이 없습니다.</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">누적 row 관리</h2>
            <p class="panel-sub">저장하면 현재 대장과 목록이 즉시 다시 조회됩니다.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table class="ledger-table">
            <thead>
              <tr>
                <th>No</th>
                <th>근로자</th>
                <th>의견</th>
                <th>조치 전/후</th>
                <th>상태/담당</th>
                <th>사진</th>
                <th>검토</th>
                <th>저장</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in siteItems" :key="item.id">
                <tr>
                  <td>{{ item.row_no }}</td>
                  <td>
                    <div class="cell-stack">
                      <input v-model="drafts[item.id].worker_name" type="text" placeholder="근로자명" />
                      <input v-model="drafts[item.id].worker_phone_number" type="text" placeholder="연락처" />
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <input v-model="drafts[item.id].opinion_kind" type="text" placeholder="의견 종류" />
                      <textarea v-model="drafts[item.id].opinion_text" rows="3" />
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <textarea v-model="drafts[item.id].action_before" rows="2" placeholder="조치 전" />
                      <textarea v-model="drafts[item.id].action_after" rows="2" placeholder="조치 후" />
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <select v-model="drafts[item.id].action_status">
                        <option value="">선택</option>
                        <option value="OPEN">접수</option>
                        <option value="IN_PROGRESS">조치중</option>
                        <option value="DONE">완료</option>
                        <option value="SHARED">공유완료</option>
                      </select>
                      <input v-model="drafts[item.id].action_owner" type="text" placeholder="담당자" />
                      <span class="mini-badge">{{ actionStatusLabel(item.action_status) }}</span>
                    </div>
                  </td>
                  <td>
                    <div class="photo-col">
                      <button v-if="item.before_photo_url" class="link-btn" type="button" @click="openFile(item.before_photo_url, `before-${item.id}.jpg`)">전 사진</button>
                      <input type="file" accept="image/*" @change="onBeforePhotoChange($event, item.id)" />
                      <button v-if="item.after_photo_url" class="link-btn" type="button" @click="openFile(item.after_photo_url, `after-${item.id}.jpg`)">후 사진</button>
                      <input type="file" accept="image/*" @change="onAfterPhotoChange($event, item.id)" />
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack">
                      <span class="mini-badge" :class="badgeClass(item)">{{ statusText(item) }}</span>
                      <button class="stitch-btn-secondary btn-sm" type="button" :disabled="!canSiteApprove(item)" @click="siteApprove(item.id)">현장승인</button>
                      <button class="stitch-btn-secondary btn-sm" type="button" @click="toggleComments(item.id)">댓글</button>
                    </div>
                  </td>
                  <td>
                    <button class="stitch-btn-primary btn-sm" type="button" @click="saveSiteItem(item.id)">저장</button>
                  </td>
                </tr>
                <tr v-if="openedCommentsItemId === item.id">
                  <td colspan="8">
                    <div class="comment-box">
                      <p v-for="c in item.comments" :key="c.id">- {{ c.body }} ({{ c.created_by_name || "-" }})</p>
                      <p v-if="item.comments.length === 0" class="empty-inline">댓글이 없습니다.</p>
                      <div class="comment-write">
                        <input v-model="commentDrafts[item.id]" type="text" placeholder="댓글 입력" />
                        <button class="stitch-btn-secondary btn-sm" type="button" @click="addComment(item.id)">등록</button>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="siteItems.length === 0">
                <td colspan="8" class="empty-cell">등록된 의견 row가 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <section v-else class="panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">전체 의견 row</h2>
          <p class="panel-sub">본사에서는 현장 승인, 본사 체크, 포상 후보 지정 중심으로 사용합니다.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table class="ledger-table">
          <thead>
            <tr>
              <th>대장</th>
              <th>근로자</th>
              <th>의견</th>
              <th>조치</th>
              <th>상태</th>
              <th>소통</th>
              <th>액션</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="item in items" :key="item.id">
              <tr>
                <td>{{ item.ledger_title }}</td>
                <td>{{ item.worker_name || "-" }}</td>
                <td>{{ item.opinion_text }}</td>
                <td>{{ item.action_after || item.action_before || "-" }}</td>
                <td>
                  <div class="cell-stack">
                    <span class="mini-badge">{{ actionStatusLabel(item.action_status) }}</span>
                    <span class="mini-badge" :class="badgeClass(item)">{{ statusText(item) }}</span>
                  </div>
                </td>
                <td>
                  <button class="stitch-btn-secondary btn-sm" type="button" @click="toggleComments(item.id)">댓글</button>
                </td>
                <td class="action-inline">
                  <button class="stitch-btn-secondary btn-sm" type="button" :disabled="!canHqCheck(item)" @click="hqCheck(item.id)">본사체크</button>
                  <button class="stitch-btn-primary btn-sm" type="button" :disabled="!canPromote(item)" @click="promote(item.id)">포상후보</button>
                </td>
              </tr>
              <tr v-if="openedCommentsItemId === item.id">
                <td colspan="7">
                  <div class="comment-box">
                    <p v-for="c in item.comments" :key="c.id">- {{ c.body }} ({{ c.created_by_name || "-" }})</p>
                    <p v-if="item.comments.length === 0" class="empty-inline">댓글이 없습니다.</p>
                    <div class="comment-write">
                      <input v-model="commentDrafts[item.id]" type="text" placeholder="댓글 입력" />
                      <button class="stitch-btn-secondary btn-sm" type="button" @click="addComment(item.id)">등록</button>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="items.length === 0">
              <td colspan="7" class="empty-cell">데이터가 없습니다.</td>
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

interface CommentRow {
  id: number;
  body: string;
  created_by_name?: string | null;
}

interface WorkerVoiceItemRow {
  id: number;
  row_no: number;
  ledger_title: string;
  ledger_source_type?: string;
  worker_name?: string | null;
  worker_birth_date?: string | null;
  worker_phone_number?: string | null;
  opinion_kind?: string | null;
  opinion_text: string;
  action_before?: string | null;
  action_after?: string | null;
  action_status?: string | null;
  action_owner?: string | null;
  before_photo_url?: string | null;
  after_photo_url?: string | null;
  site_approved: boolean;
  hq_checked: boolean;
  reward_candidate: boolean;
  comments: CommentRow[];
}

interface SiteLedgerPayload {
  ledger: {
    id: number;
    title: string;
    source_type: string;
    uploaded_at: string | null;
    file_name: string | null;
  } | null;
  items: WorkerVoiceItemRow[];
  imports: Array<{ id: number; title: string; uploaded_at: string | null; file_name: string | null }>;
}

interface DraftRow {
  worker_name: string;
  worker_birth_date: string;
  worker_phone_number: string;
  opinion_kind: string;
  opinion_text: string;
  action_before: string;
  action_after: string;
  action_status: string;
  action_owner: string;
}

const auth = useAuthStore();
const items = ref<WorkerVoiceItemRow[]>([]);
const currentLedger = ref<SiteLedgerPayload | null>(null);
const ledgerFile = ref<File | null>(null);
const ledgerFileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const savingCreate = ref(false);
const openedCommentsItemId = ref<number | null>(null);
const drafts = ref<Record<number, DraftRow>>({});
const commentDrafts = ref<Record<number, string>>({});
const beforePhotos = ref<Record<number, File | null>>({});
const afterPhotos = ref<Record<number, File | null>>({});
const createDraft = ref<DraftRow>({
  worker_name: "",
  worker_birth_date: "",
  worker_phone_number: "",
  opinion_kind: "",
  opinion_text: "",
  action_before: "",
  action_after: "",
  action_status: "",
  action_owner: "",
});

const role = computed(() => auth.user?.role ?? "");
const isSite = computed(() => role.value === "SITE");
const siteItems = computed(() => currentLedger.value?.items ?? []);

function emptyDraft(): DraftRow {
  return {
    worker_name: "",
    worker_birth_date: "",
    worker_phone_number: "",
    opinion_kind: "",
    opinion_text: "",
    action_before: "",
    action_after: "",
    action_status: "",
    action_owner: "",
  };
}

function draftFromItem(item: WorkerVoiceItemRow): DraftRow {
  return {
    worker_name: item.worker_name || "",
    worker_birth_date: item.worker_birth_date || "",
    worker_phone_number: item.worker_phone_number || "",
    opinion_kind: item.opinion_kind || "",
    opinion_text: item.opinion_text || "",
    action_before: item.action_before || "",
    action_after: item.action_after || "",
    action_status: item.action_status || "",
    action_owner: item.action_owner || "",
  };
}

function syncDrafts(list: WorkerVoiceItemRow[]) {
  drafts.value = Object.fromEntries(list.map((item) => [item.id, draftFromItem(item)]));
}

function onFileChange(e: Event) {
  ledgerFile.value = (e.target as HTMLInputElement).files?.[0] ?? null;
}

function onBeforePhotoChange(e: Event, itemId: number) {
  beforePhotos.value[itemId] = (e.target as HTMLInputElement).files?.[0] ?? null;
}

function onAfterPhotoChange(e: Event, itemId: number) {
  afterPhotos.value[itemId] = (e.target as HTMLInputElement).files?.[0] ?? null;
}

function toggleComments(itemId: number) {
  openedCommentsItemId.value = openedCommentsItemId.value === itemId ? null : itemId;
}

function statusText(item: WorkerVoiceItemRow) {
  if (item.reward_candidate) return "포상후보";
  if (item.hq_checked) return "본사확인";
  if (item.site_approved) return "현장승인";
  return "등록";
}

function actionStatusLabel(value?: string | null) {
  if (value === "OPEN") return "접수";
  if (value === "IN_PROGRESS") return "조치중";
  if (value === "DONE") return "완료";
  if (value === "SHARED") return "공유완료";
  return "미설정";
}

function badgeClass(item: WorkerVoiceItemRow) {
  if (item.reward_candidate) return "badge-good";
  if (item.hq_checked) return "badge-blue";
  if (item.site_approved) return "badge-slate";
  return "";
}

function sourceLabel(sourceType?: string) {
  return sourceType === "IMPORT" ? "초기 가져오기 대장" : "수기 관리 대장";
}

function canSiteApprove(item: WorkerVoiceItemRow) {
  return role.value === "SITE" && !item.site_approved;
}

function canHqCheck(item: WorkerVoiceItemRow) {
  return ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) && item.site_approved && !item.hq_checked;
}

function canPromote(item: WorkerVoiceItemRow) {
  return ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) && item.site_approved && item.hq_checked && !item.reward_candidate;
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

async function load() {
  if (isSite.value) {
    const res = await api.get<SiteLedgerPayload>("/safety-features/worker-voice/ledger");
    currentLedger.value = res.data;
    items.value = res.data.items ?? [];
    syncDrafts(items.value);
    return;
  }
  const res = await api.get<{ items: WorkerVoiceItemRow[] }>("/safety-features/worker-voice/items");
  items.value = res.data.items ?? [];
}

async function uploadLedger() {
  if (!ledgerFile.value) return;
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("file", ledgerFile.value);
    await api.post("/safety-features/worker-voice/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    ledgerFile.value = null;
    if (ledgerFileInput.value) ledgerFileInput.value.value = "";
    await load();
  } finally {
    uploading.value = false;
  }
}

function buildFormFromDraft(draft: DraftRow) {
  const form = new FormData();
  form.append("worker_name", draft.worker_name || "");
  form.append("worker_birth_date", draft.worker_birth_date || "");
  form.append("worker_phone_number", draft.worker_phone_number || "");
  form.append("opinion_kind", draft.opinion_kind || "");
  form.append("opinion_text", draft.opinion_text || "");
  form.append("action_before", draft.action_before || "");
  form.append("action_after", draft.action_after || "");
  form.append("action_status", draft.action_status || "");
  form.append("action_owner", draft.action_owner || "");
  return form;
}

async function createItem() {
  if (!createDraft.value.opinion_text.trim()) return;
  savingCreate.value = true;
  try {
    await api.post("/safety-features/worker-voice/items", buildFormFromDraft(createDraft.value), {
      headers: { "Content-Type": "multipart/form-data" },
    });
    createDraft.value = emptyDraft();
    await load();
  } finally {
    savingCreate.value = false;
  }
}

async function saveSiteItem(itemId: number) {
  const draft = drafts.value[itemId];
  await api.post(`/safety-features/worker-voice/items/${itemId}`, buildFormFromDraft(draft), {
    headers: { "Content-Type": "multipart/form-data" },
  });
  if (beforePhotos.value[itemId]) {
    const form = new FormData();
    form.append("file", beforePhotos.value[itemId] as File);
    await api.post(`/safety-features/worker-voice/items/${itemId}/before-photo`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
  if (afterPhotos.value[itemId]) {
    const form = new FormData();
    form.append("file", afterPhotos.value[itemId] as File);
    await api.post(`/safety-features/worker-voice/items/${itemId}/after-photo`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
  beforePhotos.value[itemId] = null;
  afterPhotos.value[itemId] = null;
  await load();
}

async function siteApprove(itemId: number) {
  await api.post(`/safety-features/worker-voice/items/${itemId}/site-approve`);
  await load();
}

async function hqCheck(itemId: number) {
  await api.post(`/safety-features/worker-voice/items/${itemId}/hq-check`);
  await load();
}

async function promote(itemId: number) {
  await api.post(`/safety-features/worker-voice/items/${itemId}/reward-candidate`);
  await load();
}

async function addComment(itemId: number) {
  const body = (commentDrafts.value[itemId] || "").trim();
  if (!body) return;
  const form = new FormData();
  form.append("body", body);
  await api.post(`/safety-features/worker-voice/items/${itemId}/comments`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  commentDrafts.value[itemId] = "";
  await load();
}

void load();
</script>

<style scoped>
.voice-page {
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
  display: flex;
  justify-content: space-between;
  gap: 12px;
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

.table-wrap {
  overflow-x: auto;
}

.ledger-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 980px;
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

.photo-col,
.action-inline {
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

.badge-good {
  background: #dcfce7;
  color: #166534;
}

.badge-blue {
  background: #dbeafe;
  color: #1d4ed8;
}

.badge-slate {
  background: #e2e8f0;
  color: #334155;
}

.btn-sm {
  padding: 6px 10px;
  font-size: 12px;
}

.comment-box {
  display: grid;
  gap: 8px;
  color: #334155;
  font-size: 13px;
}

.comment-write {
  display: flex;
  gap: 8px;
  align-items: center;
}

.comment-write input {
  flex: 1;
}

.link-btn {
  border: 0;
  background: transparent;
  color: #2563eb;
  padding: 0;
  cursor: pointer;
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
  .form-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: auto;
  }

  .page-head {
    flex-direction: column;
  }
}
</style>
