<template>
  <div class="hq-periodic-page">
    <BaseCard class="main-panel !p-[22px]">
      <template #head>
        <div class="flex w-full flex-wrap items-start justify-between gap-4">
          <div>
            <h2 class="m-0 text-[17px] font-bold text-slate-900">주기 기반 문서 모니터링</h2>
            <p class="sub">TBM은 일별 누적 운영데이터를 월간 집계로 표현하고, 클릭 시 일별 drill-down을 제공합니다.</p>
          </div>
        </div>
      </template>

      <section class="periodic-controls">
        <FilterBar class="controls">
          <div class="control-group">
            <label class="field-label">월</label>
            <input v-model="yearMonth" type="month" class="field-input" />
          </div>
          <button type="button" class="stitch-btn-secondary" @click="loadMonthly" :disabled="monthlyLoading">
            {{ monthlyLoading ? "로딩중..." : "새로고침" }}
          </button>
        </FilterBar>
      </section>

      <section class="periodic-content">
        <div v-if="monthlyLoading" class="muted">월간 집계를 불러오는 중입니다...</div>
        <div v-else>
          <BaseTable>
            <thead>
              <tr>
                <th>현장명</th>
                <th>생성 일수</th>
                <th>완료 일수</th>
                <th>배포 일수</th>
                <th>확인 일수</th>
                <th>누락 일수</th>
                <th>완료율</th>
                <th>일별 drill-down</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in monthlySites" :key="s.site_id">
                <td>
                  <strong>{{ s.site_name }}</strong>
                </td>
                <td>{{ s.generated_days }}</td>
                <td>{{ s.completed_days }}</td>
                <td>{{ s.distributed_days }}</td>
                <td>{{ s.confirmed_days }}</td>
                <td>{{ s.missing_days }}</td>
                <td>{{ s.completion_rate_pct }}%</td>
                <td>
                  <button type="button" class="stitch-btn-secondary btn-compact" @click="openDaily(s.site_id)">
                    보기
                  </button>
                </td>
              </tr>
              <tr v-if="monthlySites.length === 0">
                <td colspan="8" class="empty-cell">데이터 없음</td>
              </tr>
            </tbody>
          </BaseTable>
        </div>
      </section>
    </BaseCard>

    <div v-if="dailyModalOpen" class="modal-backdrop" @click.self="closeDailyModal">
      <BaseCard class="modal-card !w-full max-w-[920px]" title="TBM 일별 상세">
        <template #head>
          <div class="modal-head">
            <div>
              <div class="modal-title">TBM 월간 {{ dailyData?.year_month }} · {{ dailyData?.site_name }}</div>
              <div class="modal-sub">
                생성 {{ dailyData?.summary.generated_days }}일 / 완료 {{ dailyData?.summary.completed_days }}일 / 누락
                {{ dailyData?.summary.missing_days }}일
              </div>
            </div>
            <button type="button" class="stitch-btn-secondary" @click="closeDailyModal">닫기</button>
          </div>
        </template>

        <div v-if="dailyLoading" class="muted">일별 상세를 불러오는 중입니다...</div>
        <div v-else>
          <BaseTable>
            <thead>
              <tr>
                <th>날짜</th>
                <th>배포</th>
                <th>확인</th>
                <th>근로자 서명(완료/총)</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in dailyData?.days" :key="d.work_date">
                <td>{{ d.work_date }}</td>
                <td>
                  <StatusBadge :tone="d.distributed ? 'info' : 'neutral'">
                    {{ d.distributed ? `배포(${d.distribution_count})` : "미배포" }}
                  </StatusBadge>
                </td>
                <td>
                  <StatusBadge :tone="d.confirmed ? 'success' : 'neutral'">
                    {{ d.confirmed ? `확인(${d.confirmation_count})` : "미확인" }}
                  </StatusBadge>
                </td>
                <td>
                  {{ d.worker_completed }}/{{ d.worker_total }}
                </td>
                <td>
                  <StatusBadge
                    :tone="d.completed ? 'success' : d.distributed ? 'warn' : 'danger'"
                  >
                    {{ d.completed ? "완료" : d.distributed ? "미서명" : "누락" }}
                  </StatusBadge>
                </td>
              </tr>
              <tr v-if="(dailyData?.days?.length ?? 0) === 0">
                <td colspan="5" class="empty-cell">일별 데이터 없음</td>
              </tr>
            </tbody>
          </BaseTable>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";
import { BaseCard, BaseTable, FilterBar, StatusBadge } from "@/components/product";
import { yearMonthKst } from "@/utils/datetime";

interface TbmMonthlySiteSummary {
  site_id: number;
  site_name: string;
  generated_days: number;
  completed_days: number;
  distributed_days: number;
  confirmed_days: number;
  missing_days: number;
  completion_rate_pct: number;
}

interface TbmDailyWorkRow {
  work_date: string;
  distributed: boolean;
  confirmed: boolean;
  confirmation_count: number;
  distribution_count: number;
  worker_total: number;
  worker_completed: number;
  completed: boolean;
  missing: boolean;
}

interface TbmMonthlySummary extends TbmMonthlySiteSummary {}

interface TbmDailyMonitoringResponse {
  site_id: number;
  site_name: string;
  year: number;
  month: number;
  year_month: string;
  start_date: string;
  end_date: string;
  summary: TbmMonthlySummary;
  days: TbmDailyWorkRow[];
}

const yearMonth = ref<string>(yearMonthKst());

const monthlyLoading = ref(false);
const dailyLoading = ref(false);

const monthlySites = ref<TbmMonthlySiteSummary[]>([]);

const dailyModalOpen = ref(false);
const dailyData = ref<TbmDailyMonitoringResponse | null>(null);

async function loadMonthly() {
  monthlyLoading.value = true;
  try {
    const res = await api.get("/documents/periodic-monitoring/tbm/monthly", {
      params: { year_month: yearMonth.value },
    });
    monthlySites.value = res.data?.sites ?? [];
  } finally {
    monthlyLoading.value = false;
  }
}

async function openDaily(siteId: number) {
  dailyModalOpen.value = true;
  dailyLoading.value = true;
  dailyData.value = null;
  try {
    const res = await api.get("/documents/periodic-monitoring/tbm/daily", {
      params: { year_month: yearMonth.value, site_id: siteId },
    });
    dailyData.value = res.data as TbmDailyMonitoringResponse;
  } finally {
    dailyLoading.value = false;
  }
}

function closeDailyModal() {
  dailyModalOpen.value = false;
}

onMounted(loadMonthly);
</script>

<style scoped>
.hq-periodic-page {
  width: 100%;
}

.periodic-controls {
  margin-bottom: 12px;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.control-group {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.field-label {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.field-input {
  height: 36px;
  min-height: 36px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0 12px;
  background: #fff;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 50;
}

.modal-card {
  max-height: 85vh;
  overflow: auto;
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.modal-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 6px;
}

.modal-sub {
  font-size: 12px;
  color: #64748b;
}

.btn-compact {
  padding: 6px 10px;
  font-size: 12px;
}

.muted {
  color: #64748b;
}
</style>

