<script setup lang="ts">
import StatusBadge from "../StatusBadge.vue";

defineProps<{
  siteName: string;
  siteCode: string;
  compliance: { label: string; tone: "safe" | "warn" | "danger"; pct: number };
  notSubmitted: number;
  rejected: number;
}>();

function badgeTone(t: "safe" | "warn" | "danger"): "success" | "warn" | "danger" {
  if (t === "safe") return "success";
  if (t === "warn") return "warn";
  return "danger";
}
</script>

<template>
  <article class="rounded-[10px] border border-slate-200 bg-white shadow-sm">
    <div class="px-[18px] pb-4 pt-[18px]">
      <div class="flex items-start justify-between gap-2.5">
        <h3 class="m-0 min-w-0 flex-1 text-[15px] font-bold leading-snug text-slate-900">
          {{ siteName }}
        </h3>
        <StatusBadge :tone="badgeTone(compliance.tone)">{{ compliance.label }}</StatusBadge>
      </div>
      <p class="mb-0 mt-1.5 text-xs font-medium text-slate-400">#{{ siteCode }}</p>
      <div class="mt-3.5 flex items-baseline gap-0.5">
        <span class="text-4xl font-bold leading-none tracking-tight text-slate-900">{{ compliance.pct }}</span>
        <span class="text-xl font-semibold text-slate-500">%</span>
      </div>
      <p class="mb-0 mt-1.5 text-xs leading-snug text-slate-500">문서 제출 지표 · 미제출/반려 반영</p>
      <p class="mb-0 mt-2.5 text-xs text-slate-400">미제출 {{ notSubmitted }}건 · 반려 {{ rejected }}건</p>
    </div>
  </article>
</template>
