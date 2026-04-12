<template>
  <div class="site-mgmt-grid">
    <aside class="card site-list-panel">
      <div class="panel-head">
        <div class="card-title">현장 관리</div>
        <button class="secondary" :disabled="loadingList" @click="loadSites">새로고침</button>
      </div>
      <input v-model="keyword" type="text" placeholder="현장명/코드 검색" class="search-input" />
      <select v-model="statusFilter">
        <option value="ALL">전체</option>
        <option value="IN_PROGRESS">진행</option>
        <option value="STOPPED">중지</option>
        <option value="COMPLETED">준공</option>
        <option value="UNKNOWN">데이터 없음</option>
      </select>

      <div v-if="loadingList" class="panel-state">현장 목록 불러오는 중...</div>
      <div v-else-if="filteredSites.length === 0" class="panel-state">조건에 맞는 현장이 없습니다.</div>
      <div v-else class="site-list">
        <button
          v-for="site in filteredSites"
          :key="site.id"
          class="site-item"
          :class="{ active: selectedSiteId === site.id }"
          @click="selectSite(site.id)"
        >
          <div class="site-name">{{ site.site_name }}</div>
          <div class="site-meta">
            <span>{{ site.site_code }}</span>
            <span class="dot">·</span>
            <span>{{ site.status || "데이터 없음" }}</span>
          </div>
          <div class="mini-summary">미제출 {{ getNotSubmitted(site.id) }}건</div>
        </button>
      </div>
    </aside>

    <section class="card detail-panel">
      <div class="panel-head">
        <div class="card-title">현장 상세 대시보드</div>
        <span class="updated-at">기준일: {{ today }}</span>
      </div>

      <div v-if="!selectedSite" class="panel-state">선택된 현장이 없습니다.</div>
      <div v-else-if="loadingDetail" class="panel-state">현장 상세 불러오는 중...</div>
      <div v-else class="site-detail-wrap">
        <div class="header-block">
          <div>
            <h2>{{ selectedSite.site_name }}</h2>
            <div class="header-sub">{{ selectedSite.site_code }}</div>
          </div>
          <span class="status-pill">{{ selectedSite.status || "데이터 없음" }}</span>
        </div>

        <div class="header-grid">
          <div><span>공사기간</span><strong>{{ periodLabel }}</strong></div>
          <div><span>주소</span><strong>{{ selectedSite.address || "데이터 없음" }}</strong></div>
          <div><span>발주처</span><strong>{{ selectedSite.client_name || "데이터 없음" }}</strong></div>
          <div><span>시공사</span><strong>{{ selectedSite.contractor_name || "데이터 없음" }}</strong></div>
        </div>

        <div class="manager-grid">
          <div class="manager-card">
            <div class="manager-title">현장소장</div>
            <div class="manager-name">{{ managerLabel(management.project_manager) }}</div>
            <div class="manager-role">{{ managerRoleLabel(management.project_manager, "현장소장") }}</div>
          </div>
          <div class="manager-card">
            <div class="manager-title">공무</div>
            <div class="manager-name">{{ managerLabel(management.site_manager) }}</div>
            <div class="manager-role">{{ managerRoleLabel(management.site_manager, "공무군") }}</div>
          </div>
          <div class="manager-card">
            <div class="manager-title">안전관리자</div>
            <div class="manager-name">{{ managerLabel(management.safety_manager) }}</div>
            <div class="manager-role">{{ managerRoleLabel(management.safety_manager, "안전관리자") }}</div>
          </div>
        </div>

        <div class="kpi-grid">
          <div class="kpi-card"><span>오늘 출역 인원</span><strong>{{ todayWorkerCountLabel }}</strong></div>
          <div class="kpi-card"><span>서명 완료율</span><strong>{{ signatureCompletionLabel }}</strong></div>
          <div class="kpi-card"><span>미제출 문서 수</span><strong>{{ notSubmittedLabel }}</strong></div>
          <div class="kpi-card"><span>최근 반려/재업로드 필요</span><strong>{{ rejectedNeedCountLabel }}</strong></div>
        </div>

        <div class="ops-tabs">
          <button class="secondary" :class="{ active: activeOpsTab === 'documents' }" @click="activeOpsTab = 'documents'">최근 문서</button>
          <button class="secondary" :class="{ active: activeOpsTab === 'tbm' }" @click="activeOpsTab = 'tbm'">최근 TBM</button>
          <button class="secondary" :class="{ active: activeOpsTab === 'others' }" @click="activeOpsTab = 'others'">최근 이슈/피드백/교육</button>
        </div>

        <div class="info-block" v-if="activeOpsTab === 'documents'">
          <div class="block-title">최근 문서</div>
          <div v-if="recentDocumentItems.length === 0" class="muted">데이터 없음</div>
          <table v-else class="basic-table">
            <thead>
              <tr><th>문서명</th><th>상태</th><th>최근 제출</th><th>비고</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in recentDocumentItems" :key="item.requirement_id">
                <td>{{ item.title }}</td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ formatDateTime(item.latest_uploaded_at) }}</td>
                <td>{{ item.review_note || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="info-block" v-if="activeOpsTab === 'tbm'">
          <div class="block-title">최근 TBM</div>
          <div class="status-line"><span>최근 배포일:</span><strong>{{ latestDistribution?.target_date || "데이터 없음" }}</strong></div>
          <div class="status-line"><span>TBM 시작:</span><strong>{{ tbmStatusLabel }}</strong></div>
          <div class="status-line"><span>서명 진행:</span><strong>{{ signatureCompletionLabel }}</strong></div>
        </div>

        <div class="info-block" v-if="activeOpsTab === 'others'">
          <div class="block-title">최근 이슈/피드백/교육</div>
          <div class="status-line"><span>최근 피드백:</span><strong>{{ latestFeedbackLabel }}</strong></div>
          <div class="status-line"><span>최근 이슈:</span><strong>{{ issueCountLabel }}</strong></div>
          <div class="status-line"><span>최근 교육:</span><strong>연동 전</strong></div>
        </div>

        <div class="actions-row">
          <button class="secondary" @click="goDocuments">문서 보기</button>
          <button class="secondary" :disabled="!latestRejectedItem?.latest_document_id" @click="goRejectedDetail">재업로드 필요 문서 보기</button>
          <button class="secondary" disabled title="연결된 근로자 전용 페이지가 없습니다.">근로자 보기</button>
          <button class="secondary" @click="goTbm">TBM 보기</button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { formatDateTimeKst, todayKst } from "@/utils/datetime";

interface SiteRow {
  id: number;
  site_code: string;
  site_name: string;
  status: string | null;
  start_date: string | null;
  end_date: string | null;
  address: string | null;
  client_name: string | null;
  contractor_name: string | null;
  project_manager: string | null;
  site_manager: string | null;
}

interface DashboardSiteSummary {
  site_id: number;
  not_submitted_count: number;
  rejected_count: number;
}

interface DashboardItem {
  site_id: number;
  requirement_id: number;
  title: string;
  status: string;
  review_note: string | null;
  latest_uploaded_at: string | null;
  latest_document_id: number | null;
}

interface DistributionRow {
  id: number;
  target_date: string;
  worker_count: number;
  is_tbm_active: boolean;
  tbm_started_at: string | null;
}

interface DistributionWorker {
  start_signed_at: string | null;
  end_signed_at: string | null;
  issue_flag: boolean;
}

interface SiteManagerResolved {
  source_name: string | null;
  person_id: number | null;
  position_code: string | null;
  role_label: string | null;
  resolve_status: "MATCHED" | "UNMATCHED" | "UNLINKED";
}

interface SiteManagementSummary {
  project_manager: SiteManagerResolved;
  site_manager: SiteManagerResolved;
  safety_manager: SiteManagerResolved;
}

interface FeedbackRow {
  id: number;
  content: string;
  created_at: string;
}

const today = todayKst();
const router = useRouter();
const sites = ref<SiteRow[]>([]);
const loadingList = ref(false);
const loadingDetail = ref(false);
const keyword = ref("");
const statusFilter = ref<"ALL" | "IN_PROGRESS" | "STOPPED" | "COMPLETED" | "UNKNOWN">("ALL");
const selectedSiteId = ref<number | null>(null);
const activeOpsTab = ref<"documents" | "tbm" | "others">("documents");

const siteSummaryMap = ref<Record<number, DashboardSiteSummary>>({});
const dashboardItems = ref<DashboardItem[]>([]);
const latestDistribution = ref<DistributionRow | null>(null);
const distributionWorkers = ref<DistributionWorker[]>([]);
const feedbacks = ref<FeedbackRow[]>([]);
const management = ref<SiteManagementSummary>({
  project_manager: { source_name: null, person_id: null, position_code: null, role_label: null, resolve_status: "UNLINKED" },
  site_manager: { source_name: null, person_id: null, position_code: null, role_label: null, resolve_status: "UNLINKED" },
  safety_manager: { source_name: null, person_id: null, position_code: null, role_label: null, resolve_status: "UNLINKED" },
});

const selectedSite = computed(() => sites.value.find((s) => s.id === selectedSiteId.value) ?? null);
const selectedSummary = computed(() => (selectedSiteId.value ? siteSummaryMap.value[selectedSiteId.value] ?? null : null));
const filteredSites = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  return sites.value
    .filter((s) => {
      if (statusFilter.value === "ALL") return true;
      return normalizeStatusCategory(s.status) === statusFilter.value;
    })
    .filter((s) => {
      if (!q) return true;
      return `${s.site_name} ${s.site_code}`.toLowerCase().includes(q);
    });
});

