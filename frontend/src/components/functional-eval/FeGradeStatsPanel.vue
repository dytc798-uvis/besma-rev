<template>
  <div class="fe-grade-stats" :class="{ 'fe-grade-stats--compact': compact }">
    <div v-if="title" class="fe-grade-stats__title-row">
      <h3 class="fe-grade-stats__title">{{ title }}</h3>
      <span v-if="subtitle" class="fe-grade-stats__subtitle">{{ subtitle }}</span>
    </div>

    <div class="fe-grade-stats__dim-tabs" role="tablist">
      <button
        type="button"
        class="fe-grade-stats__dim-tab"
        :class="{ active: dimension === 'functional' }"
        @click="dimension = 'functional'"
      >
        2-1 기능
      </button>
      <button
        type="button"
        class="fe-grade-stats__dim-tab"
        :class="{ active: dimension === 'safety' }"
        @click="dimension = 'safety'"
      >
        2-2 안전
      </button>
    </div>

    <div v-if="!hasDisplayData" class="fe-grade-stats__empty muted">
      등급 통계를 표시할 근로자 데이터가 없습니다.
    </div>

    <div v-else class="fe-grade-stats__body">
      <div class="fe-grade-stats__chart-wrap">
        <div class="fe-grade-stats__donut" :style="donutStyle" aria-hidden="true">
          <div class="fe-grade-stats__donut-hole">
            <span class="fe-grade-stats__donut-total">{{ displayWorkersTotal }}</span>
            <span class="fe-grade-stats__donut-label">근로자</span>
            <span v-if="activeBlock?.graded_total" class="fe-grade-stats__donut-sub">
              평가완료 {{ activeBlock.graded_total }}<span v-if="activeBlock.is_demo"> (가상)</span>
            </span>
          </div>
        </div>
        <ul class="fe-grade-stats__legend">
          <li v-for="g in gradeOrder" :key="g">
            <span class="fe-grade-stats__swatch" :class="`fe-grade-stats__swatch--${g.toLowerCase()}`" />
            <span class="fe-grade-stats__legend-grade">{{ g }}</span>
            <span class="fe-grade-stats__legend-pct">{{ gradePct(g) }}%</span>
          </li>
        </ul>
      </div>

      <table class="data-table fe-grade-stats__table">
        <thead>
          <tr>
            <th>등급</th>
            <th>인원</th>
            <th>비율</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in gradeOrder" :key="`row-${g}`">
            <td><span :class="['grade-pill', `grade-pill--${g.toLowerCase()}`]">{{ g }}</span></td>
            <td>{{ gradeCount(g) }}명</td>
            <td>{{ gradePct(g) }}%</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td>합계</td>
            <td>{{ activeBlock.graded_total }}명</td>
            <td>100%</td>
          </tr>
          <tr v-if="erpHeadcount != null && erpHeadcount !== activeBlock?.workers_total">
            <td colspan="3" class="muted fe-grade-stats__foot-note">
              출역 기준 {{ activeBlock?.workers_total }}명 / ERP 인원 {{ erpHeadcount }}명
            </td>
          </tr>
          <tr v-if="activeBlock?.ungraded_count">
            <td colspan="3" class="muted fe-grade-stats__foot-note">미평가 {{ activeBlock.ungraded_count }}명 (비율 제외)</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

export type GradeBucket = {
  count: number;
  pct: number;
};

export type GradeStatBlock = {
  workers_total?: number;
  attendance_workers?: number;
  erp_headcount?: number | null;
  graded_total: number;
  ungraded_count: number;
  grades: Record<string, GradeBucket>;
  is_demo?: boolean;
};

export type GradeStatsPayload = {
  functional: GradeStatBlock;
  safety: GradeStatBlock;
};

const props = withDefaults(
  defineProps<{
    stats: GradeStatsPayload | null;
    title?: string;
    subtitle?: string;
    compact?: boolean;
  }>(),
  { compact: false },
);

const dimension = ref<"functional" | "safety">("functional");
const gradeOrder = ["S", "A", "B", "C"] as const;

const GRADE_COLORS: Record<string, string> = {
  S: "#16a34a",
  A: "#2563eb",
  B: "#d97706",
  C: "#dc2626",
};

const activeBlock = computed(() => {
  if (!props.stats) return null;
  return dimension.value === "functional" ? props.stats.functional : props.stats.safety;
});

