<template>
  <div class="dash">
    <div v-if="loading" class="dash-loading">불러오는 중…</div>
    <template v-else>
      <header class="dash-top">
        <div>
          <h1 class="dash-title">안전 운영 현황</h1>
          <p class="dash-sub">문서·의견·현장 요약</p>
        </div>
        <div class="dash-top-actions">
          <button type="button" class="btn-ghost btn-ghost-warn" @click="goApprovals">미결재 알림</button>
          <button type="button" class="btn-ghost" @click="goDocuments">보고서·문서함</button>
        </div>
      </header>

      <section class="work-entry-section" aria-labelledby="work-entry-title">
        <div class="work-entry-heading">
          <div>
            <p class="work-entry-kicker">본사 주요 업무</p>
            <h2 id="work-entry-title">업무를 선택하세요</h2>
          </div>
          <p>모바일에서는 사진 촬영이 필요한 업무를 먼저 표시합니다.</p>
        </div>
        <div class="work-entry-grid">
          <RouterLink class="work-entry-card entry-documents" :to="{ name: 'hq-safe-documents' }">
            <span class="work-entry-icon" aria-hidden="true">📚</span>
            <span><strong>문서취합</strong><small>현장 문서 제출·검토 현황</small></span>
            <b aria-hidden="true">→</b>
          </RouterLink>
          <RouterLink class="work-entry-card entry-functional" :to="{ name: 'hq-safe-functional-eval' }">
            <span class="work-entry-icon" aria-hidden="true">🦺</span>
            <span><strong>기능인인정제</strong><small>기능인 평가·승인 업무</small></span>
            <b aria-hidden="true">→</b>
          </RouterLink>
          <RouterLink class="work-entry-card entry-card" :to="{ name: 'hq-safe-card-expenses' }">
            <span class="work-entry-icon" aria-hidden="true">🧾</span>
            <span><strong>법인카드</strong><small>영수증 촬영·정산서 작성</small></span>
            <b aria-hidden="true">→</b>
          </RouterLink>
          <RouterLink class="work-entry-card entry-vehicle" :to="{ name: 'hq-safe-vehicle-logs' }">
            <span class="work-entry-icon" aria-hidden="true">🚙</span>
            <span><strong>운행기록부</strong><small>계기판 촬영·주행 기록</small></span>
            <b aria-hidden="true">→</b>
          </RouterLink>
        </div>
      </section>

      <section v-if="riskDbOverview" class="dash-alerts" aria-labelledby="dash-alerts-title">
        <h2 id="dash-alerts-title" class="dash-alerts-title">처리 필요 알림</h2>
        <p class="dash-alerts-sub">관리대장 전용 — 위험성평가 DB 등록 요청·본사 판단 (문서취합 알림과 별도)</p>
        <BaseCard class="summary-group-card risk-ledger-split-card">
          <div class="risk-ledger-split">
            <div class="risk-ledger-section">
              <h3 class="risk-ledger-section-title">근로자의견청취</h3>
              <p class="risk-ledger-section-sub">본사에서 확인할 DB 관련 건입니다. 카드를 누르면 관리대장 목록으로 이동합니다.</p>
              <div class="risk-db-kpi-grid">
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('db_pending', 'voice')"
                  @keydown.enter="goHqLedgerFilter('db_pending', 'voice')"
                >
                  <span class="risk-db-kpi-title">DB 등록 승인 대기</span>
                  <strong>{{ riskDbOverview.hq.worker_voice.pending_approval }}</strong>
                  <small class="risk-db-kpi-hint">본사 승인 필요</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('db_requests', 'voice')"
                  @keydown.enter="goHqLedgerFilter('db_requests', 'voice')"
                >
                  <span class="risk-db-kpi-title">DB 등록 요청 건</span>
                  <strong>{{ riskDbOverview.hq.worker_voice.pending_requests }}</strong>
                  <small class="risk-db-kpi-hint">요청 접수·검토 대상</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('rejected', 'voice')"
                  @keydown.enter="goHqLedgerFilter('rejected', 'voice')"
                >
                  <span class="risk-db-kpi-title">DB 반려 건</span>
                  <strong>{{ riskDbOverview.hq.worker_voice.rejected }}</strong>
                  <small class="risk-db-kpi-hint">재검토·현장 안내</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('reward', 'voice')"
                  @keydown.enter="goHqLedgerFilter('reward', 'voice')"
                >
                  <span class="risk-db-kpi-title">포상 후보</span>
                  <strong>{{ riskDbOverview.hq.worker_voice.reward_candidates }}</strong>
                  <small class="risk-db-kpi-hint">포상 검토 대상</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('db_confirmed', 'voice')"
                  @keydown.enter="goHqLedgerFilter('db_confirmed', 'voice')"
                >
                  <span class="risk-db-kpi-title">DB 승격 확정</span>
                  <strong>{{ riskDbOverview.hq.worker_voice.approved }}</strong>
                  <small class="risk-db-kpi-hint">승격 조건 충족(자동 DB 반영 아님)</small>
                </div>
              </div>
            </div>
            <div class="risk-ledger-divider" aria-hidden="true" />
            <div class="risk-ledger-section">
              <h3 class="risk-ledger-section-title">부적합사항</h3>
              <p class="risk-ledger-section-sub">본사에서 확인할 DB 관련 건입니다. 카드를 누르면 관리대장 목록으로 이동합니다.</p>
              <div class="risk-db-kpi-grid">
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('db_pending', 'nonconf')"
                  @keydown.enter="goHqLedgerFilter('db_pending', 'nonconf')"
                >
                  <span class="risk-db-kpi-title">DB 등록 승인 대기</span>
                  <strong>{{ riskDbOverview.hq.nonconformity.pending_approval }}</strong>
                  <small class="risk-db-kpi-hint">본사 승인 필요</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('db_requests', 'nonconf')"
                  @keydown.enter="goHqLedgerFilter('db_requests', 'nonconf')"
                >
                  <span class="risk-db-kpi-title">DB 등록 요청 건</span>
                  <strong>{{ riskDbOverview.hq.nonconformity.pending_requests }}</strong>
                  <small class="risk-db-kpi-hint">요청 접수·검토 대상</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('rejected', 'nonconf')"
                  @keydown.enter="goHqLedgerFilter('rejected', 'nonconf')"
                >
                  <span class="risk-db-kpi-title">DB 반려 건</span>
                  <strong>{{ riskDbOverview.hq.nonconformity.rejected }}</strong>
                  <small class="risk-db-kpi-hint">재검토·현장 안내</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('reward', 'nonconf')"
                  @keydown.enter="goHqLedgerFilter('reward', 'nonconf')"
                >
                  <span class="risk-db-kpi-title">포상 후보</span>
                  <strong>{{ riskDbOverview.hq.nonconformity.reward_candidates }}</strong>
                  <small class="risk-db-kpi-hint">포상 검토 대상</small>
                </div>
                <div
                  class="risk-db-kpi-card risk-db-kpi-card--action"
                  role="button"
                  tabindex="0"
                  @click="goHqLedgerFilter('db_confirmed', 'nonconf')"
                  @keydown.enter="goHqLedgerFilter('db_confirmed', 'nonconf')"
                >
                  <span class="risk-db-kpi-title">DB 승격 확정</span>
                  <strong>{{ riskDbOverview.hq.nonconformity.approved }}</strong>
                  <small class="risk-db-kpi-hint">승격 조건 충족(자동 DB 반영 아님)</small>
                </div>
              </div>
            </div>
          </div>
        </BaseCard>
      </section>

      <section class="summary-groups">
        <BaseCard class="summary-group-card">
          <div class="summary-group-head">
            <div>
              <h2 class="summary-group-title">문서 현황</h2>
              <p class="summary-group-sub">문서 전체 흐름과 결재 대기 상태를 한 번에 봅니다.</p>
            </div>
            <div class="summary-group-actions">
              <button type="button" class="panel-link-btn" @click="goDocuments">문서취합</button>
              <button type="button" class="panel-link-btn" @click="goApprovals">미결재</button>
            </div>
          </div>
          <div class="doc-metric-grid">
            <article class="doc-metric-card tone-blue">
              <span>전체 문서</span>
              <strong>{{ data?.total_documents ?? "—" }}</strong>
              <small>처리 여유 {{ docHealthPct }}%</small>
            </article>
            <article class="doc-metric-card tone-orange">
              <span>검토 대기</span>
              <strong>{{ data?.pending_documents ?? "—" }}</strong>
              <small>전체 대비 {{ pendingRatioPct }}%</small>
            </article>
            <article class="doc-metric-card tone-red">
              <span>반려 문서</span>
              <strong>{{ data?.rejected_documents ?? "—" }}</strong>
              <small>전체 대비 {{ rejectedRatioPct }}%</small>
            </article>
          </div>
        </BaseCard>

        <BaseCard class="summary-group-card">
          <div class="summary-group-head">
            <div>
              <h2 class="summary-group-title">문서 취합 / 제안</h2>
              <p class="summary-group-sub">근로자의견·부적합은 사이드 메뉴 대신 문서 취합 현황·아래 바로가기에서 엽니다.</p>
            </div>
          </div>
          <div class="ledger-card-grid">
            <button type="button" class="ledger-nav-card" @click="goWorkerVoice">
              <span>근로자의견청취</span>
              <strong>{{ data?.worker_voice_items ?? "—" }}</strong>
              <small>누적 row 건수</small>
            </button>
            <button type="button" class="ledger-nav-card" @click="goNonconformities">
              <span>부적합사항</span>
              <strong>{{ data?.nonconformity_items ?? "—" }}</strong>
              <small>누적 row 건수</small>
            </button>
            <button type="button" class="ledger-nav-card" @click="goOpinions">
              <span>운영 아이디어 제안</span>
              <strong>{{ data?.total_opinions ?? "—" }}</strong>
              <small>미조치 {{ data?.pending_opinions ?? "—" }}건</small>
            </button>
          </div>
        </BaseCard>

      </section>

      <FilterBar class="filter-bar">
        <select v-model="filterSiteId" class="filter-control">
          <option value="">전체 현장</option>
          <option v-for="s in sites" :key="s.id" :value="String(s.id)">{{ s.site_name }}</option>
        </select>
        <select v-model="filterSiteStatus" class="filter-control">
          <option value="ALL">현장 상태 전체</option>
          <option value="IN_PROGRESS">진행</option>
          <option value="STOPPED">중지</option>
          <option value="COMPLETED">준공</option>
          <option value="UNKNOWN">데이터 없음</option>
        </select>
        <select v-model="filterTeamDraft" class="filter-control filter-team">
          <option value="">팀·조직 전체</option>
          <optgroup v-if="teamOptionsWork.length" label="공종·업무 (현장 work_types)">
            <option v-for="o in teamOptionsWork" :key="o.value" :value="o.value">{{ o.label }}</option>
          </optgroup>
          <optgroup v-if="teamOptionsContractor.length" label="시공사 (contractor)">
            <option v-for="o in teamOptionsContractor" :key="o.value" :value="o.value">{{ o.label }}</option>
          </optgroup>
        </select>
        <div class="filter-search-wrap">
          <input v-model="filterKeyword" type="search" class="filter-control filter-search" placeholder="현장명·코드 검색" />
        </div>
        <button type="button" class="filter-apply" @click="applyTeamFilter">필터 적용</button>
      </FilterBar>
      <p v-if="filterTeamApplied" class="filter-active-hint">
        팀·조직 필터 적용 중:
        <strong>{{ teamAppliedLabel }}</strong>
      </p>

      <div class="main-grid">
        <BaseCard class="panel-sites mb-5" title="현장 모니터링">
          <template #actions>
            <RouterLink class="panel-link" :to="{ name: 'hq-safe-sites' }">전체 보기</RouterLink>
          </template>
          <div class="site-card-grid">
            <SiteCard
              v-for="site in monitoringSiteCards"
              :key="site.id"
              :site-name="site.site_name"
              :site-code="site.site_code"
              :compliance="complianceForSite(site.id)"
              :not-submitted="siteDocSummary(site.id).ns"
              :rejected="siteDocSummary(site.id).rej"
            />
            <div v-if="monitoringSiteCards.length === 0" class="empty-sites">조건에 맞는 현장이 없습니다.</div>
          </div>
        </BaseCard>

        <aside class="panel-side">
          <SummaryPanel :opinions="recentOpinions" :top-sites-by-docs="topSitesByDocs" />
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api } from "@/services/api";
import { fetchRiskDbOverviewOptional, type RiskDbOverviewPayload } from "@/services/riskDbOverview";
import type { LedgerDashboardFilter } from "@/utils/ledgerDashboardFilter";
import {
  BaseCard,
  FilterBar,
  SiteCard,
  SummaryPanel,
} from "@/components/product";
import { todayKst } from "@/utils/datetime";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
  rejected_documents: number;
  total_opinions: number;
  pending_opinions: number;
  worker_voice_items: number;
  nonconformity_items: number;
  documents_by_site: { site_id: number | null; count: number }[];
}

