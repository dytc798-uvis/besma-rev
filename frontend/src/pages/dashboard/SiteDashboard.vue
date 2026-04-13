<template>
  <div class="site-dash-page">
    <div class="site-dash-grid">
      <BaseCard title="SITE 대시보드">
        <template #actions>
          <button type="button" class="stitch-btn-secondary" @click="load">새로고침</button>
        </template>
        <template v-if="riskDbOverview">
          <section class="site-dash-alerts" aria-labelledby="site-dash-alerts-title">
            <h3 id="site-dash-alerts-title" class="site-dash-alerts-title">처리 필요 알림</h3>
            <p class="site-dash-alerts-sub">관리대장 화면에서 처리합니다. 문서취합 알림과 별도입니다.</p>
            <p class="site-ledger-kpi-intro site-ledger-kpi-intro--tight">운영 접수·조치와 DB 등록 요청 상태</p>
            <h4 class="site-ledger-section-title">근로자의견청취</h4>
            <section class="site-ledger-kpi-grid">
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('unreceived', 'voice')">
                <span class="site-ledger-kpi-label">접수 대기</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.unreceived }}</span>
                <span class="site-ledger-kpi-hint">현장 검토 필요</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('in_progress', 'voice')">
                <span class="site-ledger-kpi-label">조치중</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.in_progress }}</span>
                <span class="site-ledger-kpi-hint">조치 진행 중</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('action_completed', 'voice')">
                <span class="site-ledger-kpi-label">조치 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.action_completed }}</span>
                <span class="site-ledger-kpi-hint">운영 조치 완료</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_needed', 'voice')">
                <span class="site-ledger-kpi-label">DB 등록 요청 필요</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.db_request_needed }}</span>
                <span class="site-ledger-kpi-hint">관리대장에서 요청</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_requested', 'voice')">
                <span class="site-ledger-kpi-label">DB 등록 요청 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.db_requested }}</span>
                <span class="site-ledger-kpi-hint">본사 승인 대기</span>
              </button>
            </section>
            <div class="site-ledger-divider" aria-hidden="true" />
            <h4 class="site-ledger-section-title">부적합사항</h4>
            <section class="site-ledger-kpi-grid">
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('unreceived', 'nonconf')">
                <span class="site-ledger-kpi-label">접수 대기</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.unreceived }}</span>
                <span class="site-ledger-kpi-hint">현장 검토 필요</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('in_progress', 'nonconf')">
                <span class="site-ledger-kpi-label">조치중</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.in_progress }}</span>
                <span class="site-ledger-kpi-hint">조치 진행 중</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('action_completed', 'nonconf')">
                <span class="site-ledger-kpi-label">조치 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.action_completed }}</span>
                <span class="site-ledger-kpi-hint">운영 조치 완료</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_needed', 'nonconf')">
                <span class="site-ledger-kpi-label">DB 등록 요청 필요</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.db_request_needed }}</span>
                <span class="site-ledger-kpi-hint">관리대장에서 요청</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_requested', 'nonconf')">
                <span class="site-ledger-kpi-label">DB 등록 요청 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.db_requested }}</span>
                <span class="site-ledger-kpi-hint">본사 승인 대기</span>
              </button>
            </section>
          </section>
        </template>

        <div class="site-dash-doc-block">
          <p class="mb-3 text-sm font-semibold text-slate-700">문서·제안 현황</p>
          <p class="mb-4 text-sm text-slate-500">문서취합(내 현장 문서)과 운영 아이디어 제안 요약</p>
          <section class="site-kpi-grid">
            <KpiCard label="전체 문서 수" :value="data?.total_documents ?? '—'" accent="blue" />
            <KpiCard label="제출/검토 중" :value="data?.pending_documents ?? '—'" accent="orange" />
            <KpiCard label="반려 문서" :value="data?.rejected_documents ?? '—'" accent="red" />
            <KpiCard label="현장 의견 접수" :value="data?.total_opinions ?? '—'" accent="slate" />
            <KpiCard label="미조치 의견" :value="data?.pending_opinions ?? '—'" accent="slate" />
          </section>
        </div>
      </BaseCard>

      <BaseCard title="현장 기상 및 환경" class="weather-card">
        <template #actions>
          <span class="weather-updated">{{ formatDateTimeKst(weather?.snapshot_fetched_at || weather?.updated_at, "갱신 시각 없음") }}</span>
        </template>
        <p v-if="weather" class="weather-snapshot-meta">
          스냅샷 기준(KST·1일 2회): {{ formatDateTimeKst(weather.snapshot_anchor_kst, "—") }}
          <span class="weather-snapshot-sep">·</span>
          외부 조회 갱신: {{ formatDateTimeKst(weather.snapshot_fetched_at || weather.updated_at, "—") }}
        </p>
        <div v-if="weather?.available" class="weather-body">
          <div class="weather-main-row">
            <div>
              <p class="weather-label">{{ weather.location_name }}</p>
              <h2 class="weather-title">{{ weather.weather_label }} {{ tempText(weather.temperature) }}</h2>
              <p class="weather-sub">체감 {{ tempText(weather.feels_like) }} · 풍속 {{ speedText(weather.wind_speed) }}</p>
              <p class="weather-sub">강수 {{ mmText(weather.precipitation) }} / 강수확률 {{ percentText(weather.precipitation_probability) }}</p>
            </div>
            <div class="badge-stack">
              <span class="status-badge" :class="badgeTone(weather.pm10_status)">미세먼지 {{ weather.pm10_status }}</span>
              <span class="status-badge" :class="badgeTone(weather.pm25_status)">초미세먼지 {{ weather.pm25_status }}</span>
            </div>
          </div>
          <div class="dust-metrics">
            <div class="metric-chip">PM10 {{ valueText(weather.pm10) }}</div>
            <div class="metric-chip">PM2.5 {{ valueText(weather.pm25) }}</div>
          </div>
          <ul class="message-list">
            <li v-for="message in behaviorMessages(weather.safety_messages)" :key="message">{{ message }}</li>
            <li v-if="behaviorMessages(weather.safety_messages).length === 0" class="neutral">추가 안전 메시지 없음</li>
          </ul>
          <p v-if="weather.risk_assessment_required" class="risk-flag">위험성평가 반영 필요</p>
        </div>
        <div v-else class="weather-empty">
          <strong>{{ weather?.status_text || "일시적 조회 실패" }}</strong>
          <p>외부 기상/미세먼지 정보를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { BaseCard, KpiCard } from "@/components/product";
