<script setup lang="ts">
defineProps<{
  lines: string[];
}>();
</script>

<template>
  <div class="explain-box">
    <p v-for="line in lines" :key="line">{{ line }}</p>
  </div>
</template>

<style scoped>
.explain-box {
  border: 1px solid #e2e8f0;
  border-left: 5px solid #2563eb;
  border-radius: 10px;
  background: #f8fafc;
  padding: 14px 16px;
  color: #475569;
  line-height: 1.5;
  font-size: 13px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.explain-box p {
  margin: 0 0 6px;
}

.explain-box p:last-child {
  margin-bottom: 0;
}
</style>
