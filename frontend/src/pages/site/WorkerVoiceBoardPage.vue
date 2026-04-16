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
            <h2 class="panel-title">초기 가져오기</h2>
            <p class="panel-sub">기본 운영은 엑셀/CSV 업로드로 대장을 반영합니다. 수동 row 입력은 보조 기능입니다.</p>
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

      <details class="manual-panel">
        <summary>수동 row 추가 (보조)</summary>
        <section class="panel nested-manual">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">새 의견 row 추가</h2>
              <p class="panel-sub">업로드로 반영되지 않는 예외 건만 필요할 때 펼쳐서 입력합니다.</p>
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
      </details>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">누적 row 관리</h2>
            <p class="panel-sub">저장하면 현재 대장과 목록이 즉시 다시 조회됩니다.</p>
          </div>
        </div>
        <p v-if="dashboardListFilter" class="dashboard-filter-banner">{{ dashboardFilterBannerText }}</p>
        <div class="table-wrap">
          <table class="ledger-table">
            <thead>
              <tr>
                <th>No</th>
                <th>근로자</th>
                <th>의견</th>
                <th>조치 전/후</th>
                <th>담당</th>
                <th>사진</th>
                <th>운영 처리 (접수·조치·현장메모)</th>
                <th>위험성평가 DB (요청·본사판단)</th>
                <th>저장</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in displaySiteItems" :key="item.id">
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
                      <input v-model="drafts[item.id].action_owner" type="text" placeholder="담당자" />
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
                    <div class="cell-stack ops-block">
                      <div class="sub-label">접수 판단</div>
                      <span class="mini-badge" :class="receiptBadgeClass(item)">{{ receiptLabel(item.receipt_decision) }}</span>
                      <div class="btn-row">
                        <button class="stitch-btn-secondary btn-sm" type="button" :disabled="!canSiteApprove(item)" @click="siteApprove(item.id)">접수</button>
                        <button class="stitch-btn-secondary btn-sm danger" type="button" :disabled="!canSiteReject(item)" @click="siteReject(item.id)">반려</button>
                      </div>
                      <div class="sub-label">조치 상태</div>
                      <select v-model="actionStatusDrafts[item.id]" class="action-select">
                        <option value="not_started">미조치</option>
                        <option value="in_progress">조치중</option>
                        <option value="completed">조치완료</option>
                      </select>
                      <button class="stitch-btn-secondary btn-sm" type="button" @click="saveActionStatus(item.id)">조치 저장</button>
                      <div class="sub-label">현장 메모 (운영)</div>
                      <textarea v-model="siteCommentDrafts[item.id]" rows="2" placeholder="현장 코멘트" />
                      <button class="stitch-btn-secondary btn-sm" type="button" @click="saveSiteComment(item.id)">메모 저장</button>
                      <button class="stitch-btn-secondary btn-sm" type="button" @click="toggleComments(item.id)">이력 코멘트</button>
                    </div>
                  </td>
                  <td>
                    <div class="cell-stack db-block">
                      <p class="db-hint">접수와 별개로, DB 반영은 현장 요청 후 본사가 승인합니다.</p>
                      <div>
                        <span class="mini-badge db-badge">{{ riskDbRequestLabel(item.risk_db_request_status) }}</span>
                        <span class="mini-badge db-badge-hq" :class="riskDbHqBadgeClass(item.risk_db_hq_status)">{{ riskDbHqLabel(item.risk_db_hq_status) }}</span>
                      </div>
                      <button
                        class="stitch-btn-primary btn-sm"
                        type="button"
                        :disabled="!canRequestRiskDb(item)"
                        title="반복 위험이 있거나 타 현장 적용이 필요한 경우에만 누르세요. 접수·조치와 별개입니다."
                        @click="requestRiskDb(item.id)"
                      >
                        위험성평가 DB 등록 요청
                      </button>
                    </div>
                  </td>
                  <td>
                    <button class="stitch-btn-primary btn-sm" type="button" @click="saveSiteItem(item.id)">저장</button>
                  </td>
                </tr>
                <tr v-if="openedCommentsItemId === item.id">
                  <td colspan="9">
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
                <td colspan="9" class="empty-cell">등록된 의견 row가 없습니다.</td>
              </tr>
              <tr v-else-if="displaySiteItems.length === 0">
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
          <h2 class="panel-title">전체 의견 row</h2>
          <p class="panel-sub">본사는 위험성평가 DB 등록 요청에 대한 승인·반려와 포상 후보만 처리합니다. 접수·조치는 현장 전용입니다.</p>
        </div>
      </div>
      <p v-if="dashboardListFilter" class="dashboard-filter-banner">{{ dashboardFilterBannerText }}</p>
      <div class="table-wrap">
        <table class="ledger-table hq-table">
          <thead>
            <tr>
              <th>대장</th>
              <th>근로자</th>
              <th>의견</th>
              <th>조치</th>
              <th>접수·조치</th>
              <th>DB요청/HQ</th>
              <th>본사 메모</th>
              <th>DB·포상</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="item in displayHqItems" :key="item.id">
              <tr>
                <td>{{ item.ledger_title }}</td>
                <td>{{ item.worker_name || "-" }}</td>
                <td>{{ item.opinion_text }}</td>
                <td>{{ item.action_after || item.action_before || "-" }}</td>
                <td>
                  <div class="cell-stack">
                    <span>{{ receiptLabel(item.receipt_decision) }}</span>
                    <span class="text-muted">조치: {{ actionStatusLabelUi(item.action_status) }}</span>
                  </div>
                </td>
                <td>
                  <div class="cell-stack">
                    <span>{{ riskDbRequestLabel(item.risk_db_request_status) }}</span>
                    <span class="mini-badge db-badge-hq" :class="riskDbHqBadgeClass(item.risk_db_hq_status)">{{ riskDbHqLabel(item.risk_db_hq_status) }}</span>
                    <span v-if="item.ready_for_risk_db" class="text-ok">DB 승격 확정</span>
                  </div>
                </td>
                <td>
                  <textarea v-model="hqCommentDrafts[item.id]" rows="2" placeholder="본사 코멘트 (DB 검토 등)" />
                  <button class="stitch-btn-secondary btn-sm" type="button" @click="saveHqComment(item.id)">저장</button>
                  <button class="stitch-btn-secondary btn-sm" type="button" @click="toggleComments(item.id)">이력 코멘트</button>
                </td>
                <td class="action-inline">
                  <button
                    class="stitch-btn-secondary btn-sm"
                    type="button"
                    :disabled="!canHqApproveRiskDb(item)"
                    title="현장에서 위험성평가 DB 등록 요청을 한 항목만 승인할 수 있습니다."
                    @click="hqApproveRiskDb(item.id)"
                  >
                    DB 등록 승인
                  </button>
                  <button class="stitch-btn-secondary btn-sm danger" type="button" :disabled="!canHqRejectRiskDb(item)" @click="hqRejectRiskDb(item.id)">DB 등록 반려</button>
                  <button class="stitch-btn-primary btn-sm" type="button" :disabled="!canPromote(item)" @click="promote(item.id)">포상후보등록</button>
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
            <tr v-if="items.length === 0">
              <td colspan="8" class="empty-cell">데이터가 없습니다.</td>
            </tr>
            <tr v-else-if="displayHqItems.length === 0">
              <td colspan="8" class="empty-cell">이 필터에 해당하는 row가 없습니다.</td>
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
  receipt_decision?: string | null;
  site_approved: boolean;
  site_rejected?: boolean;
  site_reject_note?: string | null;
  site_action_comment?: string | null;
  site_comment?: string | null;
  hq_review_comment?: string | null;
  hq_comment?: string | null;
  risk_db_request_status?: string | null;
  risk_db_hq_status?: string | null;
  ready_for_risk_db?: boolean;
  hq_checked: boolean;
  hq_final_approved?: boolean;
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
const actionStatusDrafts = ref<Record<number, string>>({});
const siteCommentDrafts = ref<Record<number, string>>({});
const hqCommentDrafts = ref<Record<number, string>>({});
const createDraft = ref<DraftRow>({
  worker_name: "",
  worker_birth_date: "",
  worker_phone_number: "",
  opinion_kind: "",
  opinion_text: "",
  action_before: "",
  action_after: "",
  action_owner: "",
});

