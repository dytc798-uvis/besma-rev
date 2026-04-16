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
            <h2 class="panel-title">초기 가져오기 / 이력</h2>
            <p class="panel-sub">기본 운영은 기존 대장 업로드입니다. 수동 row 입력은 아래 보조 기능에서만 사용합니다.</p>
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

      <details class="manual-panel">
        <summary>수동 row 추가 (보조)</summary>
        <section class="panel nested-manual">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">새 부적합 row 추가</h2>
              <p class="panel-sub">업로드 파일에 없는 예외 건만 필요할 때 펼쳐서 직접 입력합니다.</p>
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
      </details>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">누적 row 관리</h2>
            <p class="panel-sub">저장 후 현재 목록이 즉시 다시 조회됩니다.</p>
          </div>
        </div>
        <p v-if="dashboardListFilter" class="dashboard-filter-banner">{{ dashboardFilterBannerText }}</p>
        <div class="table-wrap">
          <table class="ledger-table">
            <thead>
              <tr>
                <th>No</th>
                <th>부적합 내용</th>
                <th>조치 전/후</th>
                <th>담당</th>
                <th>기한/완료</th>
                <th>사진</th>
                <th>운영 처리</th>
                <th>DB 승격</th>
                <th>저장</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in displayNcSiteItems" :key="item.id">
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
                    <input v-model="draftItems[item.id].action_owner" type="text" placeholder="담당자" />
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
                  <div class="cell-stack ops-block">
                    <div class="sub-label">접수</div>
                    <span class="mini-badge" :class="ncReceiptBadge(item)">{{ ncReceiptLabel(item) }}</span>
                    <div class="btn-row">
                      <button class="stitch-btn-secondary btn-sm" type="button" :disabled="!canNcSiteApprove(item)" @click="ncSiteApprove(item.id)">접수</button>
                      <button class="stitch-btn-secondary btn-sm danger" type="button" :disabled="!canNcSiteReject(item)" @click="ncSiteReject(item.id)">반려</button>
                    </div>
                    <p v-if="item.site_reject_note" class="reject-note">반려: {{ item.site_reject_note }}</p>
                    <div class="sub-label">조치 상태</div>
                    <select v-model="ncActionDrafts[item.id]" class="action-select">
                      <option value="not_started">미조치</option>
                      <option value="in_progress">조치중</option>
                      <option value="completed">조치완료</option>
                    </select>
                    <button class="stitch-btn-secondary btn-sm" type="button" @click="ncSaveActionStatus(item.id)">조치 저장</button>
                    <div class="sub-label">현장 메모</div>
                    <textarea v-model="ncSiteCommentDrafts[item.id]" rows="2" />
                    <button class="stitch-btn-secondary btn-sm" type="button" @click="ncSaveSiteComment(item.id)">메모 저장</button>
                  </div>
                </td>
                <td>
                  <div class="cell-stack db-block">
                    <p class="db-hint">DB 반영은 현장 요청 + 본사 승인 절차입니다.</p>
                    <span class="mini-badge db-badge">{{ ncRiskReqLabel(item) }}</span>
                    <span class="mini-badge db-badge-hq" :class="ncRiskHqBadge(item)">{{ ncRiskHqLabel(item) }}</span>
                    <button
                      class="stitch-btn-primary btn-sm"
                      type="button"
                      :disabled="!canNcRequestRiskDb(item)"
                      title="반복 위험이 있거나 타 현장 적용이 필요한 경우에만 누르세요. 접수·조치와 별개입니다."
                      @click="ncRequestRiskDb(item.id)"
                    >
                      위험성평가 DB 등록 요청
                    </button>
                  </div>
                </td>
                <td>
                  <button class="stitch-btn-primary btn-sm" type="button" @click="saveItem(item.id)">저장</button>
                </td>
              </tr>
              <tr v-if="currentItems.length === 0">
                <td colspan="9" class="empty-cell">등록된 row가 없습니다.</td>
              </tr>
              <tr v-else-if="displayNcSiteItems.length === 0">
                <td colspan="9" class="empty-cell">이 필터에 해당하는 row가 없습니다.</td>
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

    <section v-if="!isSite" class="panel">
      <div class="panel-head">
        <div>
          <h2 class="panel-title">전체 부적합 row</h2>
          <p class="panel-sub">본사는 DB 등록 요청에 대한 승인·반려와 포상 후보만 처리합니다.</p>
        </div>
      </div>
      <p v-if="dashboardListFilter" class="dashboard-filter-banner">{{ dashboardFilterBannerText }}</p>
      <div class="table-wrap">
        <table class="ledger-table hq-nc-table">
          <thead>
            <tr>
              <th>현장/대장</th>
              <th>내용</th>
              <th>접수·조치</th>
              <th>DB요청/HQ</th>
              <th>본사 메모</th>
              <th>액션</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in displayNcHqItems" :key="row.id">
              <td>{{ row.ledger_title || "-" }}</td>
              <td>{{ row.issue_text }}</td>
              <td>
                <div class="cell-stack">
                  <span>{{ ncReceiptLabel(row) }}</span>
                  <span class="text-muted">조치: {{ ncActionUi(row.action_status) }}</span>
                </div>
              </td>
              <td>
                <div class="cell-stack">
                  <span>{{ ncRiskReqLabel(row) }}</span>
                  <span class="mini-badge db-badge-hq" :class="ncRiskHqBadge(row)">{{ ncRiskHqLabel(row) }}</span>
                  <span v-if="row.ready_for_risk_db" class="text-ok">DB 승격 확정</span>
                </div>
              </td>
              <td>
                <textarea v-model="ncHqCommentDrafts[row.id]" rows="2" />
                <button class="stitch-btn-secondary btn-sm" type="button" @click="ncSaveHqComment(row.id)">저장</button>
              </td>
              <td class="action-inline hq-nc-actions">
                <button
                  class="stitch-btn-secondary btn-sm"
                  type="button"
                  :disabled="!canNcHqApproveRiskDb(row)"
                  title="현장에서 위험성평가 DB 등록 요청을 한 항목만 승인할 수 있습니다."
                  @click="ncHqApproveRiskDb(row.id)"
                >
                  DB 등록 승인
                </button>
                <button class="stitch-btn-secondary btn-sm danger" type="button" :disabled="!canNcHqRejectRiskDb(row)" @click="ncHqRejectRiskDb(row.id)">DB 등록 반려</button>
                <button class="stitch-btn-primary btn-sm" type="button" :disabled="!canNcHqReward(row)" @click="ncHqReward(row.id)">포상후보등록</button>
              </td>
            </tr>
            <tr v-if="hqRowItems.length === 0">
              <td colspan="6" class="empty-cell">등록된 row가 없습니다.</td>
            </tr>
            <tr v-else-if="displayNcHqItems.length === 0">
              <td colspan="6" class="empty-cell">이 필터에 해당하는 row가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { canPreviewInBrowser } from "@/utils/filePreview";
