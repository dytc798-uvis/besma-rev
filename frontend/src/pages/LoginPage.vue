<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh">
    <div class="card" style="width: 360px">
      <div class="card-title">BESMA Local MVP 로그인</div>
      <p v-if="entryLabel" style="font-size: 12px; color: #334155; margin: 0 0 8px">
        {{ entryLabel }}
      </p>
      <form @submit.prevent="handleLogin" style="display: flex; flex-direction: column; gap: 8px">
        <label>
          <div style="font-size: 12px; margin-bottom: 2px">로그인 ID</div>
          <input v-model="loginId" type="text" autocomplete="username" />
        </label>
        <label>
          <div style="font-size: 12px; margin-bottom: 2px">비밀번호</div>
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>
        <button class="primary" type="submit" :disabled="loading">
          {{ loading ? "로그인 중..." : "로그인" }}
        </button>
        <p v-if="errorMessage" style="color: #dc2626; font-size: 12px; margin: 0">
          {{ errorMessage }}
        </p>
        <p style="font-size: 12px; color: #6b7280; margin-top: 4px">
          샘플 계정: hqsafe1 / P@ssw0rd! (관리자), worker01 / P@ssw0rd! (근로자)
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const loginId = ref("hqsafe1");
const password = ref("P@ssw0rd!");
const loading = ref(false);
const errorMessage = ref("");

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const entryLabel = (() => {
  const entry = typeof route.query.entry === "string" ? route.query.entry : "";
  if (entry === "hq") return "본사 로그인";
  if (entry === "site") return "현장 로그인";
  return "";
})();

async function handleLogin() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await auth.login(loginId.value, password.value);
    if (auth.user?.must_change_password) {
      router.replace({ name: "change-password" });
      return;
    }
    const redirectPath = typeof route.query.redirect === "string" ? route.query.redirect : "";
    if (redirectPath) {
      router.push(redirectPath);
    } else if (auth.user?.role === "WORKER") {
      router.push({ name: "worker-mobile-list" });
    } else if (auth.user?.ui_type === "HQ_SAFE") {
      router.push({ name: "hq-safe-tbm-monitor" });
    } else if (auth.user?.ui_type === "SITE") {
      router.push({ name: "site-mobile-ops" });
    } else if (auth.user?.ui_type === "HQ_OTHER") {
      router.push({ name: "hq-other-dashboard" });
    } else {
      router.push({ name: "hq-safe-tbm-monitor" });
    }
  } catch (e) {
    console.error(e);
    if (axios.isAxiosError(e)) {
      const status = e.response?.status;
      const url = e.config?.url ?? "";
      if (status === 401 && url.includes("/auth/login")) {
        errorMessage.value = "로그인에 실패했습니다. ID/비밀번호를 확인하세요.";
      } else if (url.includes("/auth/me")) {
        errorMessage.value = "로그인은 성공했지만 사용자 정보 조회에 실패했습니다. 네트워크/CORS 설정을 확인하세요.";
      } else {
        errorMessage.value = "로그인은 요청되었지만 응답 처리 중 오류가 발생했습니다. 네트워크/CORS 설정을 확인하세요.";
      }
    } else {
      errorMessage.value = "로그인 처리 중 오류가 발생했습니다.";
    }
  } finally {
    loading.value = false;
  }
}
</script>

