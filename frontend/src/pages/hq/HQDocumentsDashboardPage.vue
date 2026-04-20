<template>
  <div class="hq-doc-page">
    <div class="hq-doc-grid">
      <BaseCard class="main-panel !p-[22px]">
        <template #head>
          <div class="flex w-full flex-wrap items-start justify-between gap-4">
            <div>
              <h2 class="m-0 text-[17px] font-bold text-slate-900">문서취합현황</h2>
            </div>
          </div>
        </template>
        <div class="hq-dashboard-body">
          <div v-if="dashboardLoading" class="dashboard-loading-overlay" aria-live="polite">
            <p class="dashboard-loading-text">로딩중입니다....</p>
          </div>
        <div class="kpi-scroll-wrap">
          <div class="stitch-kpi-grid kpi-compact kpi-single-row">
            <KpiCard
              label="전체현장 업로드 비율"
              :value="`${hqKpiAggregate.uploadPct}%`"
              accent="blue"
              :progress-pct="hqKpiAggregate.uploadPct"
              footer-note="전 현장 합산: 제출 완료 건수 ÷ 필수 건수"
              compact
            />
            <KpiCard
              label="금일 미결재"
              :value="pendingSummary.day"
              accent="orange"
              footer-note="KST 오늘 기준 검토 대기/검토중 문서"
              compact
            />
            <KpiCard
              label="최근 7일 미결재"
              :value="pendingSummary.week"
              accent="slate"
              footer-note="KST 최근 7일 제출 문서"
              compact
            />
            <KpiCard
              label="최근 30일 미결재"
              :value="pendingSummary.month"
              accent="red"
              footer-note="KST 최근 30일 제출 문서"
              compact
            />
          </div>
        </div>

        <section class="matrix-section">
          <div class="matrix-head">
            <h3 class="matrix-title">현장별 서류 제출 현황</h3>
            <span class="sub">현장 {{ matrixRows.length }}개, 서류 {{ requirementColumns.length }}종</span>
          </div>
          <div class="team-slot-filter-row">
            <button
              type="button"
              class="team-all-btn"
              :class="{ active: activeTeamSlot === 'ALL' }"
              @click="setAllSitesView"
            >
              전체현장
            </button>
            <label v-for="slot in teamSlotMeta" :key="slot.key" class="team-slot-field">
              <span class="team-slot-label">{{ slot.label }}</span>
              <select
                v-model="teamSlotFilters[slot.key]"
                class="control-select team-slot-select"
                @change="handleTeamSlotChange(slot.key)"
              >
                <option value="ALL">전체</option>
                <option v-for="opt in teamOptionsForSlot(slot.key)" :key="`${slot.key}-${opt}`" :value="opt">
                  {{ opt }}
                </option>
              </select>
            </label>
            <FilterBar class="controls team-side-controls !gap-2.5">
              <input
                v-model="siteSearch"
                type="text"
                class="control-input"
                placeholder="현장명 검색..."
              />
              <select v-model="period" class="control-select" @change="load">
                <option value="all">전체</option>
                <option value="day">일간</option>
                <option value="week">주간</option>
                <option value="month">월간</option>
                <option value="quarter">분기</option>
                <option value="half_year">반기</option>
                <option value="year">연간</option>
                <option value="event">이벤트</option>
              </select>
              <button type="button" class="stitch-btn-primary" @click="openContractorDocumentItemSettings">
                문서항목 수정
              </button>
              <button type="button" class="stitch-btn-secondary" @click="load">새로고침</button>
            </FilterBar>
          </div>
          <div class="matrix-wrap">
            <table class="matrix-table">
              <thead>
                <tr class="matrix-group-header-row">
                  <th rowspan="2" class="site-col site-col-corner">현장명</th>
                  <th
                    v-for="grp in requirementColumnGroups"
                    :key="`grp-${grp.key}`"
                    :colspan="grp.columns.length"
                    class="req-group-header"
                  >
                    {{ grp.label }}
                  </th>
                </tr>
                <tr class="matrix-col-header-row">
                  <th v-for="col in requirementColumns" :key="`col-${col.requirement_key}`" class="req-col">
                    {{ col.title }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in matrixRows" :key="`site-row-${row.site_id}`">
                  <td class="site-col sticky-site">
                    <button type="button" class="site-link" @click="selectSite(row.site_id)">
                      {{ displaySiteName(row.site_name) }}
                    </button>
                  </td>
                  <td v-for="col in requirementColumns" :key="`cell-${row.site_id}-${col.requirement_key}`" class="status-cell">
                    <div class="matrix-cell-inner">
                      <template v-if="isLedgerManagedDocumentType(col.document_type_code)">
                        <button
                          type="button"
                          class="status-pill status-pill-ledger-ref"
                          @click="goLedgerFromMatrix(row.site_id, col.requirement_key)"
                        >
                          관리대장
                        </button>
                        <button type="button" class="inst-detail-link" @click="goLedgerFromMatrix(row.site_id, col.requirement_key)">
                          전용 화면
                        </button>
                      </template>
                      <template v-else-if="matrixDisplayCell(row.site_id, col.requirement_key).latest_instance_id != null">
                        <button
                          type="button"
                          class="status-pill"
                          :class="
                            statusPillClass(effectiveHqMatrixStatus(matrixDisplayCell(row.site_id, col.requirement_key)))
                          "
                          @click="goInstanceDetail(row.site_id, col.requirement_key)"
                        >
                          {{
                            statusCompactLabel(
                              effectiveHqMatrixStatus(matrixDisplayCell(row.site_id, col.requirement_key)),
                            )
                          }}
                        </button>
                        <button type="button" class="inst-detail-link" @click="goInstanceDetail(row.site_id, col.requirement_key)">
                          상세
                        </button>
                      </template>
                      <template v-else>
                        <span
                          class="status-pill status-pill-no-instance"
                          :class="
                            statusPillClass(effectiveHqMatrixStatus(matrixDisplayCell(row.site_id, col.requirement_key)))
                          "
                          title="이 주기에 DocumentInstance(회차)가 아직 생성되지 않았습니다. 목록이 갱신되면 회차가 생길 수 있습니다."
                        >
                          {{
                            statusCompactLabel(
                              effectiveHqMatrixStatus(matrixDisplayCell(row.site_id, col.requirement_key)),
                            )
                          }}
                        </span>
                        <span
                          class="no-instance-badge"
                          title="DocumentInstance(회차)가 아직 생성되지 않았습니다."
                        >
                          회차 미생성
                        </span>
                      </template>
                    </div>
                  </td>
                </tr>
                <tr v-if="matrixRows.length === 0">
                  <td :colspan="Math.max(2, requirementColumns.length + 1)" class="empty-cell">
                    필터 조건에 맞는 현장 데이터가 없습니다.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="hq-monitor-extra">
          <div class="signal-box" :class="`signal-${signalStatus.toLowerCase()}`">
            문서취합 신호등: <strong>{{ signalLabel }}</strong>
          </div>
          <div class="extra-grid">
            <BaseCard class="extra-card">
              <div class="pending-summary-row">
                <strong>미결재 문서</strong>
                <span class="pending-count-badge">{{ pendingDocuments.length }}</span>
              </div>
              <button type="button" class="stitch-btn-secondary pending-open-btn" @click="openPendingDocumentsPage">
                미결재 문서
              </button>
              <p class="sub">버튼을 눌러 새 탭에서 표 형태로 확인하세요.</p>
            </BaseCard>
            <BaseCard class="extra-card" title="본사-현장 소통">
              <div class="history-head">
                <span class="sub">미확인 {{ unreadCommunicationCount }}건 · 최근 {{ communicationItems.length }}건</span>
                <div class="history-controls">
                  <label class="sub comm-toggle">
                    <input v-model="showUnreadOnly" type="checkbox" />
                    미확인만
                  </label>
                  <button type="button" class="stitch-btn-secondary pending-open-btn" @click="historyCollapsed = !historyCollapsed">
                    {{ historyCollapsed ? "펼치기" : "접기" }}
                  </button>
                </div>
              </div>
              <div v-if="!historyCollapsed" class="comm-table-wrap">
                <table class="comm-table">
                  <thead>
                    <tr>
                      <th>날짜</th>
                      <th>문서</th>
                      <th>코멘트</th>
                      <th>확인</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in displayedCommunicationItems"
                      :key="row.item_key"
                      role="button"
                      tabindex="0"
                      class="comm-row"
                      :class="{ 'comm-unread': !isCommunicationRead(row.item_key) }"
                      @click="goDetail(row.document_id)"
                      @keydown.enter.prevent="goDetail(row.document_id)"
                    >
                      <td>{{ formatDateTime(row.created_at) }}</td>
                      <td>{{ displaySiteName(row.site_name) }} · {{ row.title }}</td>
                      <td class="comm-comment-cell">{{ row.comment_text }}</td>
                      <td>
                        <button
                          type="button"
                          class="stitch-btn-secondary"
                          :disabled="isCommunicationRead(row.item_key)"
                          @click.stop="confirmCommunication(row.item_key)"
                        >
                          {{ isCommunicationRead(row.item_key) ? "확인됨" : "확인" }}
                        </button>
                      </td>
                    </tr>
                    <tr v-if="displayedCommunicationItems.length === 0">
                      <td colspan="4" class="sub">표시할 소통 내역이 없습니다.</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="sub">공간 절약을 위해 접어 두었습니다.</p>
            </BaseCard>
          </div>
        </section>
        </div>
      </BaseCard>
    </div>

    <div v-if="detailDocumentId" class="modal-backdrop" @click.self="closeDetailModal">
      <BaseCard class="modal-card !w-full max-w-[680px]" title="문서 상세 보기">
        <p v-if="detailLoading" class="sub">불러오는 중...</p>
        <p v-else-if="detailError" class="sub detail-error">{{ detailError }}</p>
        <template v-else-if="detailDocument">
          <p v-if="detailLedgerBlocked" class="ledger-detail-banner">{{ ledgerManagedUxMessage }}</p>
          <div class="detail-grid">
            <div><strong>문서번호</strong> {{ detailDocument.document_no }}</div>
            <div><strong>제목</strong> {{ detailDocument.title }}</div>
            <div><strong>현장</strong> {{ detailDocument.site_id }}</div>
            <div><strong>상태</strong> {{ statusLabel(detailDocument.current_status) }}</div>
            <div><strong>제출자</strong> {{ detailDocument.submitter_user_id }}</div>
            <div><strong>버전</strong> v{{ detailDocument.version_no }}</div>
            <div class="detail-span-2"><strong>설명</strong> {{ detailDocument.description || "-" }}</div>
            <div v-if="!detailLedgerBlocked" class="detail-span-2"><strong>코멘트</strong> {{ detailDocument.rejection_reason || "-" }}</div>
          </div>
          <DocumentCommentsPanel
            v-if="!detailLedgerBlocked"
            :document-id="detailDocument.id"
            :document-type-code="detailDocument.document_type"
          />
          <div v-else class="ledger-detail-actions">
            <button type="button" class="stitch-btn-primary" @click="goLedgerFromDetailModal">관리대장에서 보기</button>
          </div>
          <div class="modal-actions">
            <button type="button" class="stitch-btn-secondary" @click="closeDetailModal">닫기</button>
            <button
              type="button"
              class="stitch-btn-primary"
              :disabled="!detailDocument.file_path || detailDownloadLoading || detailLedgerBlocked"
              @click="downloadDetailFile"
            >
              {{ detailDownloadLoading ? "다운로드 중..." : "파일 다운로드" }}
            </button>
          </div>
        </template>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import DocumentCommentsPanel from "@/components/documents/DocumentCommentsPanel.vue";
import { DEMO_PILOT_SITE_CODE, isDemoPilotSiteScopeEnabled } from "@/config/demoPilotSite";
import { BaseCard, FilterBar, KpiCard } from "@/components/product";
import { formatDateTimeKst, todayKst } from "@/utils/datetime";
import { getReadCommunicationKeys, markCommunicationRead } from "@/utils/hqCommunicationRead";
import {
  hqLedgerRouteForDocumentType,
  isLedgerManagedDocumentType,
  LEDGER_MANAGED_UX_MESSAGE,
} from "@/utils/ledgerManagedDocument";
import { requirementFrequencyKoLabel, requirementFrequencySortOrder } from "@/utils/requirementFrequencyGroups";

interface SiteSummaryRow {
  site_id: number;
  site_name: string;
  total_required: number;
  submitted_count: number;
  approved_count: number;
  in_review_count: number;
  rejected_count: number;
  not_submitted_count: number;
  incomplete_count: number;
  submission_rate: number;
}

interface DashboardItem {
  site_id: number;
  site_name: string;
  requirement_id: number;
  document_type_code?: string | null;
  title: string;
  frequency: string;
  status: string;
  review_note: string | null;
  latest_document_id: number | null;
  latest_uploaded_at: string | null;
  current_document_id: number | null;
  current_file_name: string | null;
  current_file_download_url: string | null;
  uploaded_at: string | null;
  uploaded_by_user_id: number | null;
  uploaded_by_name?: string | null;
  workflow_status?: string | null;
  latest_instance_id?: number | null;
  category?: string | null;
  section?: string | null;
  /** 레거시 status가 NOT_SUBMITTED로 정규화돼도 본사 매트릭스에서 반려를 드러내기 위한 필드 */
  current_cycle_last_submission_status?: string | null;
  unresolved_rejected_document_id?: number | null;
  rejected_backlog_count?: number;
}
interface MatrixCellItem extends DashboardItem {}

interface PendingDocumentRow {
  document_id: number;
  title: string;
  site_name: string;
  status: string;
}

interface CommunicationItemRow {
  item_key: string;
  source: string;
  source_id: number;
  document_id: number;
  title: string;
  site_id: number;
  site_name: string;
  user_name: string;
  user_role: string;
  comment_text: string;
  created_at: string | null;
}

interface PendingSummary {
  day: number;
  week: number;
  month: number;
}

interface DocumentDetailModalData {
  id: number;
  document_no: string;
  title: string;
  site_id: number;
  submitter_user_id: number;
  current_status: string;
  file_path: string | null;
  description: string | null;
  rejection_reason: string | null;
  version_no: number;
  document_type?: string | null;
}

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
/** 기본 period: Decision sample-hq-doc-001 (월간 기본) 승인 반영 */
const period = ref<"all" | "day" | "week" | "month" | "quarter" | "half_year" | "year" | "event">("month");
const selectedSiteId = ref<number | null>(null);
const siteSearch = ref("");
const EXCLUDED_REQUIREMENT_KEYWORDS = ["중대재해", "사고보고"];
const HQ_DOCUMENT_REFRESH_EVENT = "besma-hq-documents-refresh";

const TEAM_SLOT_KEYS = ["1", "2", "3", "4", "5", "6", "gwal"] as const;
type TeamSlotKey = (typeof TEAM_SLOT_KEYS)[number];

const teamSlotMeta: { key: TeamSlotKey; label: string }[] = [
  { key: "1", label: "1팀" },
  { key: "2", label: "2팀" },
  { key: "3", label: "3팀" },
  { key: "4", label: "4팀" },
  { key: "5", label: "5팀" },
  { key: "6", label: "6팀" },
  { key: "gwal", label: "관급" },
];

const teamSlotFilters = reactive<Record<TeamSlotKey, string>>({
  "1": "ALL",
  "2": "ALL",
  "3": "ALL",
  "4": "ALL",
  "5": "ALL",
  "6": "ALL",
  gwal: "ALL",
});
const activeTeamSlot = ref<TeamSlotKey | "ALL">(isDemoPilotSiteScopeEnabled ? "ALL" : "1");

function dashboardQueryDate(): string {
  return todayKst();
}

/** hq-dashboard가 중첩 호출될 때(라우트 동기화 등) 로딩이 먼저 꺼지지 않도록 */
let hqDashboardLoadPending = 0;
let hqDashboardLoadTicket = 0;

const siteSummaries = ref<SiteSummaryRow[]>([]);
const items = ref<DashboardItem[]>([]);
const signalStatus = ref<"GREEN" | "YELLOW" | "RED">("GREEN");
const pendingDocuments = ref<PendingDocumentRow[]>([]);
const communicationItems = ref<CommunicationItemRow[]>([]);
const pendingSummary = ref<PendingSummary>({ day: 0, week: 0, month: 0 });
const historyCollapsed = ref(false);
const showUnreadOnly = ref(true);
const dashboardLoading = ref(true);
const dashboardBackgroundPreparing = ref(false);
const communicationReadKeys = ref<Set<string>>(new Set());
const unreadCommunicationCount = computed(
  () => communicationItems.value.filter((row) => !communicationReadKeys.value.has(row.item_key)).length,
);
const displayedCommunicationItems = computed(() =>
  showUnreadOnly.value ? communicationItems.value.filter((row) => !isCommunicationRead(row.item_key)) : communicationItems.value,
);
const hqKpiAggregate = computed(() => {
  let totalRequiredSum = 0;
  let submittedSum = 0;
  for (const s of matrixRows.value) {
    if (s.total_required <= 0) continue;
    totalRequiredSum += s.total_required;
    submittedSum += s.submitted_count;
  }
  const uploadPct =
    totalRequiredSum > 0 ? Math.round((submittedSum / totalRequiredSum) * 1000) / 10 : 0;
  return { uploadPct };
});

const matrixItems = computed(() =>
  items.value.filter((it) => {
    const title = (it.title || "").trim();
    if (EXCLUDED_REQUIREMENT_KEYWORDS.some((kw) => title.includes(kw))) return false;
    if (it.status === "NOT_REQUIRED") return false;
    return true;
  }),
);
function requirementColumnKey(item: DashboardItem): string {
  // 상세 이동은 requirement_id 축으로 고정해 문서코드 중복/누락 시에도 셀 충돌을 막는다.
  return `REQ-${item.requirement_id}`;
}
const requirementColumns = computed(() => {
  const seen = new Map<
    string,
    { requirement_key: string; requirement_id: number; title: string; document_type_code: string | null; frequency: string }
  >();
  for (const item of matrixItems.value) {
    const key = requirementColumnKey(item);
    if (!seen.has(key)) {
      seen.set(key, {
        requirement_key: key,
        requirement_id: item.requirement_id,
        title: item.title,
        document_type_code: (item.document_type_code || "").trim() || null,
        frequency: (item.frequency || "").trim() || "",
      });
    }
  }
  return Array.from(seen.values()).sort((a, b) => {
    const oa = requirementFrequencySortOrder(a.frequency);
    const ob = requirementFrequencySortOrder(b.frequency);
    if (oa !== ob) return oa - ob;
    return a.title.localeCompare(b.title, "ko");
  });
});

/** 선택 기간(일간/월간…) 조회 결과 열을 주기(일간·월간·…)별로 묶어 상단 행에 표시 */
const requirementColumnGroups = computed(() => {
  type Col = (typeof requirementColumns.value)[number];
  const cols = requirementColumns.value;
  const groups: { key: string; label: string; columns: Col[] }[] = [];
  for (const col of cols) {
    const label = requirementFrequencyKoLabel(col.frequency);
    const last = groups[groups.length - 1];
    if (last && last.label === label) {
      last.columns.push(col);
    } else {
      groups.push({ key: `${label}-${col.requirement_id}`, label, columns: [col] });
    }
  }
  return groups;
});
const matrixRows = computed(() =>
  siteSummaries.value.filter((site) => {
    const matchesSearch =
      !siteSearch.value.trim() || site.site_name.toLowerCase().includes(siteSearch.value.trim().toLowerCase());
    if (!matchesSearch) return false;
    return siteMatchesTeamSlotFilters(site.site_name);
  }),
);
const matrixCellMap = computed(() => {
  const map = new Map<string, DashboardItem>();
  for (const item of matrixItems.value) {
    map.set(`${item.site_id}-${requirementColumnKey(item)}`, item);
  }
  return map;
});

const signalLabel = computed(() => {
  if (signalStatus.value === "RED") return "RED (반려 발생)";
  if (signalStatus.value === "YELLOW") return "YELLOW (미제출/검토중 존재)";
  return "GREEN (정상)";
});

const detailDocumentId = ref<number | null>(null);
const detailDocument = ref<DocumentDetailModalData | null>(null);
const detailLoading = ref(false);
const detailDownloadLoading = ref(false);
const detailError = ref<string>("");
const ledgerManagedUxMessage = LEDGER_MANAGED_UX_MESSAGE;

const detailLedgerBlocked = computed(() => isLedgerManagedDocumentType(detailDocument.value?.document_type));
function statusLabel(status: string) {
  const map: Record<string, string> = {
    NOT_REQUIRED: "비대상",
    NOT_SUBMITTED: "제출대기",
    SUBMITTED: "검토대기",
    IN_REVIEW: "검토중",
    APPROVED: "승인",
    REJECTED: "반려 (재업로드 필요)",
  };
  return map[status] ?? status;
}

/** API는 반려를 status=NOT_SUBMITTED로 두고 확장 필드에만 REJECTED를 두는 경우가 있다. */
function effectiveHqMatrixStatus(row: DashboardItem): string {
  if (row.status === "REJECTED") return "REJECTED";
  if (row.workflow_status === "REJECTED") return "REJECTED";
  if (row.current_cycle_last_submission_status === "REJECTED") return "REJECTED";
  if (row.unresolved_rejected_document_id != null) return "REJECTED";
  if ((row.rejected_backlog_count ?? 0) > 0) return "REJECTED";
  return row.status;
}

function statusCompactLabel(status: string) {
  if (status === "APPROVED") return "승인";
  if (status === "SUBMITTED" || status === "IN_REVIEW") return "검토대기";
  if (status === "REJECTED") return "반려";
  return "미제출";
}

function statusPillClass(status: string) {
  if (status === "APPROVED") return "status-pill-approved";
  if (status === "SUBMITTED" || status === "IN_REVIEW") return "status-pill-pending";
  if (status === "REJECTED") return "status-pill-rejected";
  return "status-pill-not-submitted";
}

function matrixCell(siteId: number, requirementKeyOrId: string | number) {
  if (typeof requirementKeyOrId === "string") {
    return matrixCellMap.value.get(`${siteId}-${requirementKeyOrId}`) ?? null;
  }
  // 구형 쿼리 파라미터(review_requirement_id) 호환: requirement_id로 우선 조회
  const byId = matrixItems.value.find(
    (it) => it.site_id === siteId && it.requirement_id === requirementKeyOrId,
  );
  if (byId) {
    return matrixCellMap.value.get(`${siteId}-${requirementColumnKey(byId)}`) ?? byId;
  }
  return null;
}

function extractTeam(siteName: string) {
  const bracket = siteName.match(/^\[([^\]]+)\]/);
  if (bracket?.[1]) return bracket[1].trim();
  const firstToken = siteName.trim().split(/\s+/)[0];
  return firstToken || "기타";
}