const role = computed(() => auth.user?.role ?? "");
const isSite = computed(() => role.value === "SITE");
const siteItems = computed(() => currentLedger.value?.items ?? []);

const displaySiteItems = computed(() => {
  const list = siteItems.value;
  const f = dashboardListFilter.value;
  if (!f) return list;
  return list.filter((item) => rowMatchesLedgerFilter(item, f));
});

const displayHqItems = computed(() => {
  const list = items.value;
  const f = dashboardListFilter.value;
  if (!f) return list;
  return list.filter((item) => rowMatchesLedgerFilter(item, f));
});

function emptyDraft(): DraftRow {
  return {
    worker_name: "",
    worker_birth_date: "",
    worker_phone_number: "",
    opinion_kind: "",
    opinion_text: "",
    action_before: "",
    action_after: "",
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
    action_owner: item.action_owner || "",
  };
}

function syncDrafts(list: WorkerVoiceItemRow[]) {
  drafts.value = Object.fromEntries(list.map((item) => [item.id, draftFromItem(item)]));
}

function actionStatusToUi(v?: string | null) {
  const x = (v || "not_started").toLowerCase();
  if (["in_progress"].includes(x)) return "in_progress";
  if (["completed", "done", "closed", "shared", "share_done"].includes(x)) return "completed";
  return "not_started";
}