const latestRejectedItem = computed(() => {
  const rows = dashboardItems.value.filter((it) => it.status === "REJECTED");
  if (rows.length === 0) return null;
  return [...rows].sort((a, b) => (b.latest_uploaded_at || "").localeCompare(a.latest_uploaded_at || ""))[0];
});

const recentDocumentItems = computed(() =>
  [...dashboardItems.value]
    .filter((it) => !!it.latest_uploaded_at)
    .sort((a, b) => (b.latest_uploaded_at || "").localeCompare(a.latest_uploaded_at || ""))
    .slice(0, 5),
);
const periodLabel = computed(() => {
  if (!selectedSite.value) return "데이터 없음";
  return `${selectedSite.value.start_date || "-"} ~ ${selectedSite.value.end_date || "-"}`;
});
const todayWorkerCountLabel = computed(() => {
  if (!latestDistribution.value || latestDistribution.value.target_date !== today) return "데이터 없음";
  return `${latestDistribution.value.worker_count}명`;
});
const notSubmittedLabel = computed(() => `${selectedSummary.value?.not_submitted_count ?? 0}건`);
const rejectedNeedCountLabel = computed(() => `${selectedSummary.value?.rejected_count ?? 0}건`);
const tbmStatusLabel = computed(() => {
  if (!latestDistribution.value) return "데이터 없음";
  if (latestDistribution.value.is_tbm_active) {
    return `진행 중 (${formatDateTime(latestDistribution.value.tbm_started_at)})`;
  }
  return "미시작";
});
const signatureCompletionLabel = computed(() => {
  const total = distributionWorkers.value.length;
  if (total === 0) return "데이터 없음";
  const signed = distributionWorkers.value.filter((w) => !!w.start_signed_at || !!w.end_signed_at).length;
  return `${Math.round((signed / total) * 100)}% (${signed}/${total})`;
});
const latestFeedbackLabel = computed(() => feedbacks.value[0]?.content || "데이터 없음");
const issueCountLabel = computed(() => {
  if (distributionWorkers.value.length === 0) return "데이터 없음";
  return `${distributionWorkers.value.filter((w) => w.issue_flag).length}건`;
});