function gradeCount(code: string) {
  return activeBlock.value?.grades?.[code]?.count ?? 0;
}

function gradePct(code: string) {
  return activeBlock.value?.grades?.[code]?.pct ?? 0;
}

const displayWorkersTotal = computed(() => {
  const block = activeBlock.value;
  if (!block) return 0;
  return Number(block.workers_total ?? block.graded_total ?? 0);
});

const erpHeadcount = computed(() => {
  const block = activeBlock.value;
  if (!block) return null;
  const erp = block.erp_headcount;
  if (erp == null || erp === 0) return null;
  return Number(erp);
});

const hasDisplayData = computed(() => displayWorkersTotal.value > 0 || (activeBlock.value?.graded_total ?? 0) > 0);

const donutStyle = computed(() => {
  const block = activeBlock.value;
  if (!block?.graded_total) {
    return { background: "#e2e8f0" };
  }
  let acc = 0;
  const parts: string[] = [];
  for (const g of gradeOrder) {
    const cnt = gradeCount(g);
    if (cnt <= 0) continue;
    const slice = (100 * cnt) / block.graded_total;
    const color = GRADE_COLORS[g];
    parts.push(`${color} ${acc}% ${acc + slice}%`);
    acc += slice;
  }
  if (!parts.length) {
    return { background: "#e2e8f0" };
  }
  return { background: `conic-gradient(${parts.join(", ")})` };
});
</script>

<style scoped>
.fe-grade-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fe-grade-stats__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}
.fe-grade-stats__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.fe-grade-stats__subtitle {
  font-size: 13px;
  color: #64748b;
}
.fe-grade-stats__dim-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  background: #f1f5f9;
  border-radius: 8px;
  width: fit-content;
}
.fe-grade-stats__dim-tab {
  border: none;
  background: transparent;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  color: #64748b;
}
.fe-grade-stats__dim-tab.active {
  background: #fff;
  color: #0f172a;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}
.fe-grade-stats__body {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 20px;
  align-items: start;
}
.fe-grade-stats--compact .fe-grade-stats__body {
  grid-template-columns: 1fr;
}
.fe-grade-stats__chart-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.fe-grade-stats__donut {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.fe-grade-stats--compact .fe-grade-stats__donut {
  width: 140px;
  height: 140px;
}
.fe-grade-stats__donut-hole {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px #e2e8f0;
}
.fe-grade-stats__donut-total {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
  color: #0f172a;
}
.fe-grade-stats__donut-label {
  font-size: 11px;
  color: #64748b;
}
.fe-grade-stats__donut-sub {
  font-size: 11px;
  color: #475569;
  margin-top: 2px;
}
.fe-grade-stats__legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(88px, 1fr));
  gap: 6px 12px;
  font-size: 13px;
}
.fe-grade-stats__legend li {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fe-grade-stats__swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}
.fe-grade-stats__swatch--s { background: #16a34a; }
.fe-grade-stats__swatch--a { background: #2563eb; }
.fe-grade-stats__swatch--b { background: #d97706; }
.fe-grade-stats__swatch--c { background: #dc2626; }
.fe-grade-stats__legend-grade {
  font-weight: 600;
  min-width: 14px;
}
.fe-grade-stats__legend-pct {
  color: #334155;
  font-variant-numeric: tabular-nums;
}
.fe-grade-stats__table {
  margin: 0;
  font-size: 13px;
}
.fe-grade-stats__table th,
.fe-grade-stats__table td {
  padding: 8px 10px;
}
.fe-grade-stats__foot-note {
  font-size: 12px;
  text-align: right;
}
.grade-pill {
  display: inline-block;
  min-width: 24px;
  text-align: center;
  font-weight: 700;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
}
.grade-pill--s { background: #dcfce7; color: #166534; }
.grade-pill--a { background: #dbeafe; color: #1d4ed8; }
.grade-pill--b { background: #ffedd5; color: #c2410c; }
.grade-pill--c { background: #fee2e2; color: #b91c1c; }
.fe-grade-stats__empty {
  padding: 16px;
  text-align: center;
  font-size: 13px;
}
@media (max-width: 640px) {
  .fe-grade-stats__body {
    grid-template-columns: 1fr;
  }
}
</style>