function syncOpsDrafts(list: WorkerVoiceItemRow[]) {
  const a: Record<number, string> = {};
  const s: Record<number, string> = {};
  for (const it of list) {
    a[it.id] = actionStatusToUi(it.action_status);
    s[it.id] = it.site_action_comment || it.site_comment || "";
  }
  actionStatusDrafts.value = { ...actionStatusDrafts.value, ...a };
  siteCommentDrafts.value = { ...siteCommentDrafts.value, ...s };
}

function syncHqCommentDrafts(list: WorkerVoiceItemRow[]) {
  const h: Record<number, string> = {};
  for (const it of list) {
    h[it.id] = it.hq_review_comment || it.hq_comment || "";
  }
  hqCommentDrafts.value = { ...hqCommentDrafts.value, ...h };
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

function receiptLabel(v?: string | null) {
  const x = (v || "").toLowerCase();
  if (x === "accepted") return "접수";
  if (x === "rejected") return "반려";
  return "대기";
}

function receiptBadgeClass(item: WorkerVoiceItemRow) {
  const x = (item.receipt_decision || "").toLowerCase();
  if (x === "rejected") return "badge-warn";
  if (x === "accepted") return "badge-slate";
  return "";
}

function actionStatusLabelUi(v?: string | null) {
  const u = actionStatusToUi(v);
  if (u === "in_progress") return "조치중";
  if (u === "completed") return "조치완료";
  return "미조치";
}

function riskDbRequestLabel(v?: string | null) {
  return (v || "").toLowerCase() === "requested" ? "요청됨" : "미요청";
}

function riskDbHqLabel(v?: string | null) {
  const x = (v || "").toLowerCase();
  if (x === "approved") return "본사 승인";
  if (x === "rejected") return "본사 반려";
  return "본사 대기";
}

function riskDbHqBadgeClass(v?: string | null) {
  const x = (v || "").toLowerCase();
  if (x === "approved") return "badge-blue";
  if (x === "rejected") return "badge-warn";
  return "";
}

function sourceLabel(sourceType?: string) {
  return sourceType === "IMPORT" ? "초기 가져오기 대장" : "수기 관리 대장";
}

function riskDbHqLocked(item: WorkerVoiceItemRow) {
  return (item.risk_db_hq_status || "").toLowerCase() === "approved" || !!item.hq_final_approved;
}

function canSiteApprove(item: WorkerVoiceItemRow) {
  const rec = (item.receipt_decision || "").toLowerCase();
  return role.value === "SITE" && !riskDbHqLocked(item) && (rec !== "accepted" || !!item.site_rejected);
}

function canSiteReject(item: WorkerVoiceItemRow) {
  const rec = (item.receipt_decision || "").toLowerCase();
  return role.value === "SITE" && !riskDbHqLocked(item) && rec !== "rejected" && !item.site_rejected;
}

function canRequestRiskDb(item: WorkerVoiceItemRow) {
  return (
    role.value === "SITE" &&
    (item.receipt_decision || "").toLowerCase() === "accepted" &&
    !item.site_rejected &&
    (item.risk_db_hq_status || "").toLowerCase() !== "approved"
  );
}

function canHqApproveRiskDb(item: WorkerVoiceItemRow) {
  return (
    ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) &&
    (item.receipt_decision || "").toLowerCase() === "accepted" &&
    !item.site_rejected &&
    (item.risk_db_request_status || "").toLowerCase() === "requested" &&
    (item.risk_db_hq_status || "").toLowerCase() === "pending"
  );
}