function statusLabel(status: string) {
  const map: Record<string, string> = {
    NOT_REQUIRED: "비대상",
    NOT_SUBMITTED: "미제출",
    SUBMITTED: "제출됨",
    IN_REVIEW: "검토중",
    APPROVED: "승인",
    REJECTED: "반려",
  };
  return map[status] ?? status;
}

function normalizeStatusCategory(status: string | null) {
  const value = (status || "").toUpperCase();
  if (value === "ACTIVE" || value === "IN_PROGRESS") return "IN_PROGRESS";
  if (value === "STOPPED" || value === "PAUSED") return "STOPPED";
  if (value === "COMPLETED" || value === "DONE" || value === "CLOSED") return "COMPLETED";
  return "UNKNOWN";
}

function formatDateTime(value: string | null) {
  return formatDateTimeKst(value, "-");
}

function managerLabel(manager: SiteManagerResolved) {
  if (manager.source_name) return manager.source_name;
  return "미연결";
}

function managerRoleLabel(manager: SiteManagerResolved, fallback: string) {
  if (manager.resolve_status === "UNLINKED") return "미연결";
  if (manager.resolve_status === "UNMATCHED") return "역할 미확정";
  return manager.role_label || fallback;
}

function getNotSubmitted(siteId: number) {
  return siteSummaryMap.value[siteId]?.not_submitted_count ?? 0;
}

async function loadSites() {
  loadingList.value = true;
  try {
    const [sitesRes, dashRes] = await Promise.all([
      api.get("/sites"),
      api.get("/documents/hq-dashboard", { params: { period: "day", date: today } }),
    ]);
    sites.value = sitesRes.data;
    siteSummaryMap.value = Object.fromEntries(
      (dashRes.data.site_summaries || []).map((s: DashboardSiteSummary) => [s.site_id, s]),
    );
    if (selectedSiteId.value == null && sites.value.length > 0) {
      selectedSiteId.value = sites.value[0].id;
      await loadSelectedSiteDetail();
    } else if (selectedSiteId.value != null && !sites.value.some((s) => s.id === selectedSiteId.value)) {
      selectedSiteId.value = sites.value[0]?.id ?? null;
      if (selectedSiteId.value != null) await loadSelectedSiteDetail();
    }
  } finally {
    loadingList.value = false;
  }
}

