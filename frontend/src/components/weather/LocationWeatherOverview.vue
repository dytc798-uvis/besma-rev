<template>
  <section class="weather-panel">
    <div class="weather-head">
      <div>
        <p class="eyebrow">위치 기반 작업 기상</p>
        <h2>현재 날씨와 5일 예보</h2>
        <small v-if="overview">{{ overview.location_name }} · {{ overview.source_label }}</small>
      </div>
      <button class="secondary" type="button" :disabled="loading" @click="load">
        {{ loading ? "조회 중…" : "현재 위치 새로고침" }}
      </button>
    </div>

    <p v-if="error" class="weather-error">{{ error }}</p>
    <template v-if="overview">
      <div class="current-card">
        <div>
          <span>{{ overview.current.weather_label }}</span>
          <strong>{{ numberText(overview.current.temperature_c, "℃") }}</strong>
        </div>
        <dl>
          <div><dt>습도</dt><dd>{{ numberText(overview.current.relative_humidity_pct, "%", 0) }}</dd></div>
          <div><dt>체감온도</dt><dd>{{ numberText(overview.current.apparent_temperature_c, "℃") }}</dd></div>
          <div><dt>강수</dt><dd>{{ numberText(overview.current.precipitation_mm, "mm") }}</dd></div>
          <div><dt>풍속</dt><dd>{{ numberText(overview.current.wind_speed_kmh, "km/h") }}</dd></div>
        </dl>
        <button
          v-if="canUseCurrentValues"
          type="button"
          @click="applyCurrentValues"
        >
          현재값을 체감온도 입력에 사용
        </button>
      </div>

      <div class="forecast-grid">
        <article v-for="day in overview.forecast_days" :key="day.date">
          <strong>{{ dayLabel(day.date) }}</strong>
          <span>{{ day.weather_label }}</span>
          <b>{{ numberText(day.temperature_max_c, "℃", 0) }} / {{ numberText(day.temperature_min_c, "℃", 0) }}</b>
          <small>강수 {{ numberText(day.precipitation_probability_max_pct, "%", 0) }}</small>
          <div v-if="day.risk_flags.length" class="risk-list">
            <span v-for="risk in day.risk_flags" :key="risk.code" :title="risk.message">{{ risk.label }}</span>
          </div>
        </article>
      </div>
      <p class="source-note">
        {{ overview.kma_notice }} 현재 표시값은 현장 실측값을 대체하지 않으며 작업계획 참고용입니다.
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";

interface RiskFlag { code: string; label: string; message: string }
interface ForecastDay {
  date: string;
  weather_label: string;
  temperature_max_c: number | null;
  temperature_min_c: number | null;
  precipitation_probability_max_pct: number | null;
  risk_flags: RiskFlag[];
}
interface WeatherOverview {
  location_name: string;
  source_label: string;
  source: string;
  kma_notice: string;
  current: {
    weather_label: string;
    temperature_c: number | null;
    relative_humidity_pct: number | null;
    apparent_temperature_c: number | null;
    precipitation_mm: number | null;
    wind_speed_kmh: number | null;
  };
  forecast_days: ForecastDay[];
}

const props = defineProps<{ siteId?: number | null; readOnly?: boolean; autoApply?: boolean }>();
const emit = defineEmits<{ "use-current": [payload: { temperature: number | null; humidity: number | null; source: string }] }>();
const overview = ref<WeatherOverview | null>(null);
const loading = ref(false);
const error = ref("");
const autoApplied = ref(false);
const canUseCurrentValues = computed(
  () => !props.readOnly && overview.value?.current.temperature_c != null && overview.value?.current.relative_humidity_pct != null,
);

function currentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("GEOLOCATION_UNAVAILABLE"));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 10_000,
      maximumAge: 10 * 60 * 1000,
    });
  });
}

async function load() {
  loading.value = true;
  error.value = "";
  overview.value = null;
  try {
    try {
      const position = await currentPosition();
      overview.value = (
        await api.get("/weather/location-overview", {
          params: {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          },
        })
      ).data;
    } catch (positionError) {
      if (!props.siteId) throw positionError;
      overview.value = (
        await api.get("/weather/location-overview", { params: { site_id: props.siteId } })
      ).data;
    }
    if (props.autoApply && !autoApplied.value) {
      applyCurrentValues();
      autoApplied.value = true;
    }
  } catch (loadError: any) {
    if (loadError?.code === 1) error.value = "위치 권한이 거부되었습니다. 브라우저에서 위치 사용을 허용해 주세요.";
    else if (loadError?.response?.data?.detail === "WEATHER_PROVIDER_UNAVAILABLE") error.value = "기상자료 제공처에 일시적으로 연결할 수 없습니다.";
    else error.value = "현장 좌표 또는 현재 위치를 확인할 수 없습니다.";
  } finally {
    loading.value = false;
  }
}

function applyCurrentValues() {
  if (!overview.value) return;
  emit("use-current", {
    temperature: overview.value.current.temperature_c,
    humidity: overview.value.current.relative_humidity_pct,
    source: overview.value.source,
  });
}

function numberText(value: number | null, unit: string, digits = 1) {
  return value == null ? "—" : `${Number(value).toFixed(digits)}${unit}`;
}
function dayLabel(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric", weekday: "short" });
}

defineExpose({ load });
onMounted(load);
</script>

<style scoped>
.weather-panel{background:#fff;border:1px solid #bfdbfe;border-radius:18px;padding:22px;display:grid;gap:16px}.weather-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.weather-head h2{margin:3px 0}.eyebrow{margin:0;color:#0369a1;font-weight:900}.secondary{border:1px solid #cbd5e1;background:#fff;color:#334155}.current-card{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:24px;border-radius:16px;background:linear-gradient(135deg,#eff6ff,#ecfeff);padding:18px}.current-card>div{display:grid}.current-card>div strong{font-size:36px}.current-card dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0}.current-card dl div{background:rgba(255,255,255,.75);border-radius:10px;padding:9px}.current-card dt{font-size:12px;color:#64748b}.current-card dd{margin:3px 0 0;font-weight:900}.forecast-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px}.forecast-grid article{border:1px solid #e2e8f0;border-radius:12px;padding:12px;display:grid;gap:5px}.forecast-grid b{font-size:13px}.risk-list{display:flex;flex-wrap:wrap;gap:4px}.risk-list span{border-radius:999px;background:#ffedd5;color:#9a3412;padding:3px 7px;font-size:11px;font-weight:900}.source-note{margin:0;color:#64748b;font-size:12px;line-height:1.55}.weather-error{color:#b91c1c;font-weight:800}button{border:0;border-radius:10px;background:#0369a1;color:#fff;padding:10px 13px;font-weight:800;cursor:pointer}button:disabled{opacity:.55}
@media(max-width:800px){.current-card{grid-template-columns:1fr}.current-card dl{grid-template-columns:repeat(2,1fr)}.forecast-grid{grid-template-columns:repeat(2,1fr)}.forecast-grid article:first-child{grid-column:1/-1}.weather-head{display:grid}}
</style>
