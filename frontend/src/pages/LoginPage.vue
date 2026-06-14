<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh">
    <div class="card" style="width: 360px">
      <div class="card-title">BESMA CSMS 안전보건플랫폼 로그인</div>
        <p style="font-size: 11px; color: #64748b; margin: 0 0 10px">
          데모: 본사 <code>hq01</code> / 현장 <code>site01</code> — 비밀번호 <code>1111</code><br />
          기능인제 현장: ID = <strong>별칭-이름</strong> (예: 대우청라-박명식), PW = <strong>주민번호 앞 6자리</strong><br />
          기능인제·삼성인정제 본사: ID = <strong>안전보건-이름</strong> (예: 안전보건-김복수), PW = <strong>주민번호 앞 6자리</strong>
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
import { formatLoginError } from "@/utils/loginError";
import { siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";

const loginId = ref("");
const password = ref("");
const loading = ref(false);
const errorMessage = ref("");

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

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
    } else if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
      router.push({ name: "site-functional-eval" });
    } else if (auth.user?.ui_type === "SITE") {
      router.push({ name: siteMobileOrDesktopHomeName() });
    } else if (auth.user?.ui_type === "HQ_OTHER") {
      router.push({ name: "hq-other-dashboard" });
    } else {
      router.push({ name: "hq-safe-document-explorer" });
    }
  } catch (err) {
    errorMessage.value = formatLoginError(err);
  } finally {
    loading.value = false;
  }
}
</script>