import { formatDateTimeKst } from "@/utils/datetime";
import {
  isLedgerDashboardFilter,
  ledgerFilterDescription,
  rowMatchesLedgerFilter,
  type LedgerDashboardFilter,
} from "@/utils/ledgerDashboardFilter";

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
  ledger_title?: string;
  issue_text: string;
  action_before?: string | null;
  action_after?: string | null;
  action_status?: string | null;
  action_due_date?: string | null;
  completed_at?: string | null;
  action_owner?: string | null;
  before_photo_url?: string | null;
  after_photo_url?: string | null;
  receipt_decision?: string | null;
  site_approved?: boolean;
  site_rejected?: boolean;
  site_reject_note?: string | null;
  site_action_comment?: string | null;
  site_comment?: string | null;
  hq_review_comment?: string | null;
  hq_comment?: string | null;
  risk_db_request_status?: string | null;
  risk_db_hq_status?: string | null;
  ready_for_risk_db?: boolean;
  hq_checked?: boolean;
  hq_final_approved?: boolean;
  reward_candidate?: boolean;
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
  action_due_date: string;
  completed_at: string;
  action_owner: string;
}

const auth = useAuthStore();
const route = useRoute();
const dashboardListFilter = ref<LedgerDashboardFilter | null>(null);

watch(
  () => route.query.filter,
  (q) => {
    const v = Array.isArray(q) ? q[0] : q;
    dashboardListFilter.value = typeof v === "string" && isLedgerDashboardFilter(v) ? v : null;
  },
  { immediate: true },
);

const dashboardFilterBannerText = computed(() => {
  const f = dashboardListFilter.value;
  return f ? `대시보드 필터: ${ledgerFilterDescription(f)} (목록에 맞는 row만 표시)` : "";
});

const ledgers = ref<LedgerRow[]>([]);
const currentLedger = ref<CurrentLedgerPayload | null>(null);
const ledgerFile = ref<File | null>(null);
const ledgerFileInput = ref<HTMLInputElement | null>(null);
const uploadingLedger = ref(false);
const savingCreate = ref(false);
const draftItems = ref<Record<number, DraftItem>>({});
const beforePhotos = ref<Record<number, File | null>>({});
const afterPhotos = ref<Record<number, File | null>>({});
const hqRowItems = ref<NonconformityItemRow[]>([]);
const ncActionDrafts = ref<Record<number, string>>({});
const ncSiteCommentDrafts = ref<Record<number, string>>({});
const ncHqCommentDrafts = ref<Record<number, string>>({});
const createDraft = ref<DraftItem>({
  issue_text: "",
  action_before: "",
  action_after: "",
  action_due_date: "",
  completed_at: "",
  action_owner: "",
});

