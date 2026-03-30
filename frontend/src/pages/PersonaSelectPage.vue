<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh">
    <div class="card" style="width: 520px">
      <div class="card-title">테스트 페르소나 선택</div>
      <p style="margin-top: 0; color: #6b7280; font-size: 13px">
        운영 권한은 변경하지 않고, 테스트 UI만 페르소나로 분기합니다.
      </p>
      <div style="display: grid; grid-template-columns: 1fr; gap: 10px">
        <button class="primary" @click="choose('HQ_ADMIN')">본사관리자 (HQ_ADMIN)</button>
        <button class="primary" @click="choose('SITE_MANAGER')">현장관리자 (SITE_MANAGER)</button>
        <button class="primary" @click="choose('WORKER')">근로자 (WORKER)</button>
      </div>
      <div style="margin-top: 12px; display: flex; justify-content: space-between">
        <button class="secondary" @click="logout">로그아웃</button>
        <button class="secondary" @click="goDefault">기존 역할로 진입</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuthStore, type TestPersona } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

function routeByPersona(persona: TestPersona) {
  if (persona === "HQ_ADMIN") {
    router.push({ name: "hq-safe-tbm-monitor" });
    return;
  }
  if (persona === "SITE_MANAGER") {
    router.push({ name: "site-mobile-ops" });
    return;
  }
  router.push({ name: "worker-mobile-list" });
}

function choose(persona: TestPersona) {
  auth.setPersona(persona);
  routeByPersona(persona);
}

function logout() {
  auth.logout();
  router.push({ name: "login" });
}

function goDefault() {
  auth.clearPersona();
  if (auth.user?.ui_type === "HQ_SAFE") {
    router.push({ name: "hq-safe-tbm-monitor" });
    return;
  }
  if (auth.user?.ui_type === "SITE") {
    router.push({ name: "site-mobile-ops" });
    return;
  }
  router.push({ name: "hq-other-dashboard" });
}
</script>
