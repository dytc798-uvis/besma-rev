<template>
  <div class="card">
    <div class="header-row">
      <div>
        <div class="card-title">현장 문서취합 (Requirement 기반)</div>
        <p class="page-note">기준일 {{ targetDate }} 기준으로 지금 처리할 문서와 반려 재조치 문서를 분리해서 보여줍니다.</p>
      </div>
      <div class="controls">
        <button class="secondary" @click="confirmDocComments">문서 코멘트 확인</button>
        <button class="secondary" @click="load">새로고침</button>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-label">현재 작업 문서</div>
        <div class="summary-value">{{ currentTaskItems.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">제출대기</div>
        <div class="summary-value">{{ pendingCurrentCount }}</div>
      </div>
      <div class="summary-card summary-card-alert">
        <div class="summary-label">재조치 필요</div>
        <div class="summary-value">{{ reworkItems.length }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">승인</div>
        <div class="summary-value">{{ approvedCount }}</div>
      </div>
    </div>

    <section class="section-card">
      <div class="section-head">
        <h3>현재 작업 문서</h3>
        <p>오늘/이번주/이번달 기준으로 지금 제출해야 하는 문서만 모았습니다.</p>
      </div>
      <table class="basic-table">
        <thead>
          <tr>
            <th>문서명</th>
            <th>대상 주기</th>
            <th>상태</th>
            <th>최근 제출</th>
            <th>메모</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="currentTaskItems.length === 0">
            <tr>
              <td colspan="6" class="empty-cell">현재 처리할 문서가 없습니다.</td>
            </tr>
          </template>
          <template v-else>
            <template v-for="grp in currentTaskGroups" :key="grp.key">
              <tr class="freq-group-row">
                <td colspan="6" class="freq-group-cell">{{ grp.label }}</td>
              </tr>
              <tr v-for="item in grp.items" :key="`current-${item.requirement_id}`">
            <td>
              <div class="cell-title">{{ item.title }}</div>
              <div class="cell-subtitle">{{ sectionLabel(item.section) }}</div>
              <div v-if="isLedgerManagedRequirement(item)" class="ledger-ref-badge">관리대장 전용 · 문서취합은 참조</div>
            </td>
            <td>{{ item.current_period_label || frequencyLabel(item.frequency) }}</td>
            <td>
              <span class="badge status-badge" :class="[statusClass(item.current_cycle_status || 'NOT_SUBMITTED'), currentStatusClass(item.current_cycle_status)]">
                <span class="status-dot" aria-hidden="true">{{ currentStatusIcon(item.current_cycle_status) }}</span>
                {{ currentStatusLabel(item.current_cycle_status) }}
              </span>
            </td>
            <td>{{ formatDateTime(item.current_cycle_uploaded_at) }}</td>
            <td class="note-cell">
              <span v-if="item.current_cycle_needs_reupload" class="inline-alert">
                직전 제출본이 반려되어 다시 업로드해야 합니다.
              </span>
              <span v-else>{{ item.due_rule_text || "-" }}</span>
            </td>
            <td class="actions">
              <button
                v-if="!isLedgerManagedRequirement(item)"
                class="secondary"
                :disabled="item.section === 'COMPLETION' && !completionUploadEnabled"
                @click="openUpload(item)"
              >
                {{ item.current_cycle_needs_reupload ? "수정 업로드" : "업로드" }}
              </button>
              <button
                v-if="item.current_cycle_document_id && item.current_cycle_file_name"
                class="secondary"
                @click="openDocumentFile(item.current_cycle_document_id, item.current_cycle_file_name)"
              >
                보기
              </button>
              <button
                v-if="canReplaceCurrentDocument(item)"
                class="secondary"
                @click="openReplace(item)"
              >
                수정
              </button>
              <button v-if="!isLedgerManagedRequirement(item)" class="secondary" @click="openHistory(item)">이력 보기</button>
              <button v-else type="button" class="secondary ledger-nav-btn" @click="goLedgerPage(item)">관리대장에서 보기</button>
            </td>
              </tr>
            </template>
          </template>
        </tbody>
      </table>
    </section>

    <section class="section-card section-card-alert">
      <div class="section-head">
        <h3>재조치 필요 문서</h3>
        <p>과거 제출본 중 반려 또는 보완 요청이 남아 있는 문서를 따로 모았습니다.</p>
      </div>
      <table class="basic-table">
        <thead>
          <tr>
            <th>문서명</th>
            <th>대상 주기</th>
            <th>코멘트</th>
            <th>반려 시각</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="reworkItems.length === 0">
            <tr>
              <td colspan="5" class="empty-cell">현재 재조치가 필요한 문서는 없습니다.</td>
            </tr>
          </template>
          <template v-else>
            <template v-for="grp in reworkGroups" :key="grp.key">
              <tr class="freq-group-row">
                <td colspan="5" class="freq-group-cell">{{ grp.label }}</td>
              </tr>
              <tr v-for="item in grp.items" :key="`rework-${item.requirement_id}-${item.unresolved_rejected_document_id}`">
            <td>
              <div class="cell-title">{{ item.title }}</div>
              <div class="cell-subtitle">{{ sectionLabel(item.section) }}</div>
              <div v-if="isLedgerManagedRequirement(item)" class="ledger-ref-badge">관리대장 전용 · 문서취합은 참조</div>
              <div class="rework-meta">
                <span class="badge status-badge status-rejected-strong">반려</span>
                <span v-if="firstRejectedBacklog(item)?.review_note || item.unresolved_rejected_review_note" class="rework-note-inline">
                  {{ firstRejectedBacklog(item)?.review_note || item.unresolved_rejected_review_note }}
                </span>
              </div>
            </td>
            <td>{{ firstRejectedBacklog(item)?.period_label || item.current_period_label || "-" }}</td>
            <td class="note-cell note-cell-alert">{{ firstRejectedBacklog(item)?.review_note || item.unresolved_rejected_review_note || "코멘트 없음" }}</td>
            <td>{{ formatDateTime(firstRejectedBacklog(item)?.reviewed_at || item.unresolved_rejected_reviewed_at || firstRejectedBacklog(item)?.uploaded_at || item.unresolved_rejected_uploaded_at) }}</td>
            <td class="actions">
              <button
                v-if="!isLedgerManagedRequirement(item)"
                class="secondary danger"
                :disabled="item.section === 'COMPLETION' && !completionUploadEnabled"
                @click="openUpload(item)"
              >
                수정 업로드
              </button>
              <button
                v-if="item.unresolved_rejected_document_id && item.unresolved_rejected_file_name"
                class="secondary"
                @click="openDocumentFile(item.unresolved_rejected_document_id, item.unresolved_rejected_file_name)"
              >
                보기
              </button>
              <button v-if="!isLedgerManagedRequirement(item)" class="secondary" @click="openHistory(item)">이력 보기</button>
              <button v-else type="button" class="secondary ledger-nav-btn" @click="goLedgerPage(item)">관리대장에서 보기</button>
            </td>
              </tr>
            </template>
          </template>
        </tbody>
      </table>
    </section>

    <section class="section-card">
      <div class="section-head">
        <h3>주기/기타 문서</h3>
        <p>반기·분기·연간 등 메인 작업보다 우선순위가 낮은 문서를 분리해서 보여줍니다.</p>
      </div>
      <table class="basic-table">
        <thead>
          <tr>
            <th>문서명</th>
            <th>대상 주기</th>
            <th>주기</th>
            <th>상태</th>
            <th>최근 제출</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="periodicItems.length === 0">
            <tr>
              <td colspan="6" class="empty-cell">표시할 주기 문서가 없습니다.</td>
            </tr>
          </template>
          <template v-else>
            <template v-for="grp in periodicGroups" :key="grp.key">
              <tr class="freq-group-row">
                <td colspan="6" class="freq-group-cell">{{ grp.label }}</td>
              </tr>
              <tr v-for="item in grp.items" :key="`periodic-${item.requirement_id}`">
            <td>
              <div class="cell-title">{{ item.title }}</div>
              <div class="cell-subtitle">{{ sectionLabel(item.section) }}</div>
              <div v-if="isLedgerManagedRequirement(item)" class="ledger-ref-badge">관리대장 전용 · 문서취합은 참조</div>
            </td>
            <td>{{ item.current_period_label || frequencyLabel(item.frequency) }}</td>
            <td>{{ frequencyLabel(item.frequency) }}</td>
            <td>
              <span class="badge status-badge" :class="[statusClass(item.current_cycle_status || 'NOT_SUBMITTED'), currentStatusClass(item.current_cycle_status)]">
                <span class="status-dot" aria-hidden="true">{{ currentStatusIcon(item.current_cycle_status) }}</span>
                {{ currentStatusLabel(item.current_cycle_status) }}
              </span>
            </td>
            <td>{{ formatDateTime(item.current_cycle_uploaded_at) }}</td>
            <td class="actions">
              <button
                v-if="!isLedgerManagedRequirement(item)"
                class="secondary"
                :disabled="item.section === 'COMPLETION' && !completionUploadEnabled"
                @click="openUpload(item)"
              >
                {{ item.current_cycle_needs_reupload ? "수정 업로드" : "업로드" }}
              </button>
              <button
                v-if="item.current_cycle_document_id && item.current_cycle_file_name"
                class="secondary"
                @click="openDocumentFile(item.current_cycle_document_id, item.current_cycle_file_name)"
              >
                보기
              </button>
              <button
                v-if="canReplaceCurrentDocument(item)"
                class="secondary"
                @click="openReplace(item)"
              >
                수정
              </button>
              <button v-if="!isLedgerManagedRequirement(item)" class="secondary" @click="openHistory(item)">이력 보기</button>
              <button v-else type="button" class="secondary ledger-nav-btn" @click="goLedgerPage(item)">관리대장에서 보기</button>
            </td>
              </tr>
            </template>
          </template>
        </tbody>
      </table>
    </section>
  </div>

  <div v-if="uploadTarget" class="modal-backdrop" @click.self="closeUpload">
    <div class="modal-card">
      <div class="card-title">
        {{
          uploadMode === "replace"
            ? "문서 수정"
            : uploadTarget.current_cycle_needs_reupload || uploadTarget.unresolved_rejected_document_id
              ? "문서 수정 업로드"
              : "문서 업로드"
        }}
      </div>
      <p class="upload-title">{{ uploadTarget.title }}</p>
      <p class="upload-note">
        Req ID: {{ uploadTarget.requirement_id }} · {{ sectionLabel(uploadTarget.section) }} ·
        {{ uploadTarget.current_period_label || frequencyLabel(uploadTarget.frequency) }}
      </p>
      <p v-if="uploadRejectReason(uploadTarget)" class="upload-reject-note">
        코멘트: {{ uploadRejectReason(uploadTarget) }}
      </p>
      <input type="file" @change="onFileChange" />
      <p class="upload-help">이미지 업로드 시 서버에서 자동 최적화되며, 제출용 PDF로 변환될 수 있습니다.</p>
      <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>
      <div class="modal-actions">
        <button class="secondary" @click="closeUpload">취소</button>
        <button class="primary" :disabled="!selectedFile || uploading" @click="submitUpload">
          {{
            uploading
              ? "업로드 중..."
              : uploadMode === "replace"
                ? "수정 완료"
                : uploadTarget.current_cycle_needs_reupload || uploadTarget.unresolved_rejected_document_id
                  ? "수정 업로드"
                  : "업로드"
          }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="historyTarget" class="modal-backdrop" @click.self="closeHistory">
    <div class="modal-card history-card">
      <div class="card-title">문서 이력 - {{ historyTarget.title }}</div>
      <p class="history-note">현재 주기: {{ historyTarget.current_period_label || frequencyLabel(historyTarget.frequency) }}</p>
      <table class="basic-table">
        <thead>
          <tr>
            <th>대상 주기</th>
            <th>상태</th>
            <th>업로드</th>
            <th>검토</th>
            <th>파일</th>
            <th>코멘트</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in historyItems"
            :key="row.history_id"
            role="button"
            tabindex="0"
            class="history-row"
            :class="{
              'history-current-row': isCurrentCycleHistory(row),
              'history-row-selected': historyFocusedDocumentId === row.document_id,
            }"
            @click="selectHistoryRow(row)"
            @keydown.enter.prevent="selectHistoryRow(row)"
          >
            <td>
              <div>{{ row.period_label || "-" }}</div>
              <div v-if="isCurrentCycleHistory(row)" class="history-current-label">현재 대상</div>
            </td>
            <td>
              <span class="badge" :class="statusClass(row.status)">
                {{ historyStatusLabel(row.status) }}
              </span>
            </td>
            <td>{{ formatDateTime(row.uploaded_at) }}</td>
            <td>{{ row.reviewed_at ? formatDateTime(row.reviewed_at) : "-" }}</td>
            <td>{{ row.file_name || "파일 없음" }}</td>
            <td class="note-cell">
              <span v-if="row.status === 'REJECTED'" class="inline-alert">{{ row.review_note || "코멘트 없음" }}</span>
              <span v-else>{{ row.review_note || "-" }}</span>
            </td>
            <td class="actions">
              <button
                v-if="row.history_file_available || row.document_id"
                type="button"
                class="secondary"
                @click.stop="openHistoryRowFile(row)"
              >
                파일 보기
              </button>
            </td>
          </tr>
          <tr v-if="historyItems.length === 0">
            <td colspan="7" class="empty-cell">이력이 없습니다.</td>
          </tr>
        </tbody>
      </table>
      <DocumentCommentsPanel
        v-if="historyCommentDocumentId && historyTarget && !isLedgerManagedRequirement(historyTarget)"
        :document-id="historyCommentDocumentId"
        :document-type-code="historyTarget.document_type_code"
        :title="historyFocusedDocumentId != null ? '선택 회차 문서 코멘트' : '현재 문서 코멘트'"
      />
      <div class="modal-actions">
        <button class="secondary" @click="closeHistory">닫기</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import DocumentCommentsPanel from "@/components/documents/DocumentCommentsPanel.vue";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst, todayKst, toDate } from "@/utils/datetime";
import { isLedgerManagedDocumentType, siteLedgerRouteForDocumentType } from "@/utils/ledgerManagedDocument";
import { markDocCommentTickerAck } from "@/utils/documentCommentTickerRead";
import { requirementFrequencyKoLabel, requirementFrequencySortOrder } from "@/utils/requirementFrequencyGroups";

interface RequirementStatusItem {
  requirement_id: number;
  document_type_code: string;
  title: string;
  frequency: string;
  is_required: boolean;
  status: string;
  latest_document_id: number | null;
  latest_uploaded_at: string | null;
  review_note: string | null;
  category: string | null;
  section: string | null;
  due_rule_text: string | null;
  completion_upload_enabled: boolean;
  current_cycle_status: string | null;
  current_cycle_document_id: number | null;
  current_cycle_instance_id: number | null;
  current_cycle_uploaded_at: string | null;
  current_cycle_review_note: string | null;
  current_cycle_file_name: string | null;
  current_cycle_file_download_url: string | null;
  current_cycle_start: string | null;
  current_cycle_end: string | null;
  current_cycle_target: boolean;
  current_period_label: string | null;
  site_display_bucket: string | null;
  current_cycle_needs_reupload: boolean;
  current_cycle_last_submission_status: string | null;
  unresolved_rejected_document_id: number | null;
  unresolved_rejected_instance_id: number | null;
  unresolved_rejected_uploaded_at: string | null;
  unresolved_rejected_reviewed_at: string | null;
  unresolved_rejected_review_note: string | null;
  unresolved_rejected_file_name: string | null;
  unresolved_rejected_file_download_url: string | null;
  unresolved_rejected_cycle_start: string | null;
  unresolved_rejected_cycle_end: string | null;
  rejected_backlog_count: number;
  rejected_backlog_items: Array<{
    document_id: number;
    instance_id: number | null;
    period_start: string | null;
    period_end: string | null;
    period_label: string | null;
    uploaded_at: string | null;
    reviewed_at: string | null;
    review_note: string | null;
    file_name: string | null;
    file_download_url: string | null;
  }>;
}

interface HistoryItem {
  history_id: number;
  document_id: number;
  instance_id: number | null;
  version_no: number;
  action_type: string;
  status: string;
  uploaded_at: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  file_name: string | null;
  file_download_url: string | null;
  period_start: string | null;
  period_end: string | null;
  period_label: string | null;
  history_file_available: boolean;
}

const auth = useAuthStore();
const router = useRouter();

function isLedgerManagedRequirement(item: RequirementStatusItem) {
  return isLedgerManagedDocumentType(item.document_type_code);
}

function goLedgerPage(item: RequirementStatusItem) {
  const name = siteLedgerRouteForDocumentType(item.document_type_code);
  if (name) void router.push({ name });
}

const targetDate = ref(todayKst());
const items = ref<RequirementStatusItem[]>([]);
const completionUploadEnabled = ref(false);

const uploadTarget = ref<RequirementStatusItem | null>(null);
const uploadMode = ref<"upload" | "replace">("upload");
const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const uploadError = ref("");
const historyTarget = ref<RequirementStatusItem | null>(null);
const historyItems = ref<HistoryItem[]>([]);
/** 이력 모달에서 선택한 회차의 문서 ID — 코멘트 패널·강조 표시에 사용 */
const historyFocusedDocumentId = ref<number | null>(null);

const siteId = computed(() => auth.effectiveSiteId ?? auth.user?.site_id ?? null);
const historyCommentDocumentId = computed(() => {
  if (historyFocusedDocumentId.value != null) return historyFocusedDocumentId.value;
  return (
    historyTarget.value?.current_cycle_document_id ?? historyTarget.value?.unresolved_rejected_document_id ?? null
  );
});

const visibleItems = computed(() =>
  items.value.filter((item) => isDisplayableRequirementId(item.requirement_id) && item.is_required && item.current_cycle_status !== "NOT_REQUIRED"),
);

const currentTaskItems = computed(() =>
  [...visibleItems.value]
    .filter((item) => item.site_display_bucket === "CURRENT_TASK")
    .sort(compareByCurrentPriority),
);

const reworkItems = computed(() =>
  [...visibleItems.value]
    .filter((item) => (item.rejected_backlog_count || 0) > 0)
    .sort((a, b) => compareDateDesc(a.unresolved_rejected_uploaded_at, b.unresolved_rejected_uploaded_at) || a.requirement_id - b.requirement_id),
);

const periodicItems = computed(() =>
  [...visibleItems.value]
    .filter((item) => item.site_display_bucket === "PERIODIC_OTHER")
    .sort(compareByCurrentPriority),
);

function groupItemsByFrequency(
  items: RequirementStatusItem[],
  innerSort?: (a: RequirementStatusItem, b: RequirementStatusItem) => number,
): { key: string; label: string; items: RequirementStatusItem[] }[] {
  if (!items.length) return [];
  const sorted = [...items].sort((a, b) => {
    const oa = requirementFrequencySortOrder(a.frequency);
    const ob = requirementFrequencySortOrder(b.frequency);
    if (oa !== ob) return oa - ob;
    if (innerSort) return innerSort(a, b);
    return (a.title || "").localeCompare(b.title || "", "ko");
  });
  const groups: { key: string; label: string; items: RequirementStatusItem[] }[] = [];
  for (const item of sorted) {
    const label = requirementFrequencyKoLabel(item.frequency);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(item);
    else groups.push({ key: `${label}-${item.requirement_id}`, label, items: [item] });
  }
  return groups;
}

function reworkInnerSort(a: RequirementStatusItem, b: RequirementStatusItem) {
  return compareDateDesc(a.unresolved_rejected_uploaded_at, b.unresolved_rejected_uploaded_at) || a.requirement_id - b.requirement_id;
}

const currentTaskGroups = computed(() => groupItemsByFrequency(currentTaskItems.value, compareByCurrentPriority));
const reworkGroups = computed(() => groupItemsByFrequency(reworkItems.value, reworkInnerSort));
const periodicGroups = computed(() => groupItemsByFrequency(periodicItems.value, compareByCurrentPriority));

const pendingCurrentCount = computed(() => currentTaskItems.value.filter((item) => item.current_cycle_status === "NOT_SUBMITTED").length);
const approvedCount = computed(() => visibleItems.value.filter((item) => item.current_cycle_status === "APPROVED").length);

function compareDateDesc(a: string | null, b: string | null) {
  const aTime = toDate(a)?.getTime() ?? 0;
  const bTime = toDate(b)?.getTime() ?? 0;
  return bTime - aTime;
}

function compareByCurrentPriority(a: RequirementStatusItem, b: RequirementStatusItem) {
  const statusPriority: Record<string, number> = {
    NOT_SUBMITTED: 0,
    IN_REVIEW: 1,
    SUBMITTED: 2,
    APPROVED: 3,
    NOT_REQUIRED: 9,
  };
  const pa = statusPriority[a.current_cycle_status || "NOT_SUBMITTED"] ?? 5;
  const pb = statusPriority[b.current_cycle_status || "NOT_SUBMITTED"] ?? 5;
  if (pa !== pb) return pa - pb;
  const dateGap = compareDateDesc(a.current_cycle_uploaded_at, b.current_cycle_uploaded_at);
  if (dateGap !== 0) return dateGap;
  return a.requirement_id - b.requirement_id;
}

function currentStatusLabel(status: string | null | undefined) {
  const map: Record<string, string> = {
    NOT_REQUIRED: "비대상",
    NOT_SUBMITTED: "제출대기",
    SUBMITTED: "제출완료",
    IN_REVIEW: "검토중",
    APPROVED: "승인",
    REJECTED: "반려",
  };
  return map[status || ""] ?? status ?? "-";
}

function currentStatusClass(status: string | null | undefined) {
  const map: Record<string, string> = {
    NOT_SUBMITTED: "status-pending",
    SUBMITTED: "status-submitted",
    IN_REVIEW: "status-reviewing",
    APPROVED: "status-approved",
  };
  return map[status || ""] ?? "";
}

function currentStatusIcon(status: string | null | undefined) {
  const map: Record<string, string> = {
    NOT_SUBMITTED: "🔴",
    SUBMITTED: "🟡",
    IN_REVIEW: "🔵",
    APPROVED: "🟢",
  };
  return map[status || ""] ?? "";
}

function historyStatusLabel(status: string) {
  const map: Record<string, string> = {
    SUBMITTED: "제출완료",
    IN_REVIEW: "검토중",
    APPROVED: "승인",
    REJECTED: "반려",
  };
  return map[status] ?? status;
}

function categoryLabel(category: string | null | undefined) {
  const map: Record<string, string> = {
    MOEL_GENERAL: "노동부 일반",
    MOEL_SAFETY: "노동부 안전",
    MIDDLE_LAW: "중처법",
    INTERNAL_RULE: "사규",
    GENERAL: "일반",
  };
  if (!category) return "-";
  return map[category] ?? category;
}

function firstRejectedBacklog(item: RequirementStatusItem) {
  return item.rejected_backlog_items?.[0] ?? null;
}

function sectionLabel(section: string | null | undefined) {
  if (section === "COMPLETION") return "준공서류";
  return "법적 서류";
}

function frequencyLabel(frequency: string | null | undefined) {
  return requirementFrequencyKoLabel(frequency);
}

function statusClass(status: string) {
  if (status === "NOT_SUBMITTED") return "badge-status-DRAFT";
  if (status === "IN_REVIEW") return "badge-status-UNDER_REVIEW";
  return `badge-status-${status}`;
}

function isDisplayableRequirementId(requirementId: unknown) {
  if (typeof requirementId !== "number") return false;
  if (!Number.isFinite(requirementId)) return false;
  return requirementId > 0;
}

function formatDateTime(value: string | null) {
  return formatDateTimeKst(value, "-");
}

function uploadRejectReason(item: RequirementStatusItem) {
  return firstRejectedBacklog(item)?.review_note || item.unresolved_rejected_review_note || item.current_cycle_review_note || item.review_note || null;
}

function canPreviewInBrowser(fileName: string | null) {
  const ext = (fileName || "").split(".").pop()?.toLowerCase() || "";
  return ["pdf", "png", "jpg", "jpeg", "gif", "webp", "txt"].includes(ext);
}

async function openBlobFile(path: string, fileName: string | null) {
  const previewable = canPreviewInBrowser(fileName);
  const res = await api.get(path, {
    params: { disposition: previewable ? "inline" : "attachment" },
    responseType: "blob",
  });
  const contentType = (res.headers["content-type"] as string | undefined) || "application/octet-stream";
  const blob = new Blob([res.data], { type: contentType });
  if (!previewable) {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName || "document.bin";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    return;
  }
  const url = window.URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => window.URL.revokeObjectURL(url), 5000);
}

async function openDocumentFile(documentId: number, fileName: string | null) {
  await openBlobFile(`/documents/${documentId}/file`, fileName);
}

async function openHistoryFile(path: string, fileName: string | null) {
  await openBlobFile(path, fileName);
}

function selectHistoryRow(row: HistoryItem) {
  historyFocusedDocumentId.value = row.document_id ?? null;
}

async function openHistoryRowFile(row: HistoryItem) {
  if (row.history_file_available && row.file_download_url && row.file_name) {
    await openHistoryFile(row.file_download_url, row.file_name);
    return;
  }
  if (row.document_id) {
    await openDocumentFile(row.document_id, row.file_name || "document.bin");
  }
}

async function load() {
  if (!siteId.value) return;
  const res = await api.get("/documents/requirements/status", {
    params: {
      site_id: siteId.value,
      period: "all",
      date: targetDate.value,
    },
  });
  items.value = res.data.items;
  completionUploadEnabled.value = !!res.data.completion_upload_enabled;
}

function openUpload(item: RequirementStatusItem) {
  if (isLedgerManagedRequirement(item)) return;
  uploadMode.value = "upload";
  uploadTarget.value = item;
  selectedFile.value = null;
  uploadError.value = "";
}

function openReplace(item: RequirementStatusItem) {
  if (isLedgerManagedRequirement(item)) return;
  if (!canReplaceCurrentDocument(item)) return;
  uploadMode.value = "replace";
  uploadTarget.value = item;
  selectedFile.value = null;
  uploadError.value = "";
}

function closeUpload() {
  uploadMode.value = "upload";
  uploadTarget.value = null;
  selectedFile.value = null;
  uploadError.value = "";
}

async function openHistory(item: RequirementStatusItem) {
  if (isLedgerManagedRequirement(item)) return;
  if (!siteId.value) return;
  historyTarget.value = item;
  historyFocusedDocumentId.value = null;
  const res = await api.get("/documents/history", {
    params: {
      site_id: siteId.value,
      requirement_id: item.requirement_id,
    },
  });
  historyItems.value = res.data.items;
}

function closeHistory() {
  historyTarget.value = null;
  historyItems.value = [];
  historyFocusedDocumentId.value = null;
}

function isCurrentCycleHistory(row: HistoryItem) {
  if (!historyTarget.value) return false;
  return !!historyTarget.value.current_cycle_instance_id && !!row.instance_id && historyTarget.value.current_cycle_instance_id === row.instance_id;
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
}

function reuploadInstanceId(item: RequirementStatusItem | null) {
  if (!item) return null;
  return item.unresolved_rejected_instance_id || item.current_cycle_instance_id || null;
}

function canReplaceCurrentDocument(item: RequirementStatusItem) {
  if (isLedgerManagedRequirement(item)) return false;
  if (!item.current_cycle_document_id || !item.current_cycle_instance_id) return false;
  const status = (item.current_cycle_status || "").toUpperCase();
  return status === "SUBMITTED" || status === "IN_REVIEW";
}

async function submitUpload() {
  if (!uploadTarget.value || !selectedFile.value || !siteId.value) return;
  if (uploadTarget.value.section === "COMPLETION" && !completionUploadEnabled.value) return;
  uploading.value = true;
  uploadError.value = "";
  try {
    const form = new FormData();
    form.append("file", selectedFile.value);
    if (uploadMode.value === "replace") {
      form.append("instance_id", String(uploadTarget.value.current_cycle_instance_id));
      await api.post("/document-submissions/replace", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    } else {
      const targetInstanceId = reuploadInstanceId(uploadTarget.value);
      if (targetInstanceId) {
        form.append("instance_id", String(targetInstanceId));
      }
      form.append("site_id", String(siteId.value));
      form.append("requirement_id", String(uploadTarget.value.requirement_id));
      form.append("document_type_code", uploadTarget.value.document_type_code);
      form.append("work_date", targetDate.value);
      await api.post("/document-submissions/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    }
    closeUpload();
    await load();
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    uploadError.value = detail || "업로드에 실패했습니다. 잠시 후 다시 시도해주세요.";
  } finally {
    uploading.value = false;
  }
}

function confirmDocComments() {
  markDocCommentTickerAck(auth.user?.login_id ?? null);
}

onMounted(async () => {
  if (auth.token) {
    await auth.loadMe();
  }
  await load();
});
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.page-note { margin: 6px 0 0; font-size: 12px; color: #64748b; }
.controls { display: flex; gap: 8px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
.summary-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
.summary-card-alert { background: #fff7ed; border-color: #fdba74; }
.summary-label { font-size: 12px; color: #64748b; }
.summary-value { margin-top: 6px; font-size: 24px; font-weight: 700; color: #0f172a; }
.section-card { margin-top: 12px; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; background: #fff; }
.section-card-alert { border-color: #fecaca; background: #fffafa; }
.section-head h3 { margin: 0; font-size: 15px; }
.section-head p { margin: 4px 0 10px; color: #475569; font-size: 12px; }
.cell-title { font-weight: 600; color: #0f172a; }
.cell-subtitle { margin-top: 4px; font-size: 12px; color: #64748b; }
.rework-meta { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; margin-top: 8px; }
.rework-note-inline { font-size: 12px; color: #9a3412; }
.note-cell { max-width: 320px; white-space: pre-wrap; word-break: break-word; color: #334155; }
.note-cell-alert { color: #991b1b; font-weight: 600; }
.inline-alert { display: inline-block; color: #b91c1c; font-weight: 700; }
.status-badge { display: inline-flex; align-items: center; gap: 4px; font-weight: 700; }
.status-dot { line-height: 1; }
.status-pending { background: #fef2f2; color: #b91c1c; border-color: #fca5a5; }
.status-submitted { background: #fefce8; color: #a16207; border-color: #fcd34d; }
.status-reviewing { background: #eff6ff; color: #1d4ed8; border-color: #93c5fd; }
.status-approved { background: #ecfdf5; color: #15803d; border-color: #86efac; }
.status-rejected-strong { background: linear-gradient(135deg, #fff7ed, #fee2e2); color: #c2410c; border-color: #fb923c; }
.empty-cell { text-align: center; color: #6b7280; }
.freq-group-cell {
  background: #e0f2fe;
  color: #0c4a6e;
  font-weight: 700;
  font-size: 13px;
  padding: 8px 10px;
  border-bottom: 1px solid #bae6fd;
}
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
.secondary.danger { border-color: #ef4444; color: #b91c1c; background: #fef2f2; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(17, 24, 39, 0.4); display: flex; align-items: center; justify-content: center; z-index: 40; }
.modal-card { width: 440px; background: #fff; border-radius: 8px; padding: 16px; }
.history-card { width: min(1120px, calc(100vw - 32px)); max-height: 80vh; overflow: auto; }
.upload-title { margin: 8px 0 12px; font-weight: 600; }
.upload-note { margin: -8px 0 10px; font-size: 12px; color: #64748b; }
.upload-reject-note { margin: 0 0 10px; font-size: 12px; color: #991b1b; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px; }
.upload-help { margin: 8px 0 0; font-size: 12px; color: #475569; }
.upload-error { margin: 8px 0 0; font-size: 12px; color: #b91c1c; font-weight: 600; }
.history-note { margin: 6px 0 12px; font-size: 12px; color: #64748b; }
.history-row { cursor: pointer; }
.history-row:focus-visible { outline: 2px solid #3b82f6; outline-offset: -2px; }
.history-current-row { background: #eff6ff; }
.history-row-selected { background: #e0e7ff; }
.history-current-label { margin-top: 4px; font-size: 12px; color: #1d4ed8; font-weight: 700; }
.modal-actions { margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px; }

.ledger-ref-badge {
  margin-top: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 4px 8px;
  display: inline-block;
}
.ledger-nav-btn { border-color: #3b82f6; color: #1d4ed8; }

@media (max-width: 960px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
