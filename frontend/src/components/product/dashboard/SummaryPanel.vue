<script setup lang="ts">
import { RouterLink } from "vue-router";
import BaseCard from "../BaseCard.vue";
import StatusBadge from "../StatusBadge.vue";

export interface OpinionRow {
  id: number;
  category: string;
  content: string;
  status: string;
  created_at?: string;
}

export interface TopSiteDocRow {
  site_id: number | null;
  name: string;
  pct: number;
  count: number;
}

defineProps<{
  opinions: OpinionRow[];
  topSitesByDocs: TopSiteDocRow[];
}>();

function initials(text: string) {
  const t = (text || "").trim();
  if (!t) return "?";
  return t.slice(0, 2);
}

function truncate(s: string, n: number) {
  if (!s) return "";
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

function formatTime(iso: string | undefined) {
  if (!iso) return "—";
  return iso.slice(0, 16).replace("T", " ");
}

function opinionTone(status: string): "success" | "warn" | "danger" {
  if (status === "ACTIONED") return "success";
  if (status === "HOLD") return "danger";
  return "warn";
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <BaseCard class="panel-side-inner !p-4 !shadow-none">
      <template #head>
        <div class="flex w-full items-center justify-between gap-2">
          <h2 class="m-0 text-sm font-semibold text-slate-500">최근 의견</h2>
          <RouterLink class="text-[13px] font-medium text-slate-400 hover:underline" :to="{ name: 'hq-safe-opinions' }">
            전체
          </RouterLink>
        </div>
      </template>
      <ul class="m-0 list-none p-0">
        <li
          v-for="op in opinions"
          :key="op.id"
          class="flex gap-2.5 border-b border-slate-100 py-2.5 last:border-b-0"
        >
          <div
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-[11px] font-bold text-slate-600"
            :title="op.category"
          >
            {{ initials(op.category) }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-baseline justify-between gap-2">
              <span class="text-[13px] font-semibold text-slate-700">{{ op.category }}</span>
              <span class="shrink-0 text-xs text-slate-400">#{{ op.id }}</span>
            </div>
            <div class="mt-1 text-[13px] text-slate-600">{{ truncate(op.content, 48) }}</div>
            <div class="mt-2 flex items-center gap-2.5">
              <StatusBadge :tone="opinionTone(op.status)">{{ op.status }}</StatusBadge>
              <span class="text-xs text-slate-400">{{ formatTime(op.created_at) }}</span>
            </div>
          </div>
        </li>
        <li v-if="opinions.length === 0" class="py-5 text-center text-[13px] text-slate-400">의견 데이터가 없습니다.</li>
      </ul>
    </BaseCard>

    <BaseCard class="panel-side-inner zone-panel !p-4 !shadow-none">
      <h2 class="m-0 text-sm font-semibold text-slate-500">현장별 문서 건수 (상위)</h2>
      <p class="mb-3 mt-1 text-[11px] text-slate-400">사이트별 문서 집계 (API)</p>
      <ul class="m-0 list-none p-0">
        <li v-for="row in topSitesByDocs" :key="row.site_id ?? 'none'" class="mb-3 last:mb-0">
          <div class="mb-1 text-xs font-semibold leading-snug text-slate-600">{{ row.name }}</div>
          <div class="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div class="h-full rounded-full bg-slate-400 transition-[width] duration-200" :style="{ width: row.pct + '%' }" />
          </div>
          <div class="mt-1 text-[11px] text-slate-400">{{ row.count }}건</div>
        </li>
        <li v-if="topSitesByDocs.length === 0" class="py-5 text-center text-[13px] text-slate-400">집계 데이터가 없습니다.</li>
      </ul>
    </BaseCard>
  </div>
</template>
