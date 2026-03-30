<template>
  <div class="dash">
    <div v-if="loading" class="dash-loading">불러오는 중…</div>
    <template v-else>
      <header class="dash-top">
        <div>
          <h1 class="dash-title">안전 운영 현황</h1>
          <p class="dash-sub">문서·의견·현장 요약 (실시간 API 기준)</p>
        </div>
        <div class="dash-top-actions">
          <button type="button" class="btn-ghost btn-ghost-warn" @click="goApprovals">미결재 알림</button>
          <button type="button" class="btn-ghost" @click="goDocuments">보고서·문서함</button>
        </div>
      </header>

      <section class="stitch-kpi-grid">
        <KpiCard
          label="전체 문서"
          :value="data?.total_documents ?? '—'"
          accent="blue"
          :progress-pct="docHealthPct"
          :footer-note="`처리 여유 ${docHealthPct}%`"
          :badge-text="docHealthPct >= 85 ? '양호' : docHealthPct >= 60 ? '주의' : '점검'"
          :badge-tone="docHealthPct >= 85 ? 'success' : docHealthPct >= 60 ? 'warn' : 'danger'"
        />
        <KpiCard
          label="검토 대기"
          :value="data?.pending_documents ?? '—'"
          accent="orange"
          :progress-pct="pendingRatioPct"
          :footer-note="`전체 대비 ${pendingRatioPct}%`"
          :badge-text="pendingRatioPct > 20 ? '집중' : '정상'"
          :badge-tone="pendingRatioPct > 20 ? 'warn' : 'neutral'"
        />
        <KpiCard
          label="반려 문서"
          :value="data?.rejected_documents ?? '—'"
          accent="red"
          :progress-pct="rejectedRatioPct"
          :footer-note="`전체 대비 ${rejectedRatioPct}%`"
          :badge-text="rejectedDocs > 0 ? '재검토' : '없음'"
          :badge-tone="rejectedDocs > 0 ? 'danger' : 'success'"
        />
        <KpiCard
          label="의견 미조치"
          :value="data?.pending_opinions ?? '—'"
          accent="slate"
          :progress-pct="opinionPendingPct"
          :footer-note="`의견 대비 ${opinionPendingPct}%`"
          :badge-text="pendingOpinions > 0 ? '조치 필요' : '없음'"
          :badge-tone="pendingOpinions > 0 ? 'warn' : 'success'"
        />
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
            <button
              v-if="isDemoPilotSiteScopeEnabled"
              type="button"
              class="panel-link"
              @click="toggleMonitoringSitesExpand"
            >
              {{ showAllMonitoringSites ? "파일럿만" : "다른 현장 보기" }}
            </button>
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
import { DEMO_PILOT_SITE_CODE, isDemoPilotSiteScopeEnabled } from "@/config/demoPilotSite";
import {
  BaseCard,
  FilterBar,
  KpiCard,
  SiteCard,
  SummaryPanel,
} from "@/components/product";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
  rejected_documents: number;
  total_opinions: number;
  pending_opinions: number;
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

const filterSiteId = ref("");
const filterSiteStatus = ref<"ALL" | "IN_PROGRESS" | "STOPPED" | "COMPLETED" | "UNKNOWN">("ALL");
const filterKeyword = ref("");
/** 팀·조직: 선택값은 적용 버튼 후 반영 */
const filterTeamDraft = ref("");
const filterTeamApplied = ref("");

/** 데모: 홈 모니터링 카드는 기본 파일럿만, 클릭 시 전체 */
const showAllMonitoringSites = ref(false);

function toggleMonitoringSitesExpand() {
  showAllMonitoringSites.value = !showAllMonitoringSites.value;
  void load();
}

const totalDocs = computed(() => data.value?.total_documents ?? 0);
const pendingDocs = computed(() => data.value?.pending_documents ?? 0);
const rejectedDocs = computed(() => data.value?.rejected_documents ?? 0);
const totalOpinions = computed(() => data.value?.total_opinions ?? 0);
const pendingOpinions = computed(() => data.value?.pending_opinions ?? 0);

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

const opinionPendingPct = computed(() => {
  const t = totalOpinions.value;
  if (t <= 0) return 0;
  return Math.min(100, Math.round((pendingOpinions.value / t) * 100));
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
  const base = filteredSites.value;
  if (!isDemoPilotSiteScopeEnabled || showAllMonitoringSites.value) return base;
  return base.filter((s) => s.site_code === DEMO_PILOT_SITE_CODE);
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

async function load() {
  loading.value = true;
  try {
    const today = new Date().toISOString().slice(0, 10);
    const dashParams: Record<string, string> = { period: "day", date: today };
    if (isDemoPilotSiteScopeEnabled && !showAllMonitoringSites.value) {
      dashParams.site_code = DEMO_PILOT_SITE_CODE;
    }
    const [sumRes, sitesRes, dashRes, opRes] = await Promise.all([
      api.get<DashboardSummary>("/dashboard/summary"),
      api.get<SiteRow[]>("/sites"),
      api.get("/documents/hq-dashboard", { params: dashParams }),
      api.get<OpinionRow[]>("/opinions"),
    ]);
    data.value = sumRes.data;
    sites.value = sitesRes.data || [];
    siteSummaryMap.value = Object.fromEntries(
      ((dashRes.data as { site_summaries?: DashboardSiteSummary[] }).site_summaries || []).map((x) => [
        x.site_id,
        x,
      ]),
    );
    recentOpinions.value = (opRes.data || []).slice(0, 8);
  } catch {
    data.value = null;
    sites.value = [];
    siteSummaryMap.value = {};
    recentOpinions.value = [];
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
