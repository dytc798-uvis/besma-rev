<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "success" | "warn" | "danger" | "neutral" | "info";
  }>(),
  { tone: "neutral" },
);
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold leading-tight"
    :class="{
      'bg-[#dcfce7] text-[#166534]': tone === 'success',
      'bg-[#ffedd5] text-[#c2410c]': tone === 'warn',
      'bg-[#fee2e2] text-[#b91c1c]': tone === 'danger',
      'bg-[#f1f5f9] text-[#475569]': tone === 'neutral',
      'bg-[#dbeafe] text-[#1e40af]': tone === 'info',
    }"
  >
    <slot />
  </span>
</template>
