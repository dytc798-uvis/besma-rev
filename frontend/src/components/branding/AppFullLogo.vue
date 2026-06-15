<template>
  <div class="app-full-logo-wrap" :class="{ 'app-full-logo-wrap--compact': compact }">
    <img :src="FULL_LOGO_SRC" :alt="BRAND_ALT" class="app-full-logo" />
  </div>
</template>

<script setup lang="ts">
import { BRAND_ALT, FULL_LOGO_SRC } from "@/constants/branding";

defineProps<{
  compact?: boolean;
}>();
</script>
