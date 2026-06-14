<template>
  <section class="fe-grade-print-block">
    <header v-if="title || subtitle" class="fe-grade-print-block__head">
      <h3 v-if="title" class="fe-grade-print-block__title">{{ title }}</h3>
      <p v-if="subtitle" class="fe-grade-print-block__subtitle">{{ subtitle }}</p>
    </header>

    <p v-if="!hasData" class="fe-grade-print-block__empty muted">등급 통계를 표시할 데이터가 없습니다.</p>

    <div v-else class="fe-grade-print-block__grid" :class="{ 'fe-grade-print-block__grid--single': !dual }">
      <div v-for="dim in dimensions" :key="dim.key" class="fe-grade-print-block__col">
        <h4 class="fe-grade-print-block__dim-title">{{ dim.label }}</h4>
        <div class="fe-grade-print-block__chart-row">
          <FeGradeStatsDonutSvg
            :block="dim.block"
            :size="donutSize"
            :dimension-label="dim.label"
          />
          <ul class="fe-grade-print-block__legend">
            <li v-for="g in gradeOrder" :key="`${dim.key}-${g}`">
              <span class="fe-grade-print-block__swatch" :class="`fe-grade-print-block__swatch--${g.toLowerCase()}`" />
              <span class="fe-grade-print-block__legend-grade">{{ g }}</span>
              <span class="fe-grade-print-block__legend-count">{{ dim.gradeCount(g) }}명</span>
              <span class="fe-grade-print-block__legend-pct">{{ dim.gradePct(g) }}%</span>
            </li>
          </ul>
        </div>
        <table class="fe-grade-print-block__table">
          <thead>
            <tr>
              <th>등급</th>
              <th>인원</th>
              <th>비율</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="g in gradeOrder" :key="`row-${dim.key}-${g}`">
              <td><span :class="['grade-pill', `grade-pill--${g.toLowerCase()}`]">{{ g }}</span></td>
              <td>{{ dim.gradeCount(g) }}명</td>
              <td>{{ dim.gradePct(g) }}%</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>합계</td>
              <td>{{ dim.block?.graded_total ?? 0 }}명</td>
              <td>100%</td>
            </tr>
            <tr v-if="dim.footNote">
              <td colspan="3" class="muted fe-grade-print-block__foot-note">{{ dim.footNote }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import FeGradeStatsDonutSvg from "@/components/functional-eval/FeGradeStatsDonutSvg.vue";
import type { GradeStatBlock, GradeStatsPayload } from "@/components/functional-eval/FeGradeStatsPanel.vue";

const props = withDefaults(
  defineProps<{
    stats: GradeStatsPayload | null;
    title?: string;
    subtitle?: string;
    dual?: boolean;
    activeDimension?: "functional" | "safety";
    donutSize?: number;
  }>(),
  { dual: true, donutSize: 130 },
);

const gradeOrder = ["S", "A", "B", "C"] as const;

function gradeCount(block: GradeStatBlock | null | undefined, code: string) {
  return block?.grades?.[code]?.count ?? 0;
}

function gradePct(block: GradeStatBlock | null | undefined, code: string) {
  return block?.grades?.[code]?.pct ?? 0;
}

function footNoteFor(block: GradeStatBlock | null | undefined) {
  if (!block) return "";
  const parts: string[] = [];
  const erp = block.erp_headcount;
  if (erp != null && erp > 0 && erp !== block.workers_total) {
    parts.push(`출역 ${block.workers_total ?? 0}명 / ERP ${erp}명`);
  }
  if (block.ungraded_count) {
    parts.push(`미평가 ${block.ungraded_count}명 (비율 제외)`);
  }
  return parts.join(" · ");
}

const dimensions = computed(() => {
  const stats = props.stats;
  const all = [
    {
      key: "functional" as const,
      label: "2-1 기능",
      block: stats?.functional ?? null,
      gradeCount: (g: string) => gradeCount(stats?.functional, g),
      gradePct: (g: string) => gradePct(stats?.functional, g),
      footNote: footNoteFor(stats?.functional),
    },
    {
      key: "safety" as const,
      label: "2-2 안전",
      block: stats?.safety ?? null,
      gradeCount: (g: string) => gradeCount(stats?.safety, g),
      gradePct: (g: string) => gradePct(stats?.safety, g),
      footNote: footNoteFor(stats?.safety),
    },
  ];
  if (props.dual) return all;
  const key = props.activeDimension ?? "functional";
  return all.filter((d) => d.key === key);
});

const hasData = computed(() =>
  dimensions.value.some(
    (d) => (d.block?.workers_total ?? 0) > 0 || (d.block?.graded_total ?? 0) > 0,
  ),
);
</script>

<style scoped>
.fe-grade-print-block {
  break-inside: avoid;
}
.fe-grade-print-block__head {
  margin-bottom: 10px;
}
.fe-grade-print-block__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.fe-grade-print-block__subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}
.fe-grade-print-block__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.fe-grade-print-block__grid--single {
  grid-template-columns: 1fr;
}
.fe-grade-print-block__dim-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}
.fe-grade-print-block__chart-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}
.fe-grade-print-block__legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
  font-size: 12px;
  align-self: center;
}
.fe-grade-print-block__legend li {
  display: grid;
  grid-template-columns: 10px 18px 36px 36px;
  gap: 4px;
  align-items: center;
}
.fe-grade-print-block__swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.fe-grade-print-block__swatch--s { background: #16a34a; }
.fe-grade-print-block__swatch--a { background: #2563eb; }
.fe-grade-print-block__swatch--b { background: #d97706; }
.fe-grade-print-block__swatch--c { background: #dc2626; }
.fe-grade-print-block__legend-grade {
  font-weight: 700;
}
.fe-grade-print-block__legend-pct,
.fe-grade-print-block__legend-count {
  font-variant-numeric: tabular-nums;
  color: #334155;
}
.fe-grade-print-block__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.fe-grade-print-block__table th,
.fe-grade-print-block__table td {
  border: 1px solid #e2e8f0;
  padding: 5px 8px;
  text-align: left;
}
.fe-grade-print-block__table th {
  background: #f8fafc;
  font-weight: 600;
}
.fe-grade-print-block__foot-note {
  font-size: 11px;
  text-align: right;
}
.fe-grade-print-block__empty {
  font-size: 13px;
  padding: 8px 0;
}
.grade-pill {
  display: inline-block;
  min-width: 22px;
  text-align: center;
  font-weight: 700;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.grade-pill--s { background: #dcfce7; color: #166534; }
.grade-pill--a { background: #dbeafe; color: #1d4ed8; }
.grade-pill--b { background: #ffedd5; color: #c2410c; }
.grade-pill--c { background: #fee2e2; color: #b91c1c; }
.muted {
  color: #64748b;
}
</style>
