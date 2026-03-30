<script setup lang="ts">
import { computed } from "vue";
import StatusBadge from "./StatusBadge.vue";

const props = withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    accent: "blue" | "orange" | "red" | "slate";
    progressPct?: number;
    footerNote?: string;
    badgeText?: string;
    badgeTone?: "success" | "warn" | "danger" | "neutral" | "info";
    /** 긴 텍스트 값(근로자 카드 등)용 축소 타이포 */
    compact?: boolean;
  }>(),
  {
    progressPct: undefined,
    footerNote: undefined,
    badgeText: undefined,
    badgeTone: "neutral",
    compact: false,
  },
);

const topBorder = computed(
  () =>
    ({
      blue: "border-t-blue-600",
      orange: "border-t-orange-600",
      red: "border-t-red-600",
      slate: "border-t-slate-400",
    })[props.accent],
);

const barColor = computed(
  () =>
    ({
      blue: "#2563eb",
      orange: "#ea580c",
      red: "#dc2626",
      slate: "#64748b",
    })[props.accent],
);
</script>

<template>
  <article
    class="relative overflow-hidden rounded-xl border border-slate-200 bg-white px-[22px] pb-5 pt-[22px] shadow-sm border-t-4"
    :class="topBorder"
  >
    <div class="flex items-start justify-between gap-2.5">
      <span class="text-[11px] font-bold uppercase tracking-wider text-slate-500">{{ label }}</span>
      <StatusBadge v-if="badgeText" :tone="badgeTone">{{ badgeText }}</StatusBadge>
    </div>
    <div
      :class="
        compact
          ? 'mt-3 text-lg font-bold leading-snug tracking-tight text-slate-900'
          : 'mt-3 text-4xl font-bold leading-none tracking-tight text-slate-900'
      "
    >
      {{ value }}
    </div>
    <p v-if="footerNote" class="mt-2.5 text-xs leading-snug text-slate-500">{{ footerNote }}</p>
    <div v-if="progressPct != null" class="mt-3.5 h-2.5 overflow-hidden rounded-full bg-slate-100">
      <div
        class="h-full rounded-full transition-[width] duration-200 ease-out"
        :style="{
          width: `${Math.min(100, Math.max(0, progressPct))}%`,
          background: barColor,
        }"
      />
    </div>
  </article>
</template>
