<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh">
    <div class="card" style="width: 360px">
      <div class="card-title">BESMA 임시플랫폼 로그인</div>
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
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const loginId = ref("");
const password = ref("");
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
      router.push({ name: "hq-safe-document-explorer" });
    } else if (auth.user?.ui_type === "SITE") {
      router.push({ name: "site-mobile-ops" });
    } else if (auth.user?.ui_type === "HQ_OTHER") {
      router.push({ name: "hq-other-dashboard" });
    } else {
      router.push({ name: "hq-safe-document-explorer" });
    }
  } catch {
    errorMessage.value = "로그인에 실패했습니다.";
  } finally {
    loading.value = false;
  }
}
</script>