interface SiteRow {
  id: number;
  site_code: string;
  site_name: string;
  status: string | null;
  address: string | null;
  work_types?: string | null;
  contractor_name?: string | null;
}

interface DashboardSiteSummary {
  site_id: number;
  not_submitted_count: number;
  rejected_count: number;
}

interface OpinionRow {
  id: number;
  site_id: number;
  category: string;
  content: string;
  status: string;
  created_at?: string;
}

const router = useRouter();
const loading = ref(true);
const data = ref<DashboardSummary | null>(null);
const sites = ref<SiteRow[]>([]);
const siteSummaryMap = ref<Record<number, DashboardSiteSummary>>({});
const recentOpinions = ref<OpinionRow[]>([]);
const riskDbOverview = ref<RiskDbOverviewPayload | null>(null);

const filterSiteId = ref("");
const filterSiteStatus = ref<"ALL" | "IN_PROGRESS" | "STOPPED" | "COMPLETED" | "UNKNOWN">("ALL");
const filterKeyword = ref("");
/** 팀·조직: 선택값은 적용 버튼 후 반영 */
const filterTeamDraft = ref("");
const filterTeamApplied = ref("");

const totalDocs = computed(() => data.value?.total_documents ?? 0);
const pendingDocs = computed(() => data.value?.pending_documents ?? 0);
const rejectedDocs = computed(() => data.value?.rejected_documents ?? 0);
const totalOpinions = computed(() => data.value?.total_opinions ?? 0);