import { formatDateTimeKst } from "@/utils/datetime";
import type { LedgerDashboardFilter } from "@/utils/ledgerDashboardFilter";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
  rejected_documents: number;
  total_opinions: number;
  pending_opinions: number;
}

interface RiskDbHqKpis {
  pending_requests: number;
  pending_approval: number;
  rejected: number;
  approved: number;
  reward_candidates: number;
}

interface RiskDbSiteKpis {
  unreceived: number;
  in_progress: number;
  action_completed: number;
  db_request_needed: number;
  db_requested: number;
}

interface RiskDbOverviewPayload {
  hq: {
    combined: RiskDbHqKpis;
    worker_voice: RiskDbHqKpis;
    nonconformity: RiskDbHqKpis;
  };
  site: {
    combined: RiskDbSiteKpis;
    worker_voice: RiskDbSiteKpis;
    nonconformity: RiskDbSiteKpis;
  };
}

interface WeatherSummary {
  available: boolean;
  location_name: string;
  weather_label: string;
  temperature: number | null;
  feels_like: number | null;
  wind_speed: number | null;
  precipitation: number | null;
  precipitation_probability: number | null;
  pm10: number | null;
  pm10_status: string;
  pm25: number | null;
  pm25_status: string;
  safety_messages: string[];
  risk_assessment_required: boolean;
  updated_at: string | null;
  status_text?: string;
  /** KST 앵커(05:00 또는 12:00) ISO 문자열 */
  snapshot_anchor_kst?: string | null;
  /** Open-Meteo 조회 완료 시각(UTC 권장) ISO 문자열 */
  snapshot_fetched_at?: string | null;
}

const router = useRouter();
const data = ref<DashboardSummary | null>(null);
const weather = ref<WeatherSummary | null>(null);
const riskDbOverview = ref<RiskDbOverviewPayload | null>(null);
const summaryError = ref(false);
const weatherError = ref(false);

function goSiteLedgerFilter(filter: LedgerDashboardFilter, board: "voice" | "nonconf") {
  const name = board === "voice" ? "site-worker-voice" : "site-nonconformities";
  router.push({ name, query: { filter } });
}

function tempText(value: number | null) {
  return value == null ? "—" : `${Math.round(value)}℃`;
}

function speedText(value: number | null) {
  return value == null ? "—" : `${Math.round(value * 10) / 10}m/s`;
}

function mmText(value: number | null) {
  return value == null ? "—" : `${Math.round(value * 10) / 10}mm`;
}