function siteTeamSlot(siteName: string): TeamSlotKey | null {
  const m = siteName.match(/^\[([1-6])\./);
  if (m?.[1]) return m[1] as TeamSlotKey;
  if (/관급/.test(siteName)) return "gwal";
  return null;
}

function teamOptionsForSlot(slotKey: TeamSlotKey): string[] {
  const teams = new Set<string>();
  for (const site of siteSummaries.value) {
    if (siteTeamSlot(site.site_name) === slotKey) {
      teams.add(extractTeam(site.site_name));
    }
  }
  return Array.from(teams).sort((a, b) => a.localeCompare(b, "ko"));
}

function setAllSitesView() {
  activeTeamSlot.value = "ALL";
}

function handleTeamSlotChange(slotKey: TeamSlotKey) {
  activeTeamSlot.value = slotKey;
}

function displaySiteName(siteName: string): string {
  if (siteName.includes("청라C18") || siteName.includes("C18BL")) {
    return `(삼성인정제) ${siteName}`;
  }
  return siteName;
}

function siteMatchesTeamSlotFilters(siteName: string): boolean {
  if (activeTeamSlot.value === "ALL") return true;
  const slot = siteTeamSlot(siteName);
  if (slot === null) return false;
  if (slot !== activeTeamSlot.value) return false;
  const sel = teamSlotFilters[slot];
  return sel === "ALL" || sel === extractTeam(siteName);
}

function matrixDisplayCell(siteId: number, requirementKeyOrId: string | number): MatrixCellItem {
  const row = matrixCell(siteId, requirementKeyOrId);
  if (row) return row;
  const siteName = siteSummaries.value.find((s) => s.site_id === siteId)?.site_name ?? "-";
  const col =
    typeof requirementKeyOrId === "string"
      ? requirementColumns.value.find((c) => c.requirement_key === requirementKeyOrId)
      : requirementColumns.value.find((c) => c.requirement_id === requirementKeyOrId);
  return {
    site_id: siteId,
    site_name: siteName,
    requirement_id: typeof requirementKeyOrId === "number" ? requirementKeyOrId : -1,
    document_type_code: col?.document_type_code ?? null,
    title: col?.title ?? "-",
    frequency: "",
    status: "NOT_SUBMITTED",
    review_note: null,
    latest_document_id: null,
    latest_uploaded_at: null,
    current_document_id: null,
    current_file_name: null,
    current_file_download_url: null,
    uploaded_at: null,
    uploaded_by_user_id: null,
    uploaded_by_name: null,
    workflow_status: null,
    latest_instance_id: null,
    category: null,
    section: null,
  };
}

function goLedgerFromMatrix(siteId: number, requirementKey: string) {
  const col = requirementColumns.value.find((c) => c.requirement_key === requirementKey);
  const name = hqLedgerRouteForDocumentType(col?.document_type_code ?? null);
  if (!name) return;
  void router.push({ name, query: { site_id: String(siteId) } });
}

function goInstanceDetail(siteId: number, requirementKey: string) {
  const col = requirementColumns.value.find((c) => c.requirement_key === requirementKey);
  if (isLedgerManagedDocumentType(col?.document_type_code ?? null)) {
    goLedgerFromMatrix(siteId, requirementKey);
    return;
  }
  const cell = matrixDisplayCell(siteId, requirementKey);
  if (cell.latest_instance_id == null) return;
  void router.push({
    name: "hq-safe-document-instance-detail",
    params: { instanceId: String(cell.latest_instance_id) },
  });
}

function formatDateTime(value: string | null) {
  return formatDateTimeKst(value, "—");
}

function querySiteId(): number | null {
  const raw = route.query.site_id;
  if (typeof raw !== "string") return null;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

async function syncSiteIdQuery(nextSiteId: number | null) {
  const currentRaw = route.query.site_id;
  const currentSiteId = typeof currentRaw === "string" ? Number(currentRaw) : null;
  if (currentSiteId === nextSiteId) return;

  const nextQuery: Record<string, unknown> = { ...route.query };
  if (nextSiteId == null) {
    delete nextQuery.site_id;
  } else {
    nextQuery.site_id = String(nextSiteId);
  }
  await router.push({ name: "hq-safe-documents", query: nextQuery });
}

function applyDashboardPayload(
  payload: {
    site_summaries?: SiteSummaryRow[];
    items?: DashboardItem[];
    signal_status?: "GREEN" | "YELLOW" | "RED";
    pending_documents?: PendingDocumentRow[];
    pending_documents_summary?: PendingSummary;
  },
  routeSiteId: number | null,
) {
  siteSummaries.value = payload.site_summaries ?? [];
  items.value = payload.items ?? [];
  signalStatus.value = payload.signal_status ?? "GREEN";
  pendingDocuments.value = payload.pending_documents ?? [];
  pendingSummary.value = payload.pending_documents_summary ?? { day: 0, week: 0, month: 0 };
  if (routeSiteId != null && siteSummaries.value.some((s) => s.site_id === routeSiteId)) {
    selectedSiteId.value = routeSiteId;
  } else {
    selectedSiteId.value = siteSummaries.value[0]?.site_id ?? null;
  }
}

function isCommunicationRead(itemKey: string): boolean {
  return communicationReadKeys.value.has(itemKey);
}

function confirmCommunication(itemKey: string) {
  markCommunicationRead(authLoginId.value, itemKey);
  communicationReadKeys.value = getReadCommunicationKeys(authLoginId.value);
}

const authLoginId = computed(() => auth.user?.login_id ?? null);

async function loadCommunications() {
  const res = await api.get("/documents/hq-communications", { params: { limit: 120 } });
  communicationItems.value = (res.data?.items ?? []) as CommunicationItemRow[];
  communicationReadKeys.value = getReadCommunicationKeys(authLoginId.value);
}

async function syncFallbackSiteId(routeSiteId: number | null) {
  if (isDemoPilotSiteScopeEnabled) return;
  if (routeSiteId != null) return;
  if (selectedSiteId.value != null) {
    await syncSiteIdQuery(selectedSiteId.value);
  }
}

async function load() {
  const ticket = ++hqDashboardLoadTicket;
  hqDashboardLoadPending += 1;
  dashboardLoading.value = true;
  dashboardBackgroundPreparing.value = false;
  try {
    const routeSiteId = querySiteId();
    const paramsBase: Record<string, string | number> = {
      period: period.value,
      date: dashboardQueryDate(),
      ...(routeSiteId != null ? { site_id: routeSiteId } : {}),
      ...(isDemoPilotSiteScopeEnabled && routeSiteId == null ? { site_code: DEMO_PILOT_SITE_CODE } : {}),
    };
    const useQuickFirst =
      !isDemoPilotSiteScopeEnabled &&
      activeTeamSlot.value === "1" &&
      routeSiteId == null &&
      !siteSearch.value.trim();

    if (useQuickFirst) {
      const quick = await api.get("/documents/hq-dashboard", {
        params: { ...paramsBase, team_slot: "1" },
      });
      if (ticket !== hqDashboardLoadTicket) return;
      applyDashboardPayload(quick.data, routeSiteId);
      await loadCommunications();
      dashboardLoading.value = false;
      dashboardBackgroundPreparing.value = true;
      void api
        .get("/documents/hq-dashboard", { params: paramsBase })
        .then((full) => {
          if (ticket !== hqDashboardLoadTicket) return;
          applyDashboardPayload(full.data, routeSiteId);
          void loadCommunications();
        })
        .finally(() => {
          if (ticket === hqDashboardLoadTicket) {
            dashboardBackgroundPreparing.value = false;
          }
        });
      return;
    }

    const res = await api.get("/documents/hq-dashboard", { params: paramsBase });
    if (ticket !== hqDashboardLoadTicket) return;
    applyDashboardPayload(res.data, routeSiteId);
    await loadCommunications();
    await syncFallbackSiteId(routeSiteId);

    const reviewSiteRaw = route.query.review_site_id;
    const reviewRequirementRaw = route.query.review_requirement_id;
    if (typeof reviewSiteRaw === "string" && typeof reviewRequirementRaw === "string") {
      const reviewSiteId = Number(reviewSiteRaw);
      const reviewRequirementId = Number(reviewRequirementRaw);
      if (Number.isInteger(reviewSiteId) && Number.isInteger(reviewRequirementId)) {
        const cell = matrixDisplayCell(reviewSiteId, reviewRequirementId);
        if (cell.latest_instance_id != null) {
          await router.replace({
            name: "hq-safe-document-instance-detail",
            params: { instanceId: String(cell.latest_instance_id) },
          });
        }
      }
    }
  } finally {
    hqDashboardLoadPending -= 1;
    if (hqDashboardLoadPending <= 0) {
      hqDashboardLoadPending = 0;
      dashboardLoading.value = false;
    }
  }
}

function handleHqDocumentRefresh() {
  void load();
}

function handleVisibilityChange() {
  if (document.visibilityState === "visible") {
    void load();
  }
}

function handleStorage(event: StorageEvent) {
  if (event.key === HQ_DOCUMENT_REFRESH_EVENT) {
    void load();
  }
}

async function selectSite(siteId: number) {
  if (selectedSiteId.value === siteId) return;
  selectedSiteId.value = siteId;
  await syncSiteIdQuery(siteId);
}

function openPendingDocumentsPage() {
  const target = router.resolve({
    name: "hq-safe-documents-pending",
    query: { date: dashboardQueryDate(), period: period.value },
  });
  window.open(target.href, "_blank", "noopener");
}

function openContractorDocumentItemSettings() {
  const groupKey = activeTeamSlot.value === "4" ? "SAMSUNG" : "GENERAL";
  router.push({
    name: "hq-safe-contractor-document-settings",
    query: { group_key: groupKey },
  });
}

async function goDetail(id: number) {
  detailDocumentId.value = id;
  detailDocument.value = null;
  detailError.value = "";
  detailLoading.value = true;
  try {
    const res = await api.get(`/documents/${id}`);
    detailDocument.value = res.data as DocumentDetailModalData;
  } catch (err: unknown) {
    detailError.value = "문서 상세를 불러오지 못했습니다.";
  } finally {
    detailLoading.value = false;
  }
}

function goLedgerFromDetailModal() {
  const code = detailDocument.value?.document_type;
  const name = hqLedgerRouteForDocumentType(code || null);
  const sid = detailDocument.value?.site_id;
  closeDetailModal();
  if (name && sid != null) void router.push({ name, query: { site_id: String(sid) } });
  else if (name) void router.push({ name });
}

function closeDetailModal() {
  detailDocumentId.value = null;
  detailDocument.value = null;
  detailError.value = "";
  detailLoading.value = false;
  detailDownloadLoading.value = false;
}

function resolveFilenameFromHeader(headerValue: string | undefined, fallback: string) {
  if (!headerValue) return fallback;
  const matchUtf = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (matchUtf?.[1]) {
    try {
      return decodeURIComponent(matchUtf[1]);
    } catch {
      return fallback;
    }
  }
  const matchPlain = headerValue.match(/filename=\"?([^\";]+)\"?/i);
  return matchPlain?.[1] ?? fallback;
}

async function downloadDetailFile() {
  if (!detailDocument.value || detailLedgerBlocked.value) return;
  detailDownloadLoading.value = true;
  try {
    const res = await api.get(`/documents/${detailDocument.value.id}/file`, {
      responseType: "blob",
    });
    const blob = new Blob([res.data]);
    const contentDisposition = res.headers["content-disposition"] as string | undefined;
    const filename = resolveFilenameFromHeader(
      contentDisposition,
      `${detailDocument.value.document_no || "document"}.bin`,
    );
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } finally {
    detailDownloadLoading.value = false;
  }
}

onMounted(() => {
  void load();
  window.addEventListener("focus", handleHqDocumentRefresh);
  window.addEventListener(HQ_DOCUMENT_REFRESH_EVENT, handleHqDocumentRefresh as EventListener);
  window.addEventListener("storage", handleStorage);
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onUnmounted(() => {
  window.removeEventListener("focus", handleHqDocumentRefresh);
  window.removeEventListener(HQ_DOCUMENT_REFRESH_EVENT, handleHqDocumentRefresh as EventListener);
  window.removeEventListener("storage", handleStorage);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
});

watch(
  () => route.query.site_id,
  async () => {
    await load();
  },
);

</script>

<style scoped>
.hq-dashboard-body {
  position: relative;
  min-height: 200px;
}

.dashboard-loading-overlay {
  position: absolute;
  inset: 0;
  z-index: 6;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.78);
  pointer-events: none;
}

.dashboard-loading-text {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #475569;
  letter-spacing: -0.01em;
}

.hq-doc-page {
  width: 100%;
}

.hq-doc-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.site-panel {
  padding: 20px 18px;
}

.panel-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.main-title {
  font-size: 17px;
  margin-bottom: 4px;
}

.site-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.site-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.site-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}

.site-item.active {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2);
}

.site-name {
  font-weight: 700;
  margin-bottom: 8px;
  color: #0f172a;
  font-size: 14px;
}

.site-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.main-panel {
  padding: 22px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.control-input,
.control-select {
  box-sizing: border-box;
  height: 36px;
  min-height: 36px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0 12px;
  line-height: 1.25;
  font-size: 14px;
  font-weight: 600;
  background: #fff;
  color: #0f172a;
}

.control-input {
  line-height: normal;
}

.control-select {
  -webkit-text-fill-color: #0f172a;
}

.control-select option {
  color: #0f172a;
}

.kpi-compact {
  margin-bottom: 10px;
}

.kpi-scroll-wrap {
  width: 100%;
  overflow-x: auto;
}

.kpi-single-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(200px, 1fr));
  gap: 8px;
}

.kpi-single-row :deep(article) {
  padding: 10px 12px 12px;
  border-top-width: 3px;
  border: 1px solid #cbd5e1;
  box-shadow:
    0 8px 20px rgba(15, 23, 42, 0.12),
    0 2px 6px rgba(15, 23, 42, 0.08);
}

.kpi-single-row :deep(article p) {
  margin-top: 4px;
}

.kpi-single-row :deep(article .mt-3\.5) {
  margin-top: 8px;
  height: 6px;
}

.hq-monitor-extra {
  margin: 0 0 16px;
}

.signal-box {
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
}

.signal-green { background: #ecfdf5; color: #166534; border: 1px solid #bbf7d0; }
.signal-yellow { background: #fefce8; color: #854d0e; border: 1px solid #fde68a; }
.signal-red { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }

.extra-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.extra-card {
  padding: 12px;
}

.pending-summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.pending-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 22px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.pending-open-btn {
  margin-bottom: 6px;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.history-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comm-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.extra-list {
  margin: 0;
  padding-left: 16px;
  display: grid;
  gap: 6px;
}

.comm-table-wrap {
  overflow: auto;
}

.comm-table {
  width: 100%;
  border-collapse: collapse;
}

.comm-table th,
.comm-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 8px 6px;
  font-size: 12px;
  text-align: left;
  vertical-align: top;
}

.comm-row {
  cursor: pointer;
}

.comm-row:hover {
  background: #f8fafc;
}

.comm-unread {
  background: #fff7ed;
}

.comm-comment-cell {
  max-width: 340px;
  white-space: pre-wrap;
}

.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: #1d4ed8;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}

.sub {
  display: block;
  font-size: 12px;
  color: #64748b;
}

.table-wrap {
  margin-top: 0;
}

.matrix-section {
  margin-top: 14px;
}

.matrix-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.matrix-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.matrix-wrap {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.matrix-table {
  width: max-content;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 11px;
}

.matrix-table th,
.matrix-table td {
  border-right: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  padding: 5px 6px;
  background: #fff;
  vertical-align: middle;
}

.matrix-table th {
  position: sticky;
  top: 0;
  z-index: 3;
  background: #f8fafc;
  font-weight: 700;
  text-align: center;
}

.matrix-group-header-row .req-group-header {
  top: 0;
  z-index: 5;
  background: #e0f2fe;
  color: #0c4a6e;
  font-size: 11px;
  padding: 6px 4px;
  border-bottom: 1px solid #bae6fd;
}

.matrix-col-header-row th.req-col {
  top: 30px;
  z-index: 4;
  background: #f8fafc;
}

.site-col-corner {
  position: sticky;
  top: 0;
  left: 0;
  z-index: 7;
  vertical-align: middle;
}

.site-col {
  min-width: 150px;
  max-width: 180px;
  text-align: left !important;
}

.sticky-site {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #fff;
}

.req-col {
  min-width: 72px;
  max-width: 84px;
  white-space: normal;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-cell {
  text-align: center;
}

.status-pill {
  border: 0;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  cursor: pointer;
  white-space: nowrap;
  min-width: 48px;
}

.status-pill-empty {
  display: inline-block;
  cursor: default;
}

.cell-actions {
  margin-top: 6px;
  display: flex;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
}

.cell-btn {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  cursor: pointer;
}

.cell-btn-primary {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}

.status-pill-approved { background: #dcfce7; color: #166534; }
.status-pill-rejected { background: #fee2e2; color: #991b1b; }
.status-pill-pending { background: #fef3c7; color: #92400e; }
.status-pill-not-submitted { background: #ffedd5; color: #9a3412; }
.status-pill-neutral { background: #e2e8f0; color: #334155; }

.status-pill-no-instance {
  cursor: default;
  opacity: 0.92;
}

.status-pill-ledger-ref {
  background: #dbeafe;
  color: #1e40af;
}

.no-instance-badge {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  background: #f1f5f9;
  border-radius: 4px;
  padding: 2px 6px;
  cursor: help;
}

.site-link {
  border: 0;
  background: transparent;
  color: #0f172a;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
  max-height: 2.6em;
  font-size: 11px;
  width: 100%;
}

.team-slot-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: flex-end;
  margin: 0 0 8px;
}

.team-side-controls {
  margin-left: auto;
}

.team-all-btn {
  height: 36px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.team-all-btn.active {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}

.team-slot-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.team-slot-label {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
}

.team-slot-select {
  min-width: 120px;
  max-width: 200px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn-compact {
  padding: 6px 12px;
  font-size: 12px;
}

.cell-muted {
  color: #64748b;
  font-size: 13px;
  max-width: 220px;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 32px 16px !important;
}

.matrix-cell-inner {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.inst-detail-link {
  font-size: 12px;
  padding: 0;
  border: none;
  background: none;
  color: #2563eb;
  cursor: pointer;
  text-decoration: underline;
}

.inst-detail-link:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  text-decoration: none;
}

.status-pill:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-card {
  width: min(440px, 92vw);
  padding: 22px;
}

.modal-title {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}

.modal-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  font-size: 13px;
}

.detail-span-2 {
  grid-column: 1 / -1;
}

.ledger-detail-banner {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e3a8a;
  font-size: 13px;
  line-height: 1.45;
}

.ledger-detail-actions {
  margin-top: 14px;
}

.detail-error {
  color: #b91c1c;
}

@media (max-width: 1024px) {
  .hq-doc-grid {
    grid-template-columns: 1fr;
  }
  .extra-grid {
    grid-template-columns: 1fr;
  }
}
</style>