function canHqRejectRiskDb(item: WorkerVoiceItemRow) {
  return (
    ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) &&
    (item.risk_db_request_status || "").toLowerCase() === "requested" &&
    (item.risk_db_hq_status || "").toLowerCase() !== "approved"
  );
}

function canPromote(item: WorkerVoiceItemRow) {
  return (
    ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) &&
    item.site_approved &&
    !item.site_rejected &&
    (item.risk_db_hq_status || "").toLowerCase() === "approved" &&
    !item.reward_candidate
  );
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
    syncOpsDrafts(items.value);
    return;
  }
  const res = await api.get<{ items: WorkerVoiceItemRow[] }>("/safety-features/worker-voice/items");
  items.value = res.data.items ?? [];
  syncHqCommentDrafts(items.value);
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
  form.append("action_status", "");
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

async function siteReject(itemId: number) {
  const note = window.prompt("반려 사유(선택)") || "";
  const form = new FormData();
  form.append("reject_note", note);
  await api.post(`/safety-features/worker-voice/items/${itemId}/site-reject`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function saveActionStatus(itemId: number) {
  const form = new FormData();
  form.append("action_status", actionStatusDrafts.value[itemId] || "not_started");
  await api.post(`/safety-features/worker-voice/items/${itemId}/action-status`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function saveSiteComment(itemId: number) {
  const form = new FormData();
  form.append("comment", siteCommentDrafts.value[itemId] || "");
  await api.post(`/safety-features/worker-voice/items/${itemId}/site-action-comment`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function saveHqComment(itemId: number) {
  const form = new FormData();
  form.append("comment", hqCommentDrafts.value[itemId] || "");
  await api.post(`/safety-features/worker-voice/items/${itemId}/hq-review-comment`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  await load();
}

async function requestRiskDb(itemId: number) {
  await api.post(`/safety-features/worker-voice/items/${itemId}/request-risk-db-registration`);
  await load();
}

async function hqApproveRiskDb(itemId: number) {
  await api.post(`/safety-features/worker-voice/items/${itemId}/approve-risk-db-registration`);
  await load();
}

async function hqRejectRiskDb(itemId: number) {
  const note = window.prompt("DB 등록 반려 사유(선택)") || "";
  const form = new FormData();
  form.append("reject_note", note);
  await api.post(`/safety-features/worker-voice/items/${itemId}/reject-risk-db-registration`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
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
  min-width: 1180px;
}

.hq-table {
  min-width: 1100px;
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

.hq-table .action-inline {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8px;
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

.badge-warn {
  background: #fee2e2;
  color: #991b1b;
}

.stitch-btn-secondary.danger {
  color: #b91c1c;
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
