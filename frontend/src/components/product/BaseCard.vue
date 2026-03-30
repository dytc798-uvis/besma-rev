<script setup lang="ts">
defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
  }>(),
  {},
);
</script>

<template>
  <section
    class="rounded-xl border border-slate-200 bg-white px-[22px] py-5 shadow-sm"
    v-bind="$attrs"
  >
    <header v-if="$slots.head" class="mb-[18px]">
      <slot name="head" />
    </header>
    <header
      v-else-if="title || subtitle || $slots.actions || $slots['under-title']"
      class="mb-[18px] flex items-start justify-between gap-4"
    >
      <div class="min-w-0 flex-1">
        <h2 v-if="title" class="m-0 text-[17px] font-bold text-slate-900">{{ title }}</h2>
        <p v-if="subtitle" class="mt-1.5 text-[13px] leading-snug text-slate-500">{{ subtitle }}</p>
        <slot name="under-title" />
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 flex-wrap gap-2">
        <slot name="actions" />
      </div>
    </header>
    <div class="body">
      <slot />
    </div>
  </section>
</template>
