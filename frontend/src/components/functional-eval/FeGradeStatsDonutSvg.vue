<template>
  <div class="fe-donut-svg" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg
      :width="size"
      :height="size"
      :viewBox="`0 0 ${size} ${size}`"
      role="img"
      :aria-label="ariaLabel"
    >
      <circle
        v-if="!segments.length"
        :cx="center"
        :cy="center"
        :r="outerR"
        fill="#e2e8f0"
      />
      <path
        v-for="(seg, idx) in segments"
        :key="`${seg.grade}-${idx}`"
        :d="seg.path"
        :fill="seg.color"
      />
      <circle :cx="center" :cy="center" :r="innerR" fill="#fff" />
      <text :x="center" :y="center - 6" text-anchor="middle" class="fe-donut-svg__total">{{ workersTotal }}</text>
      <text :x="center" :y="center + 10" text-anchor="middle" class="fe-donut-svg__label">근로자</text>
      <text
        v-if="block?.graded_total"
        :x="center"
        :y="center + 22"
        text-anchor="middle"
        class="fe-donut-svg__sub"
      >
        평가 {{ block.graded_total }}<tspan v-if="block.is_demo"> (가상)</tspan>
      </text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { GradeStatBlock } from "@/components/functional-eval/FeGradeStatsPanel.vue";

const props = withDefaults(
  defineProps<{
    block: GradeStatBlock | null | undefined;
    size?: number;
    dimensionLabel?: string;
  }>(),
  { size: 140, dimensionLabel: "등급" },
);

const gradeOrder = ["S", "A", "B", "C"] as const;
const GRADE_COLORS: Record<string, string> = {
  S: "#16a34a",
  A: "#2563eb",
  B: "#d97706",
  C: "#dc2626",
};

const center = computed(() => props.size / 2);
const outerR = computed(() => props.size / 2 - 2);
const innerR = computed(() => outerR.value * 0.58);

const workersTotal = computed(() => {
  const block = props.block;
  if (!block) return 0;
  return Number(block.workers_total ?? block.graded_total ?? 0);
});

const ariaLabel = computed(() => {
  const parts = gradeOrder.map((g) => {
    const cnt = props.block?.grades?.[g]?.count ?? 0;
    return cnt > 0 ? `${g} ${cnt}명` : "";
  }).filter(Boolean);
  return `${props.dimensionLabel} 등급 분포 ${parts.join(", ") || "데이터 없음"}`;
});

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function segmentPath(cx: number, cy: number, outer: number, inner: number, startDeg: number, endDeg: number) {
  const sweep = endDeg - startDeg;
  if (sweep >= 359.99) {
    return [
      `M ${cx} ${cy - outer}`,
      `A ${outer} ${outer} 0 1 1 ${cx - 0.01} ${cy - outer}`,
      `L ${cx - 0.01} ${cy - inner}`,
      `A ${inner} ${inner} 0 1 0 ${cx} ${cy - inner}`,
      "Z",
    ].join(" ");
  }
  const startOuter = polar(cx, cy, outer, startDeg);
  const endOuter = polar(cx, cy, outer, endDeg);
  const startInner = polar(cx, cy, inner, endDeg);
  const endInner = polar(cx, cy, inner, startDeg);
  const largeArc = sweep > 180 ? 1 : 0;
  return [
    `M ${startOuter.x} ${startOuter.y}`,
    `A ${outer} ${outer} 0 ${largeArc} 1 ${endOuter.x} ${endOuter.y}`,
    `L ${startInner.x} ${startInner.y}`,
    `A ${inner} ${inner} 0 ${largeArc} 0 ${endInner.x} ${endInner.y}`,
    "Z",
  ].join(" ");
}

const segments = computed(() => {
  const block = props.block;
  if (!block?.graded_total) return [];
  let angle = 0;
  const cx = center.value;
  const cy = center.value;
  const out = outerR.value;
  const inn = innerR.value;
  const items: { grade: string; color: string; path: string }[] = [];
  for (const g of gradeOrder) {
    const cnt = block.grades?.[g]?.count ?? 0;
    if (cnt <= 0) continue;
    const sweep = (360 * cnt) / block.graded_total;
    items.push({
      grade: g,
      color: GRADE_COLORS[g],
      path: segmentPath(cx, cy, out, inn, angle, angle + sweep),
    });
    angle += sweep;
  }
  return items;
});
</script>

<style scoped>
.fe-donut-svg {
  flex-shrink: 0;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.fe-donut-svg__total {
  font-size: 18px;
  font-weight: 700;
  fill: #0f172a;
}
.fe-donut-svg__label {
  font-size: 9px;
  fill: #64748b;
}
.fe-donut-svg__sub {
  font-size: 8px;
  fill: #475569;
}
</style>
