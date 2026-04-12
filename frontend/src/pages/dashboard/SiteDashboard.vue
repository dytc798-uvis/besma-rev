<template>
  <div class="site-dash-page">
    <div class="site-dash-grid">
      <BaseCard title="SITE 대시보드">
        <template #actions>
          <button type="button" class="stitch-btn-secondary" @click="load">새로고침</button>
        </template>
        <p class="mb-5 text-sm text-slate-500">내 현장 KPI</p>
        <section class="site-kpi-grid">
          <KpiCard label="전체 문서 수" :value="data?.total_documents ?? '—'" accent="blue" />
          <KpiCard label="제출/검토 중" :value="data?.pending_documents ?? '—'" accent="orange" />
          <KpiCard label="반려 문서" :value="data?.rejected_documents ?? '—'" accent="red" />
          <KpiCard label="현장 의견 접수" :value="data?.total_opinions ?? '—'" accent="slate" />
          <KpiCard label="미조치 의견" :value="data?.pending_opinions ?? '—'" accent="slate" />
        </section>
      </BaseCard>

      <BaseCard title="현장 기상 및 환경" class="weather-card">
        <template #actions>
          <span class="weather-updated">{{ formatDateTimeKst(weather?.updated_at, "업데이트 정보 없음") }}</span>
        </template>
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
import { api } from "@/services/api";
import { BaseCard, KpiCard } from "@/components/product";
import { formatDateTimeKst } from "@/utils/datetime";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
  rejected_documents: number;
  total_opinions: number;
  pending_opinions: number;
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
}

const data = ref<DashboardSummary | null>(null);
const weather = ref<WeatherSummary | null>(null);

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
  try {
    const [summaryRes, weatherRes] = await Promise.all([
      api.get("/dashboard/summary"),
      api.get("/dashboard/weather/site-summary"),
    ]);
    data.value = summaryRes.data;
    weather.value = weatherRes.data;
  } catch {
    data.value = null;
    weather.value = null;
  }
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

.weather-card {
  min-height: 100%;
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
