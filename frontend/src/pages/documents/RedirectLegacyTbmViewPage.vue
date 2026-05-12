<template>
  <div class="redirect-page">
    <p>이전 TBM 화면 경로는 더 이상 사용하지 않습니다. 문서 상세로 이동합니다…</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

onMounted(() => {
  const id = String(route.params.id ?? "");
  const name = String(route.name ?? "");
  if (!id) {
    void router.replace({ name: "login" });
    return;
  }
  let target: string;
  if (name.startsWith("hq-safe")) target = `/hq-safe/documents/${id}`;
  else if (name.startsWith("site")) target = `/site/documents/${id}`;
  else if (name.startsWith("hq-other")) target = `/hq-other/documents/${id}`;
  else target = `/hq-safe/documents/${id}`;
  void router.replace(target);
});
</script>

<style scoped>
.redirect-page {
  padding: 24px;
  color: #475569;
  font-size: 14px;
}
</style>
