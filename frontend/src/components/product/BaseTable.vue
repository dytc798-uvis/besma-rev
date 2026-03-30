<script setup lang="ts">
defineOptions({ inheritAttrs: false });
</script>

<template>
  <div class="stitch-table-shell" v-bind="$attrs">
    <table class="stitch-table">
      <slot />
    </table>
  </div>
</template>