const isSite = computed(() => auth.user?.role === "SITE");
const currentItems = computed(() => currentLedger.value?.items ?? []);
const hqRoles = computed(() => ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(auth.user?.role || ""));

const displayNcSiteItems = computed(() => {
  const list = currentItems.value;
  const f = dashboardListFilter.value;
  if (!f) return list;
  return list.filter((item) => rowMatchesLedgerFilter(item, f));
});

const displayNcHqItems = computed(() => {
  const list = hqRowItems.value;
  const f = dashboardListFilter.value;
  if (!f) return list;
  return list.filter((item) => rowMatchesLedgerFilter(item, f));
});

function emptyDraft(): DraftItem {
  return {
    issue_text: "",
    action_before: "",
    action_after: "",
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
    action_due_date: item.action_due_date || "",
    completed_at: item.completed_at || "",
    action_owner: item.action_owner || "",
  };
}

function syncDrafts(items: NonconformityItemRow[]) {
  draftItems.value = Object.fromEntries(items.map((item) => [item.id, draftFromItem(item)]));
}

function ncActionToUi(v?: string | null) {
  const x = (v || "not_started").toLowerCase();
  if (["in_progress"].includes(x)) return "in_progress";
  if (["completed", "done", "closed"].includes(x)) return "completed";
  return "not_started";
}

function syncNcOpsDrafts(items: NonconformityItemRow[]) {
  const a: Record<number, string> = {};
  const s: Record<number, string> = {};
  for (const it of items) {
    a[it.id] = ncActionToUi(it.action_status);
    s[it.id] = it.site_action_comment || it.site_comment || "";
  }
  ncActionDrafts.value = { ...ncActionDrafts.value, ...a };
  ncSiteCommentDrafts.value = { ...ncSiteCommentDrafts.value, ...s };
}

function syncNcHqCommentDrafts(items: NonconformityItemRow[]) {
  const h: Record<number, string> = {};
  for (const it of items) {
    h[it.id] = it.hq_review_comment || it.hq_comment || "";
  }
  ncHqCommentDrafts.value = { ...ncHqCommentDrafts.value, ...h };
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
    syncNcOpsDrafts(res.data.items ?? []);
    return;
  }
  const res = await api.get<{ items: LedgerRow[] }>("/safety-features/nonconformities");
  ledgers.value = res.data.items ?? [];
  const rowRes = await api.get<{ items: NonconformityItemRow[] }>("/safety-features/nonconformities/items");
  hqRowItems.value = rowRes.data.items ?? [];
  syncNcHqCommentDrafts(hqRowItems.value);
}

function buildItemForm(draft: DraftItem) {
  const form = new FormData();
  form.append("issue_text", draft.issue_text || "");
  form.append("action_before", draft.action_before || "");
  form.append("action_after", draft.action_after || "");
  form.append("action_status", "");
  form.append("action_due_date", draft.action_due_date || "");
  form.append("completed_at", draft.completed_at || "");
  form.append("action_owner", draft.action_owner || "");
  return form;
}

function ncReceiptLabel(item: NonconformityItemRow) {
  const x = (item.receipt_decision || "").toLowerCase();
  if (x === "accepted") return "접수";
  if (x === "rejected") return "반려";
  return "대기";
}

function ncReceiptBadge(item: NonconformityItemRow) {
  const x = (item.receipt_decision || "").toLowerCase();
  if (x === "rejected") return "badge-warn";
  if (x === "accepted") return "badge-slate";
  return "";
}

function ncRiskReqLabel(item: NonconformityItemRow) {
  return (item.risk_db_request_status || "").toLowerCase() === "requested" ? "요청됨" : "미요청";
}

function ncRiskHqLabel(item: NonconformityItemRow) {
  const x = (item.risk_db_hq_status || "").toLowerCase();
  if (x === "approved") return "본사 승인";
  if (x === "rejected") return "본사 반려";
  return "본사 대기";
}

function ncRiskHqBadge(item: NonconformityItemRow) {
  const x = (item.risk_db_hq_status || "").toLowerCase();
  if (x === "approved") return "badge-blue";
  if (x === "rejected") return "badge-warn";
  return "";
}

function ncActionUi(v?: string | null) {
  const u = ncActionToUi(v);
  if (u === "in_progress") return "조치중";
  if (u === "completed") return "조치완료";
  return "미조치";
}

function ncRiskDbLocked(item: NonconformityItemRow) {
  return (item.risk_db_hq_status || "").toLowerCase() === "approved" || !!item.hq_final_approved;
}

