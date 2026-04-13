<template>
  <div class="dash">
    <div v-if="loading" class="dash-loading">불러오는 중…</div>
    <template v-else>
      <header class="dash-top">
        <div>
          <h1 class="dash-title">안전 운영 현황</h1>
          <p class="dash-sub">문서·의견·현장 요약 (기상은 1일 2회 스냅샷: 05:00·12:00 KST)</p>
        </div>
        <div class="dash-top-actions">
          <button type="button" class="btn-ghost btn-ghost-warn" @click="goApprovals">미결재 알림</button>
          <button type="button" class="btn-ghost" @click="goDocuments">보고서·문서함</button>
        </div>
      </header>

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
              <h2 class="summary-group-title">관리대장 / 제안</h2>
              <p class="summary-group-sub">주요 운영 메뉴로 바로 이동할 수 있습니다.</p>
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

        <BaseCard class="summary-group-card">
          <div class="summary-group-head">
            <div>
              <h2 class="summary-group-title">기상 현황</h2>
              <p class="summary-group-sub">본사·현장 기상은 Open-Meteo 스냅샷(05:00·12:00 KST 앵커)으로 갱신되며, 동일 앵커 구간에서는 디스크에 저장된 마지막 조회 결과를 보여줍니다.</p>
            </div>
          </div>
          <div class="weather-overview">
            <div class="weather-office-card">
              <span class="weather-overview-label">본사</span>
              <strong>{{ officeTitle }}</strong>
              <p class="weather-overview-sub">{{ officeSummary }}</p>
              <p class="weather-overview-updated">
                패널 기준 최종 갱신: {{ formatDateTimeKst(weatherOverview?.snapshot_fetched_at || weatherOverview?.updated_at, "업데이트 정보 없음") }}
              </p>
              <p class="weather-overview-snapshot">
                스냅샷 기준(KST): {{ formatDateTimeKst(weatherOverview?.office?.snapshot_anchor_kst || weatherOverview?.snapshot_anchor_kst, "—") }}
                <span class="weather-overview-sep">·</span>
                본사 조회 갱신: {{ formatDateTimeKst(weatherOverview?.office?.snapshot_fetched_at || weatherOverview?.office?.updated_at, "—") }}
              </p>
            </div>
            <ul class="weather-site-list">
              <li v-for="site in weatherOverview?.sites || []" :key="site.site_id || site.location_name">
                <div class="weather-site-head">
                  <strong>{{ site.location_name }}</strong>
                  <span class="weather-chip" :class="chipTone(site)">{{ headlineStatus(site) }}</span>
                </div>
                <p>{{ site.summary_text }}</p>
              </li>
              <li v-if="(weatherOverview?.sites || []).length === 0" class="weather-empty-item">
                표시할 현장 기상 요약이 없습니다.
              </li>
            </ul>
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
import { formatDateTimeKst, todayKst } from "@/utils/datetime";

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

interface WeatherOverviewSite {
  available: boolean;
  location_name: string;
  site_id?: number | null;
  summary_text: string;
  pm10_status: string;
  pm25_status: string;
  advisory_flags: string[];
  warning_score: number;
  snapshot_anchor_kst?: string | null;
  snapshot_fetched_at?: string | null;
  updated_at?: string | null;
}

interface WeatherOverview {
  office: {
    available: boolean;
    location_name: string;
    weather_label?: string;
    temperature?: number | null;
    status_text?: string;
    updated_at?: string | null;
    snapshot_anchor_kst?: string | null;
    snapshot_fetched_at?: string | null;
  };
  sites: WeatherOverviewSite[];
  updated_at: string | null;
  snapshot_anchor_kst?: string | null;
  snapshot_fetched_at?: string | null;
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
const weatherOverview = ref<WeatherOverview | null>(null);
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

const officeTitle = computed(() => {
  const office = weatherOverview.value?.office;
  if (!office) return "정보 없음";
  if (!office.available) return office.location_name || "본사";
  const temp = office.temperature == null ? "—" : `${Math.round(office.temperature)}℃`;
  return `${office.location_name} ${temp}`;
});

const officeSummary = computed(() => {
  const office = weatherOverview.value?.office;
  if (!office) return "기상 정보 없음";
  if (!office.available) return office.status_text || "본사 위치 미설정";
  return office.weather_label || "기상 정보";
});

function headlineStatus(site: WeatherOverviewSite) {
  if (!site.available) return "정보 없음";
  const flags = site.advisory_flags || [];
  if (site.pm25_status === "매우나쁨" || site.pm10_status === "매우나쁨") return "매우나쁨";
  if (site.pm25_status === "나쁨" || site.pm10_status === "나쁨") return "미세먼지 주의";
  if (flags.includes("WIND")) return "강풍 주의";
  if (flags.includes("RAIN")) return "우천 주의";
  return "정상";
}

function chipTone(site: WeatherOverviewSite) {
  const status = headlineStatus(site);
  if (status === "매우나쁨") return "chip-bad";
  if (status === "미세먼지 주의" || status === "강풍 주의" || status === "우천 주의") return "chip-warn";
  return "chip-good";
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
      api.get<WeatherOverview>("/dashboard/weather/hq-overview"),
    ]);

    const [sumRes, sitesRes, dashRes, opRes, weatherRes] = settled;

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

    if (weatherRes.status === "fulfilled") {
      weatherOverview.value = weatherRes.value.data;
    } else {
      weatherOverview.value = {
        office: {
          available: false,
          location_name: "본사",
          status_text: "일시적 조회 실패",
          snapshot_anchor_kst: null,
          snapshot_fetched_at: null,
        },
        sites: [],
        updated_at: null,
        snapshot_anchor_kst: null,
        snapshot_fetched_at: null,
      };
    }
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

.weather-overview {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.1fr);
  gap: 12px;
}

.weather-office-card {
  border: 1px solid #dbeafe;
  background: #f8fbff;
  border-radius: 14px;
  padding: 14px;
  display: grid;
  gap: 6px;
}

.weather-overview-label,
.weather-overview-updated {
  font-size: 12px;
  color: #64748b;
}

.weather-office-card strong {
  font-size: 24px;
  color: #0f172a;
}

.weather-overview-sub {
  margin: 0;
  color: #334155;
  font-size: 13px;
}

.weather-overview-snapshot {
  margin: 0;
  font-size: 12px;
  color: #475569;
  line-height: 1.45;
}

.weather-overview-sep {
  margin: 0 6px;
  color: #94a3b8;
}

.weather-site-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}

.weather-site-list li {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
}

.weather-site-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.weather-site-list p {
  margin: 0;
  font-size: 13px;
  color: #475569;
}

.weather-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
}

.chip-good {
  background: #dcfce7;
  color: #166534;
}

.chip-warn {
  background: #ffedd5;
  color: #c2410c;
}

.chip-bad {
  background: #fee2e2;
  color: #b91c1c;
}

.weather-empty-item {
  color: #64748b;
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
  .weather-overview {
    grid-template-columns: 1fr;
  }

  .main-grid {
    grid-template-columns: minmax(0, 1fr) minmax(220px, 260px);
  }
}

@media (max-width: 1024px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dash-top {
    flex-direction: column;
  }
}
</style>
