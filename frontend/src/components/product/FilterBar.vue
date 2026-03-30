<script setup lang="ts">
defineOptions({ inheritAttrs: false });
</script>

<template>
  <div class="flex flex-wrap items-center gap-3" v-bind="$attrs">
    <slot />
  </div>
</template>