function canNcSiteApprove(item: NonconformityItemRow) {
  const rec = (item.receipt_decision || "").toLowerCase();
  return isSite.value && !ncRiskDbLocked(item) && (rec !== "accepted" || !!item.site_rejected);
}

function canNcSiteReject(item: NonconformityItemRow) {
  const rec = (item.receipt_decision || "").toLowerCase();
  return isSite.value && !ncRiskDbLocked(item) && rec !== "rejected" && !item.site_rejected;
}

function canNcRequestRiskDb(item: NonconformityItemRow) {
  return (
    isSite.value &&
    (item.receipt_decision || "").toLowerCase() === "accepted" &&
    !item.site_rejected &&
    (item.risk_db_hq_status || "").toLowerCase() !== "approved"
  );
}

function canNcHqApproveRiskDb(item: NonconformityItemRow) {
  return (
    hqRoles.value &&
    (item.receipt_decision || "").toLowerCase() === "accepted" &&
    !item.site_rejected &&
    (item.risk_db_request_status || "").toLowerCase() === "requested" &&
    (item.risk_db_hq_status || "").toLowerCase() === "pending"
  );
}

function canNcHqRejectRiskDb(item: NonconformityItemRow) {
  return (
    hqRoles.value &&
    (item.risk_db_request_status || "").toLowerCase() === "requested" &&
    (item.risk_db_hq_status || "").toLowerCase() !== "approved"
  );
}

function canNcHqReward(item: NonconformityItemRow) {
  return (
    hqRoles.value &&
    !!item.site_approved &&
    !item.site_rejected &&
    (item.risk_db_hq_status || "").toLowerCase() === "approved" &&
    !item.reward_candidate
  );
}

async function ncSiteApprove(itemId: number) {
  await api.post(`/safety-features/nonconformities/items/${itemId}/site-approve`);
  await load();
}

async function ncSiteReject(itemId: number) {
  const note = window.prompt("반려 사유(선택)") || "";
  const form = new FormData();
  form.append("reject_note", note);
  await api.post(`/safety-features/nonconformities/items/${itemId}/site-reject`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function ncSaveActionStatus(itemId: number) {
  const form = new FormData();
  form.append("action_status", ncActionDrafts.value[itemId] || "not_started");
  await api.post(`/safety-features/nonconformities/items/${itemId}/action-status`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function ncSaveSiteComment(itemId: number) {
  const form = new FormData();
  form.append("comment", ncSiteCommentDrafts.value[itemId] || "");
  await api.post(`/safety-features/nonconformities/items/${itemId}/site-action-comment`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function ncSaveHqComment(itemId: number) {
  const form = new FormData();
  form.append("comment", ncHqCommentDrafts.value[itemId] || "");
  await api.post(`/safety-features/nonconformities/items/${itemId}/hq-review-comment`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function ncRequestRiskDb(itemId: number) {
  await api.post(`/safety-features/nonconformities/items/${itemId}/request-risk-db-registration`);
  await load();
}

async function ncHqApproveRiskDb(itemId: number) {
  await api.post(`/safety-features/nonconformities/items/${itemId}/approve-risk-db-registration`);
  await load();
}

async function ncHqRejectRiskDb(itemId: number) {
  const note = window.prompt("DB 등록 반려 사유(선택)") || "";
  const form = new FormData();
  form.append("reject_note", note);
  await api.post(`/safety-features/nonconformities/items/${itemId}/reject-risk-db-registration`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function ncHqReward(itemId: number) {
  await api.post(`/safety-features/nonconformities/items/${itemId}/reward-candidate`);
  await load();
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

.manual-panel {
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: #f8fafc;
}

.manual-panel summary {
  cursor: pointer;
  list-style: none;
  padding: 14px 16px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.manual-panel summary::-webkit-details-marker {
  display: none;
}

.nested-manual {
  margin: 0 12px 12px;
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
  min-width: 1180px;
}

.hq-nc-table {
  min-width: 960px;
}

.sub-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.db-hint {
  margin: 0 0 6px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.35;
}

.ops-block .btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.db-block {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 8px;
  background: #f8fafc;
}

.db-badge {
  margin-right: 6px;
}

.action-select {
  max-width: 140px;
}

.text-muted {
  font-size: 12px;
  color: #64748b;
}

.text-ok {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #166534;
}

.dashboard-filter-banner {
  margin: 0 0 10px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  font-size: 12px;
  color: #1e40af;
}

.hq-nc-actions {
  flex-direction: row;
  flex-wrap: wrap;
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

.mini-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
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

.badge-warn {
  background: #fee2e2;
  color: #991b1b;
}

.stitch-btn-secondary.danger {
  color: #b91c1c;
}

.action-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reject-note {
  margin: 4px 0 0;
  font-size: 11px;
  color: #b91c1c;
}

.btn-sm {
  padding: 6px 10px;
  font-size: 12px;
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
