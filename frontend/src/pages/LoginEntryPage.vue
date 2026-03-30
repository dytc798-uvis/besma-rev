<template>
  <div class="entry-shell">
    <div class="card entry-card">
      <h1 class="entry-title">로그인 선택</h1>
      <div class="entry-actions">
        <button class="primary entry-btn" type="button" @click="goHQ">본사 로그인</button>
        <button class="secondary entry-btn" type="button" @click="goSite">현장 로그인</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

function goHQ() {
  router.push({ name: "login", query: { entry: "hq" } });
}

function goSite() {
  router.push({ name: "login", query: { entry: "site" } });
}
</script>

<style scoped>
.entry-shell {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
}

.entry-card {
  width: 360px;
}

.entry-title {
  margin: 0 0 12px;
  font-size: 22px;
  color: #0f172a;
}

.entry-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.entry-btn {
  min-height: 44px;
  font-size: 15px;
}
</style>

