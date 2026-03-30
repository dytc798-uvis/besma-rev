<script setup lang="ts">
import BaseCard from "../BaseCard.vue";

/**
 * TBM 화면용 카드 — 제목/액션 슬롯 또는 커스텀 #head 중 하나 사용
 */
withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
  }>(),
  {},
);
</script>

<template>
  <BaseCard v-if="$slots.head" class="mb-5">
    <template #head>
      <slot name="head" />
    </template>
    <slot />
  </BaseCard>
  <BaseCard v-else :title="title" :subtitle="subtitle" class="mb-5">
    <template #actions>
      <slot name="actions" />
    </template>
    <template #under-title>
      <slot name="under-title" />
    </template>
    <slot />
  </BaseCard>
</template>
