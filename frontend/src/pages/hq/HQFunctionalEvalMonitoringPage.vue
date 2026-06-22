<template>
  <div class="fe-monitor-page">
    <div class="fe-monitor-header">
      <div>
        <h1 class="page-title">기능인인정제 운영지표 모니터링</h1>
        <p v-if="period" class="page-sub">
          마지막 출역일 {{ period.last_attendance_date || "없음" }} ·
          마감일 {{ period.deadline_date }}
          <span :class="period.is_closed ? 'badge closed' : 'badge open'">
            {{ period.is_closed ? "마감" : "진행" }}
          </span>
          <span v-if="cacheLabel" class="cache-label">· {{ cacheLabel }}</span>
        </p>
      </div>
      <button class="stitch-btn-secondary" type="button" :disabled="loading" @click="loadMonitoring">
        {{ loading ? "조회 중..." : "새로고침" }}
      </button>
    </div>

    <p v-if="loadError" class="load-error">{{ loadError }}</p>
    <p v-if="attendanceMessage" class="attendance-warning">{{ attendanceMessage }}</p>

    <section class="monitor-kpi-grid">
      <KpiCard
        label="미평가"
        :value="monitorCounts.not_started"
        accent="slate"
        badge-text="미평가"
        badge-tone="neutral"
      />
      <KpiCard
        label="평가중"
        :value="monitorCounts.in_progress"
        accent="blue"
        badge-text="평가중"
        badge-tone="info"
      />
      <KpiCard
        label="평가완료"
        :value="monitorCounts.completed"
        accent="emerald"
        badge-text="평가완료"
        badge-tone="success"
      />
      <KpiCard
        label="평가완료율"
        :value="completionRateLabel"
        accent="violet"
        badge-text="전체"
        badge-tone="info"
      />
    </section>

    <section class="monitor-kpi-grid" v-if="bucketSummaryText">
      <KpiCard label="평가 미진행 현장" :value="siteBuckets.not_started" accent="blue" compact />
      <KpiCard label="평가 진행 현장" :value="siteBuckets.in_progress" accent="orange" compact />
      <KpiCard label="평가완료 현장" :value="siteBuckets.completed" accent="emerald" compact />
      <KpiCard label="총 현장" :value="totals?.sites || 0" accent="slate" compact />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { KpiCard } from "@/components/product";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";

const auth = useAuthStore();
const loading = ref(false);
const loadError = ref("");
const attendanceMessage = ref("");
const period = ref<{
  deadline_date: string;
  is_closed: boolean;
  last_attendance_date?: string | null;
} | null>(null);
const totals = ref<{
  sites: number;
  workers: number;
  fully_complete: number;
} | null>(null);
const workerStatusCounts = ref({
  not_started: 0,
  in_progress: 0,
  completed: 0,
});
const siteBuckets = ref({
  in_progress: 0,
  not_started: 0,
  completed: 0,
});
const cacheInfo = ref<{
  mode?: string;
  computed_at?: string | null;
  ttl_seconds?: number;
} | null>(null);

const monitorCounts = computed(() => workerStatusCounts.value);
const completionRate = computed(() => {
  const total = totals.value?.workers ?? 0;
  if (!total) return 0;
  return Math.round((workerStatusCounts.value.completed / total) * 100);
});
const completionRateLabel = computed(() => `${completionRate.value}%`);
const bucketSummaryText = computed(() =>
  siteBuckets.value.in_progress + siteBuckets.value.not_started + siteBuckets.value.completed > 0,
);
const cacheLabel = computed(() => {
  if (!cacheInfo.value?.computed_at) return "";
  const mode = cacheInfo.value.mode === "cached" ? "캐시" : "갱신";
  return `${mode} 기준 ${cacheInfo.value.computed_at.slice(0, 16).replace("T", " ")} · 1시간 주기`;
});

function assertMonitorRole() {
  const role = auth.user?.role ?? "";
  return ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "HQ_OTHER", "FUNCTIONAL_EVAL_VIEWER"].includes(role);
}

async function loadMonitoring() {
  if (!assertMonitorRole()) {
    loadError.value = "이 계정은 기능인인정제 모니터링 조회 권한이 없습니다.";
    return;
  }
  loading.value = true;
  loadError.value = "";
  attendanceMessage.value = "";
  try {
    const res = await api.get("/functional-eval/hq/monitoring-summary");
    const data = res.data as {
      period: typeof period.value;
      attendance_message?: string;
      totals?: { sites: number; workers: number; fully_complete: number };
      worker_status_counts?: { not_started: number; in_progress: number; completed: number };
      site_buckets?: { in_progress: number; not_started: number; completed: number };
      cache?: { mode?: string; computed_at?: string | null; ttl_seconds?: number };
    };
    period.value = data.period;
    totals.value = data.totals || null;
    attendanceMessage.value = data.attendance_message || "";
    cacheInfo.value = data.cache || null;
    workerStatusCounts.value = {
      not_started: Number(data.worker_status_counts?.not_started || 0),
      in_progress: Number(data.worker_status_counts?.in_progress || 0),
      completed: Number(data.worker_status_counts?.completed || 0),
    };
    siteBuckets.value = {
      in_progress: Number(data.site_buckets?.in_progress || 0),
      not_started: Number(data.site_buckets?.not_started || 0),
      completed: Number(data.site_buckets?.completed || 0),
    };
  } catch {
    loadError.value = "운영지표 조회에 실패했습니다. 잠시 후 새로고침하세요.";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadMonitoring();
});
</script>

<style scoped>
.fe-monitor-page {
  width: 100%;
  display: grid;
  gap: 16px;
}

.fe-monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0 0 6px;
  font-size: 22px;
}

.page-sub {
  margin: 0;
  color: #334155;
}

.cache-label {
  color: #64748b;
}

.badge {
  margin-left: 8px;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
}

.badge.open {
  background: #e0f2fe;
  color: #0c4a6e;
}

.badge.closed {
  background: #f3f4f6;
  color: #374151;
}

.monitor-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.load-error {
  color: #dc2626;
  margin: 0;
}

.attendance-warning {
  margin: 0;
  color: #0f172a;
}

@media (max-width: 900px) {
  .monitor-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 540px) {
  .monitor-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