function percentText(value: number | null) {
  return value == null ? "—" : `${Math.round(value)}%`;
}

function valueText(value: number | null) {
  return value == null ? "—" : `${Math.round(value)}`;
}

function badgeTone(status: string) {
  if (status === "매우나쁨") return "tone-bad";
  if (status === "나쁨") return "tone-warn";
  if (status === "보통") return "tone-normal";
  return "tone-good";
}

function behaviorMessages(messages: string[]) {
  return messages.filter((message) => message !== "위험성평가 반영 필요");
}

async function load() {
  summaryError.value = false;
  weatherError.value = false;
  const summaryPromise = api.get<DashboardSummary>("/dashboard/summary").then(
    (res) => {
      data.value = res.data;
    },
    () => {
      summaryError.value = true;
      data.value = null;
    },
  );
  const riskPromise = api.get<RiskDbOverviewPayload>("/dashboard/risk-db-overview").then(
    (res) => {
      riskDbOverview.value = res.data;
    },
    () => {
      riskDbOverview.value = null;
    },
  );
  const weatherPromise = api.get<WeatherSummary>("/dashboard/weather/site-summary").then(
    (res) => {
      weather.value = res.data;
    },
    () => {
      weatherError.value = true;
      weather.value = {
        available: false,
        location_name: "",
        weather_label: "",
        temperature: null,
        feels_like: null,
        wind_speed: null,
        precipitation: null,
        precipitation_probability: null,
        pm10: null,
        pm10_status: "",
        pm25: null,
        pm25_status: "",
        safety_messages: [],
        risk_assessment_required: false,
        updated_at: null,
        status_text: "일시적 조회 실패",
        snapshot_anchor_kst: null,
        snapshot_fetched_at: null,
      };
    },
  );
  await Promise.all([summaryPromise, weatherPromise, riskPromise]);
}

onMounted(load);
</script>

<style scoped>
.site-dash-page {
  width: 100%;
}

.site-dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.site-kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.site-dash-alerts {
  margin-bottom: 18px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e2e8f0;
}

.site-dash-alerts-title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
}

.site-dash-alerts-sub {
  margin: 0 0 10px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.site-dash-doc-block {
  margin-top: 8px;
}

.site-ledger-kpi-intro {
  margin: 14px 0 8px;
  font-size: 12px;
  color: #64748b;
}

.site-ledger-kpi-intro--tight {
  margin-top: 0;
}

.site-ledger-section-title {
  margin: 12px 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.site-ledger-kpi-intro + .site-ledger-section-title {
  margin-top: 4px;
}

.site-ledger-divider {
  height: 1px;
  margin: 14px 0 4px;
  background: linear-gradient(to right, transparent, #e2e8f0 8%, #e2e8f0 92%, transparent);
}

.site-ledger-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.site-ledger-kpi {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;
}

.site-ledger-kpi:hover {
  border-color: #cbd5e1;
  background: #fff;
}

.site-ledger-kpi-label {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
}

.site-ledger-kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.site-ledger-kpi-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.3;
}

.weather-card {
  min-height: 100%;
}

.weather-snapshot-meta {
  margin: 0 0 10px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.weather-snapshot-sep {
  margin: 0 6px;
  color: #94a3b8;
}

.weather-body {
  display: grid;
  gap: 12px;
}

.weather-main-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.weather-label,
.weather-sub,
.weather-updated {
  color: #64748b;
  font-size: 12px;
}

.weather-title {
  margin: 6px 0;
  font-size: 24px;
  color: #0f172a;
}

.badge-stack {
  display: grid;
  gap: 8px;
  align-content: start;
}

.status-badge,
.metric-chip {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
}

.tone-good {
  background: #dcfce7;
  color: #166534;
}

.tone-normal {
  background: #e2e8f0;
  color: #334155;
}

.tone-warn {
  background: #ffedd5;
  color: #c2410c;
}

.tone-bad {
  background: #fee2e2;
  color: #b91c1c;
}

.dust-metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.metric-chip {
  background: #eff6ff;
  color: #1d4ed8;
}

.message-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
}

.risk-flag {
  margin: 0;
  color: #b91c1c;
  font-weight: 700;
}

.weather-empty {
  color: #64748b;
  font-size: 13px;
}

.weather-empty strong {
  display: block;
  color: #0f172a;
  margin-bottom: 6px;
}

.neutral {
  color: #64748b;
}

@media (max-width: 900px) {
  .site-dash-grid {
    grid-template-columns: 1fr;
  }

  .site-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .site-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
