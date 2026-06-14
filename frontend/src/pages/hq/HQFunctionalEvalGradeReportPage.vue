<template>
  <div class="report-page">
    <div class="report-toolbar no-print">
      <RouterLink class="secondary-link" :to="{ name: 'hq-safe-functional-eval' }">
        기능인제 본사로 돌아가기
      </RouterLink>
      <button type="button" class="secondary" @click="previewPrint">프린터로 출력</button>
    </div>

    <p v-if="loading" class="muted">불러오는 중…</p>
    <p v-else-if="errorMessage" class="error">{{ errorMessage }}</p>

    <article v-else-if="gradeStats" class="report-paper report-print-root">
      <header class="report-header">
        <div>
          <h1>기능인제 등급 통계 보고서</h1>
          <p class="subtitle">BESMA 기능인 인정제 · 본사 출력본</p>
        </div>
        <dl class="header-meta">
          <div>
            <dt>평가기간</dt>
            <dd>{{ periodLabel }}</dd>
          </div>
          <div>
            <dt>출력일시</dt>
            <dd>{{ printedAtLabel }}</dd>
          </div>
          <div v-if="gradeStats.computed_at_label">
            <dt>통계갱신</dt>
            <dd>{{ gradeStats.computed_at_label }}</dd>
          </div>
        </dl>
      </header>

      <p v-if="gradeStats.grade_stats_mode === 'demo'" class="demo-notice">
        {{ gradeStats.grade_stats_mode_label || "데모 등급 분포" }} — 실평가 시작 후 실제 데이터로 전환됩니다.
      </p>

      <section class="report-section">
        <h2>전체 현장 등급 분포</h2>
        <p class="section-note">{{ overallSubtitle }}</p>
        <FeGradeStatsPrintBlock
          :stats="overallStats"
          :donut-size="150"
        />
      </section>

      <section v-if="teamStats.length" class="report-section">
        <h2>팀별 등급 분포</h2>
        <p class="section-note">현장명 [N.시공사] 기준 공사N팀 · 소장 1명 = 현장 1곳</p>
        <div class="team-report-grid">
          <div
            v-for="team in teamStats"
            :key="String(team.team_key)"
            class="team-report-card"
          >
            <FeGradeStatsPrintBlock
              :stats="teamStatsPayload(team)"
              :title="String(team.team_label || team.team_key)"
              :subtitle="teamSubtitle(team)"
              :donut-size="110"
            />
          </div>
        </div>
      </section>

      <section v-if="siteStats.length" class="report-section site-table-section">
        <h2>현장별 등급 요약</h2>
        <table class="site-summary-table">
          <thead>
            <tr>
              <th rowspan="2">현장</th>
              <th rowspan="2">소장</th>
              <th rowspan="2">출역</th>
              <th colspan="4">2-1 기능</th>
              <th colspan="4">2-2 안전</th>
            </tr>
            <tr>
              <th v-for="g in gradeOrder" :key="`fn-h-${g}`">{{ g }}</th>
              <th v-for="g in gradeOrder" :key="`sf-h-${g}`">{{ g }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="site in siteStats" :key="String(site.site_code)">
              <td class="site-name">{{ site.site_name || site.site_code }}</td>
              <td>{{ site.evaluator_name || "—" }}</td>
              <td class="num">{{ siteWorkersTotal(site) }}</td>
              <td v-for="g in gradeOrder" :key="`${site.site_code}-fn-${g}`" class="num">
                {{ siteGradeCount(site, "functional", g) }}
              </td>
              <td v-for="g in gradeOrder" :key="`${site.site_code}-sf-${g}`" class="num">
                {{ siteGradeCount(site, "safety", g) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <footer class="report-footer">
        <p>출력 대상: 안전보건실 · 대표이사 · BESMA 기능인 인정제</p>
      </footer>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import FeGradeStatsPrintBlock from "@/components/functional-eval/FeGradeStatsPrintBlock.vue";
import type { GradeStatsPayload } from "@/components/functional-eval/FeGradeStatsPanel.vue";
import { api } from "@/services/api";
import { formatDateTimeKst } from "@/utils/datetime";
import { loadFeGradeReportCache } from "@/utils/feGradeReportCache";

interface PeriodInfo {
  deadline_date?: string;
  is_closed?: boolean;
  last_attendance_date?: string | null;
  attendance_row_count?: number;
}

type SiteStatRow = Record<string, unknown> & {
  site_code?: string;
  site_name?: string;
  evaluator_name?: string;
  functional?: GradeStatsPayload["functional"];
  safety?: GradeStatsPayload["safety"];
};

const route = useRoute();
const loading = ref(true);
const errorMessage = ref("");
const gradeStats = ref<Record<string, unknown> | null>(null);
const period = ref<PeriodInfo | null>(null);
const gradeOrder = ["S", "A", "B", "C"] as const;

const shouldAutoPrint = computed(() => route.query.autoPrint === "1");

const printedAtLabel = computed(() => formatDateTimeKst(new Date().toISOString(), "—"));

const periodLabel = computed(() => {
  const p = period.value;
  if (!p) return "—";
  const parts: string[] = [];
  if (p.last_attendance_date) {
    parts.push(`출역 ${p.last_attendance_date}`);
    if (p.attendance_row_count != null) parts.push(`${p.attendance_row_count}명`);
  }
  if (p.deadline_date) {
    parts.push(`마감 ${p.deadline_date}${p.is_closed ? " (마감)" : " (진행)"}`);
  }
  return parts.length ? parts.join(" · ") : "—";
});

const overallStats = computed(() => (gradeStats.value?.overall as GradeStatsPayload | undefined) ?? null);

const teamStats = computed(() => {
  const rows = gradeStats.value?.by_team;
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : [];
});

const siteStats = computed(() => {
  const rows = gradeStats.value?.by_site;
  return Array.isArray(rows) ? (rows as SiteStatRow[]) : [];
});

const overallSubtitle = computed(() => {
  const fn = overallStats.value?.functional;
  const workersTotal = Number(fn?.workers_total ?? 0);
  const erpTotal = Number(gradeStats.value?.erp_headcount_total ?? fn?.erp_headcount ?? 0);
  const demo = gradeStats.value?.grade_stats_mode === "demo";
  if (demo) {
    const suffix = erpTotal > 0 && erpTotal !== workersTotal ? ` · ERP ${erpTotal}명` : "";
    return `출역 ${workersTotal}명 · 전원 평가완료(가상)${suffix}`;
  }
  if (erpTotal > 0 && erpTotal !== workersTotal) {
    return `출역 ${workersTotal}명 · ERP ${erpTotal}명`;
  }
  return `출역 ${workersTotal}명`;
});

function teamStatsPayload(team: Record<string, unknown>): GradeStatsPayload {
  return {
    functional: team.functional as GradeStatsPayload["functional"],
    safety: team.safety as GradeStatsPayload["safety"],
  };
}

function teamSubtitle(team: Record<string, unknown>) {
  const sites = Number(team.site_count ?? 0);
  const workers = Number((team.functional as { workers_total?: number } | undefined)?.workers_total ?? 0);
  const labels = team.contractor_labels as string[] | undefined;
  const single = String(team.contractor_label || "").trim();
  let suffix = "";
  if (labels && labels.length > 1) suffix = ` · ${labels.length}개 시공사`;
  else if (single) suffix = ` · ${single}`;
  return `현장 ${sites}곳 · 출역 ${workers}명${suffix}`;
}

function siteWorkersTotal(site: SiteStatRow) {
  return Number(site.functional?.workers_total ?? site.functional?.graded_total ?? 0);
}

function siteGradeCount(site: SiteStatRow, dim: "functional" | "safety", grade: string) {
  const block = dim === "functional" ? site.functional : site.safety;
  return block?.grades?.[grade]?.count ?? 0;
}

function previewPrint() {
  window.print();
}

async function waitForPaint() {
  await nextTick();
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

async function triggerAutoPrint() {
  await waitForPaint();
  window.print();
}

async function loadFromApi() {
  const [statsRes, periodRes] = await Promise.all([
    api.get("/functional-eval/hq/grade-stats"),
    api.get("/functional-eval/period/current"),
  ]);
  gradeStats.value = statsRes.data;
  period.value = periodRes.data ?? null;
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const cached = loadFeGradeReportCache();
    if (cached) {
      gradeStats.value = cached.gradeStats;
      period.value = cached.period;
    } else {
      await loadFromApi();
    }
    if (shouldAutoPrint.value) {
      await triggerAutoPrint();
    }
  } catch {
    errorMessage.value = "등급 통계 보고서 데이터를 불러오지 못했습니다.";
    gradeStats.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.report-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.report-paper {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  padding: 14mm;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  color: #111827;
  box-sizing: border-box;
}
.report-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 2px solid #1f2937;
  padding-bottom: 12px;
}
.report-header h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: 0.02em;
}
.subtitle {
  margin: 6px 0 0;
  color: #4b5563;
  font-size: 13px;
}
.header-meta {
  margin: 0;
  min-width: 240px;
  display: grid;
  gap: 6px;
  font-size: 13px;
}
.header-meta div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
}
.header-meta dt {
  color: #374151;
  font-weight: 700;
}
.header-meta dd {
  margin: 0;
}
.demo-notice {
  margin: 12px 0 0;
  padding: 8px 10px;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 6px;
  font-size: 12px;
  color: #92400e;
}
.report-section {
  margin-top: 20px;
  break-inside: avoid;
}
.report-section h2 {
  margin: 0 0 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid #d1d5db;
  font-size: 17px;
}
.section-note {
  margin: 0 0 10px;
  font-size: 12px;
  color: #64748b;
}
.team-report-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}
.team-report-card {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  break-inside: avoid;
}
.site-table-section {
  break-inside: auto;
}
.site-summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
.site-summary-table th,
.site-summary-table td {
  border: 1px solid #d1d5db;
  padding: 4px 6px;
  text-align: center;
}
.site-summary-table th {
  background: #f8fafc;
  font-weight: 600;
}
.site-summary-table .site-name {
  text-align: left;
  min-width: 120px;
}
.site-summary-table .num {
  font-variant-numeric: tabular-nums;
}
.report-footer {
  margin-top: 24px;
  padding-top: 10px;
  border-top: 1px solid #e5e7eb;
  font-size: 11px;
  color: #6b7280;
}
.report-footer p {
  margin: 0;
}
.secondary-link,
.secondary {
  color: #334155;
  text-decoration: none;
  padding: 6px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
  background: #fff;
  cursor: pointer;
}
.muted {
  color: #64748b;
}
.error {
  color: #b91c1c;
  font-weight: 600;
}
@media (max-width: 1024px) {
  .report-paper {
    width: 100%;
    min-height: auto;
    padding: 16px;
  }
  .report-header {
    flex-direction: column;
  }
}
@media print {
  .no-print {
    display: none !important;
  }
  .report-page {
    background: #fff;
  }
  .report-paper {
    width: auto;
    min-height: auto;
    margin: 0;
    border: none;
    border-radius: 0;
    padding: 0;
  }
  .team-report-card {
    border-color: #cbd5e1;
  }
  @page {
    size: A4;
    margin: 12mm;
  }
}
</style>

<style>
@media print {
  body * {
    visibility: hidden;
  }
  .report-print-root,
  .report-print-root * {
    visibility: visible;
  }
  .report-print-root {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0;
    background: #fff;
    box-shadow: none;
    border: none;
  }
}
</style>