async function loadSelectedSiteDetail() {
  if (!selectedSiteId.value) return;
  loadingDetail.value = true;
  dashboardItems.value = [];
  latestDistribution.value = null;
  distributionWorkers.value = [];
  feedbacks.value = [];
  management.value = {
    project_manager: { source_name: null, person_id: null, position_code: null, role_label: null, resolve_status: "UNLINKED" },
    site_manager: { source_name: null, person_id: null, position_code: null, role_label: null, resolve_status: "UNLINKED" },
    safety_manager: { source_name: null, person_id: null, position_code: null, role_label: null, resolve_status: "UNLINKED" },
  };
  try {
    const [dashRes, distRes, mgmtRes] = await Promise.all([
      api.get("/documents/hq-dashboard", {
        params: { period: "day", date: today, site_id: selectedSiteId.value },
      }),
      api.get("/daily-work-plans/distributions", {
        params: { site_id: selectedSiteId.value, limit: 1 },
      }),
      api.get(`/sites/${selectedSiteId.value}/management-summary`),
    ]);

    dashboardItems.value = dashRes.data.items || [];
    management.value = mgmtRes.data;

    const latestDist = (distRes.data || [])[0] ?? null;
    latestDistribution.value = latestDist;
    if (latestDist?.id) {
      try {
        const [detailRes, feedbackRes] = await Promise.all([
          api.get(`/daily-work-plans/distributions/${latestDist.id}`),
          api.get(`/daily-work-plans/distributions/${latestDist.id}/feedbacks`),
        ]);
        distributionWorkers.value = detailRes.data.workers || [];
        feedbacks.value = feedbackRes.data || [];
      } catch {
        distributionWorkers.value = [];
        feedbacks.value = [];
      }
    }
  } finally {
    loadingDetail.value = false;
  }
}

async function selectSite(siteId: number) {
  if (selectedSiteId.value === siteId) return;
  selectedSiteId.value = siteId;
  await loadSelectedSiteDetail();
}

function goDocuments() {
  router.push({ name: "hq-safe-documents", query: { site_id: selectedSiteId.value ?? undefined } });
}

function goRejectedDetail() {
  if (!latestRejectedItem.value?.latest_document_id) return;
  router.push({
    name: "hq-safe-document-detail",
    params: { id: latestRejectedItem.value.latest_document_id },
  });
}

function goTbm() {
  router.push({ name: "hq-safe-tbm-monitor" });
}

onMounted(loadSites);
</script>

<style scoped>
.site-mgmt-grid { display: grid; grid-template-columns: 300px 1fr; gap: 12px; }
.site-list-panel { display: flex; flex-direction: column; gap: 10px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.search-input { width: 100%; }
.site-list { display: flex; flex-direction: column; gap: 8px; max-height: 70vh; overflow: auto; }
.site-item { border: 1px solid #e5e7eb; background: #fff; border-radius: 8px; padding: 10px; text-align: left; cursor: pointer; }
.site-item.active { border-color: #1d4ed8; background: #eff6ff; }
.site-name { font-weight: 700; margin-bottom: 2px; }
.site-meta { color: #4b5563; font-size: 12px; }
.dot { margin: 0 4px; }
.mini-summary { margin-top: 6px; font-size: 12px; color: #1f2937; font-weight: 600; }
.detail-panel { min-height: 420px; }
.updated-at { color: #6b7280; font-size: 12px; }
.panel-state { color: #6b7280; padding: 20px 0; }
.site-detail-wrap { display: grid; gap: 12px; }
.header-block { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }
.header-block h2 { margin: 0; font-size: 22px; }
.header-sub { color: #6b7280; margin-top: 4px; }
.status-pill { background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 600; }
.header-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.header-grid > div { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 4px; }
.header-grid span { color: #6b7280; font-size: 12px; }
.manager-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.manager-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; }
.manager-title { color: #6b7280; font-size: 12px; margin-bottom: 4px; }
.manager-name { font-weight: 700; margin-bottom: 2px; }
.manager-role { font-size: 12px; color: #374151; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.kpi-card { background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; padding: 10px; display: flex; flex-direction: column; gap: 4px; }
.kpi-card span { color: #6b7280; font-size: 12px; }
.ops-tabs { display: flex; gap: 8px; }
.ops-tabs .active { background: #e5e7eb; font-weight: 700; }
.info-block { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
.block-title { font-weight: 700; margin-bottom: 6px; }
.muted { color: #6b7280; }
.status-line { display: flex; gap: 8px; margin-bottom: 4px; }
.actions-row { display: flex; gap: 8px; }
</style>