const docHealthPct = computed(() => {
  const t = totalDocs.value;
  if (t <= 0) return 100;
  const p = Math.round(((t - pendingDocs.value - rejectedDocs.value) / t) * 100);
  return Math.max(0, Math.min(100, p));
});

const pendingRatioPct = computed(() => {
  const t = totalDocs.value;
  if (t <= 0) return 0;
  return Math.min(100, Math.round((pendingDocs.value / t) * 100));
});

const rejectedRatioPct = computed(() => {
  const t = totalDocs.value;
  if (t <= 0) return 0;
  return Math.min(100, Math.round((rejectedDocs.value / t) * 100));
});

const siteNameById = computed(() => {
  const m = new Map<number, string>();
  for (const s of sites.value) m.set(s.id, s.site_name);
  return m;
});

function splitWorkTypeTags(raw: string | null | undefined): string[] {
  if (!raw?.trim()) return [];
  return raw
    .split(/[,，、;/|]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

const teamOptionsWork = computed(() => {
  const set = new Set<string>();
  for (const s of sites.value) {
    for (const t of splitWorkTypeTags(s.work_types)) set.add(t);
  }
  return [...set]
    .sort()
    .map((label) => ({ value: `wt:${label}`, label }));
});

const teamOptionsContractor = computed(() => {
  const set = new Set<string>();
  for (const s of sites.value) {
    const c = s.contractor_name?.trim();
    if (c) set.add(c);
  }
  return [...set]
    .sort()
    .map((label) => ({ value: `ct:${label}`, label }));
});

const teamAppliedLabel = computed(() => {
  const key = filterTeamApplied.value;
  if (!key) return "";
  if (key.startsWith("wt:")) return `공종·업무: ${key.slice(3)}`;
  if (key.startsWith("ct:")) return `시공사: ${key.slice(3)}`;
  return key;
});

function siteMatchesAppliedTeam(s: SiteRow): boolean {
  const key = filterTeamApplied.value;
  if (!key) return true;
  if (key.startsWith("wt:")) {
    const tag = key.slice(3);
    return splitWorkTypeTags(s.work_types).some((t) => t === tag);
  }
  if (key.startsWith("ct:")) {
    const name = key.slice(3);
    return (s.contractor_name || "").trim() === name;
  }
  return true;
}

function normalizeStatusCategory(status: string | null) {
  const value = (status || "").toUpperCase();
  if (value === "ACTIVE" || value === "IN_PROGRESS") return "IN_PROGRESS";
  if (value === "STOPPED" || value === "PAUSED") return "STOPPED";
  if (value === "COMPLETED" || value === "DONE" || value === "CLOSED") return "COMPLETED";
  return "UNKNOWN";
}

const filteredSites = computed(() => {
  let rows = sites.value;
  if (filterSiteId.value) {
    const id = Number(filterSiteId.value);
    rows = rows.filter((s) => s.id === id);
  }
  if (filterSiteStatus.value !== "ALL") {
    rows = rows.filter((s) => normalizeStatusCategory(s.status) === filterSiteStatus.value);
  }
  rows = rows.filter((s) => siteMatchesAppliedTeam(s));
  const q = filterKeyword.value.trim().toLowerCase();
  if (q) {
    rows = rows.filter((s) => `${s.site_name} ${s.site_code}`.toLowerCase().includes(q));
  }
  return rows;
});

const monitoringSiteCards = computed(() => {
  return filteredSites.value;
});

const topSitesByDocs = computed(() => {
  const rows = data.value?.documents_by_site || [];
  const visibleIds = new Set(monitoringSiteCards.value.map((s) => s.id));
  const withNames = rows
    .filter((r) => r.site_id != null && visibleIds.has(r.site_id as number))
    .map((r) => ({
      site_id: r.site_id as number,
      count: r.count,
      name: siteNameById.value.get(r.site_id as number) || `현장 #${r.site_id}`,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);
  const max = withNames.reduce((m, r) => Math.max(m, r.count), 0) || 1;
  return withNames.map((r) => ({ ...r, pct: Math.round((r.count / max) * 100) }));
});

function complianceForSite(siteId: number) {
  const s = siteSummaryMap.value[siteId];
  const score = Math.max(0, Math.min(100, Math.round(s?.submission_rate ?? 0)));
  if (score >= 90) return { pct: score, label: "양호", tone: "safe" as const };
  if (score >= 70) return { pct: score, label: "주의", tone: "warn" as const };
  return { pct: score, label: "위험", tone: "danger" as const };
}

function siteDocSummary(siteId: number) {
  const s = siteSummaryMap.value[siteId];
  return { ns: s?.not_submitted_count ?? 0, rej: s?.rejected_count ?? 0 };
}

function applyTeamFilter() {
  filterTeamApplied.value = filterTeamDraft.value;
}

function goDocuments() {
  router.push({ name: "hq-safe-documents" });
}

function goApprovals() {
  router.push({ name: "hq-safe-approval-inbox" });
}

function goWorkerVoice() {
  router.push({ name: "hq-safe-worker-voice" });
}

function goNonconformities() {
  router.push({ name: "hq-safe-nonconformities" });
}

function goOpinions() {
  router.push({ name: "hq-safe-opinions" });
}

function goHqLedgerFilter(filter: LedgerDashboardFilter, board: "voice" | "nonconf") {
  const name = board === "voice" ? "hq-safe-worker-voice" : "hq-safe-nonconformities";
  router.push({ name, query: { filter } });
}

async function load() {
  loading.value = true;
  try {
    const today = todayKst();
    const dashParams: Record<string, string> = { period: "day", date: today };
    const riskDeferred = fetchRiskDbOverviewOptional();
    const settled = await Promise.allSettled([
      api.get<DashboardSummary>("/dashboard/summary"),
      api.get<SiteRow[]>("/sites"),
      api.get("/documents/hq-dashboard", { params: dashParams }),
      api.get<OpinionRow[]>("/opinions"),
    ]);

    const [sumRes, sitesRes, dashRes, opRes] = settled;

    if (sumRes.status === "fulfilled") {
      data.value = sumRes.value.data;
    } else {
      data.value = null;
    }

    if (sitesRes.status === "fulfilled") {
      sites.value = sitesRes.value.data || [];
    } else {
      sites.value = [];
    }

    if (dashRes.status === "fulfilled") {
      siteSummaryMap.value = Object.fromEntries(
        ((dashRes.value.data as { site_summaries?: DashboardSiteSummary[] }).site_summaries || []).map((x) => [
          x.site_id,
          x,
        ]),
      );
    } else {
      siteSummaryMap.value = {};
    }

    if (opRes.status === "fulfilled") {
      recentOpinions.value = (opRes.value.data || []).slice(0, 8);
    } else {
      recentOpinions.value = [];
    }

    riskDbOverview.value = await riskDeferred;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.dash {
  width: 100%;
  max-width: none;
  margin: 0;
  box-sizing: border-box;
}

.dash-alerts {
  margin-bottom: 20px;
}

.dash-alerts-title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.dash-alerts-sub {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.dash-loading {
  padding: 48px;
  text-align: center;
  color: #64748b;
  font-size: 15px;
}

.dash-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}

.dash-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.dash-sub {
  margin: 6px 0 0;
  font-size: 14px;
  color: #64748b;
}

.work-entry-section {
  margin-bottom: 24px;
  padding: 22px;
  border: 1px solid #dce6ec;
  border-radius: 20px;
  background: linear-gradient(145deg, #f8fbfc, #eef7f5);
}

.work-entry-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.work-entry-heading h2,
.work-entry-heading p { margin: 0; }
.work-entry-heading h2 { color: #142033; font-size: 21px; }
.work-entry-heading > p { color: #64748b; font-size: 13px; }
.work-entry-kicker {
  margin-bottom: 4px !important;
  color: #0f6b6d;
  font-size: 12px;
  font-weight: 800;
}

.work-entry-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.work-entry-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 11px;
  min-height: 92px;
  padding: 16px;
  border: 1px solid #d5e0e6;
  border-radius: 16px;
  color: #142033;
  text-decoration: none;
  background: #fff;
  box-shadow: 0 7px 20px rgba(31, 53, 71, .06);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
}

.work-entry-card:hover,
.work-entry-card:focus-visible {
  transform: translateY(-2px);
  border-color: #4f8790;
  box-shadow: 0 11px 24px rgba(31, 53, 71, .11);
}

.work-entry-card > span:not(.work-entry-icon) { display: grid; gap: 4px; }
.work-entry-card strong { font-size: 17px; }
.work-entry-card small { color: #64748b; font-size: 12px; line-height: 1.4; }
.work-entry-card > b { color: #0f6b6d; font-size: 20px; }
.work-entry-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 13px;
  background: #e8f7f4;
  font-size: 22px;
}

.summary-groups {
  display: grid;
  gap: 16px;
  margin-bottom: 20px;
}

.summary-group-card {
  border-radius: 18px;
}

.summary-group-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.summary-group-title {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.summary-group-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}

.summary-group-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-link-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.doc-metric-grid,
.ledger-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.doc-metric-card,
.ledger-nav-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.doc-metric-card span,
.ledger-nav-card span {
  font-size: 12px;
  color: #475569;
  font-weight: 700;
}

.doc-metric-card strong,
.ledger-nav-card strong {
  font-size: 28px;
  color: #0f172a;
}

.doc-metric-card small,
.ledger-nav-card small {
  font-size: 12px;
  color: #64748b;
}

.tone-blue { background: #f8fbff; }
.tone-orange { background: #fff7ed; }
.tone-red { background: #fef2f2; }

.ledger-nav-card {
  cursor: pointer;
  text-align: left;
}

.ledger-nav-card:hover,
.panel-link-btn:hover {
  filter: brightness(0.98);
}

.risk-ledger-split-card {
  overflow: visible;
}

.risk-ledger-split {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 960px) {
  .risk-ledger-split {
    grid-template-columns: 1fr;
  }

  .risk-ledger-divider {
    width: 100%;
    height: 1px;
    min-height: 0;
  }
}

.risk-ledger-section-title {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.risk-ledger-section-sub {
  margin: 0 0 12px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

.risk-ledger-divider {
  width: 1px;
  min-height: 120px;
  background: linear-gradient(to bottom, transparent, #e2e8f0 12%, #e2e8f0 88%, transparent);
  align-self: stretch;
}

.risk-db-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.risk-db-kpi-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 12px 14px 10px;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  text-align: left;
}

.risk-db-kpi-card:hover {
  border-color: #cbd5e1;
  background: #fff;
}

.risk-db-kpi-card--action:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

.risk-db-kpi-title {
  font-size: 12px;
  color: #475569;
  font-weight: 700;
}

.risk-db-kpi-card strong {
  font-size: 24px;
  color: #0f172a;
}

.risk-db-kpi-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.35;
  margin-top: 2px;
}

.dash-top-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.btn-ghost {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: #fff;
  color: #334155;
}

.btn-ghost:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.btn-ghost-warn {
  border-color: #fecaca;
  color: #b91c1c;
}

.btn-ghost-warn:hover {
  background: #fef2f2;
}

.filter-bar {
  margin-bottom: 8px;
}

.filter-active-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: #64748b;
}

.filter-active-hint strong {
  color: #0f172a;
}

.filter-team {
  min-width: 200px;
  max-width: 280px;
}

.filter-control {
  border: 2px solid #cbd5e1;
  border-radius: 10px;
  padding: 8px 12px;
  min-height: 44px;
  line-height: 1.35;
  font-size: 14px;
  font-weight: 600;
  background: #fff;
  color: #0f172a;
  min-width: 160px;
}

select.filter-control {
  -webkit-text-fill-color: #0f172a;
}

select.filter-control option {
  color: #0f172a;
}

.filter-search-wrap {
  flex: 1;
  min-width: 200px;
}

.filter-search {
  width: 100%;
  min-width: 0;
}

.filter-apply {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  background: #fff;
  color: #475569;
}

.filter-apply:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, min(20vw, 320px));
  gap: 20px;
  align-items: start;
}

.panel-link {
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  text-decoration: none;
}

button.panel-link {
  cursor: pointer;
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
}

.panel-link:hover {
  text-decoration: underline;
}

.site-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr));
  gap: 16px;
}

.empty-sites {
  grid-column: 1 / -1;
  text-align: center;
  padding: 32px;
  color: #64748b;
  font-size: 14px;
}

.panel-side {
  display: flex;
  flex-direction: column;
  gap: 0;
}

@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: minmax(0, 1fr) minmax(220px, 260px);
  }
}

@media (max-width: 1024px) {
  .work-entry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .main-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dash-top {
    flex-direction: column;
  }

  .work-entry-section { padding: 16px; }
  .work-entry-heading { display: block; }
  .work-entry-heading > p { margin-top: 6px; }
  .work-entry-grid { grid-template-columns: 1fr; }
  .work-entry-card { min-height: 84px; }
  .entry-functional { order: 1; }
  .entry-card { order: 2; }
  .entry-vehicle { order: 3; }
  .entry-documents { order: 4; }
}
</style>
