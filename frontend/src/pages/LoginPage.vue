<template>
  <div class="login-page">
    <div class="login-stack">
      <img :src="ONLY_LOGO_SRC" :alt="BRAND_ALT" class="login-only-logo" width="360" height="auto" />
      <div class="card login-card">
        <div class="card-title login-card-title">안전보건플랫폼 로그인</div>
        <form class="login-form" @submit.prevent="handleLogin">
          <label>
            <div class="login-label">로그인 ID</div>
            <input v-model="loginId" type="text" autocomplete="username" />
          </label>
          <label>
            <div class="login-label">비밀번호</div>
            <input v-model="password" type="password" autocomplete="current-password" />
          </label>
          <button class="primary" type="submit" :disabled="loading">
            {{ loading ? "로그인 중..." : "로그인" }}
          </button>
          <p v-if="errorMessage" class="login-error" role="alert">{{ errorMessage }}</p>
        </form>

        <div class="login-issue-block">
          <p class="login-issue-text">아이디를 받지 못하셨나요?</p>
          <button type="button" class="secondary login-issue-btn" @click="showIssueModal = true">
            아이디 발급
          </button>
        </div>
      </div>
    </div>

    <AccountIssueModal v-if="showIssueModal" @close="showIssueModal = false" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AccountIssueModal from "@/components/auth/AccountIssueModal.vue";
import { BRAND_ALT, ONLY_LOGO_SRC } from "@/constants/branding";
import { FE_GUIDE_SAMPLE_LOGIN, isFeGuidePreview } from "@/utils/feGuidePreview";
import { formatLoginError } from "@/utils/loginError";
import { siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";
import { hqSafeHomeRouteName } from "@/utils/hqHomeRoute";

const loginId = ref("");
const password = ref("");
const loading = ref(false);
const errorMessage = ref("");
const showIssueModal = ref(false);

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

onMounted(() => {
  if (!isFeGuidePreview()) return;
  const role = typeof route.query.guideRole === "string" ? route.query.guideRole : "team";
  const sample = FE_GUIDE_SAMPLE_LOGIN[role as keyof typeof FE_GUIDE_SAMPLE_LOGIN] ?? FE_GUIDE_SAMPLE_LOGIN.team;
  loginId.value = sample.loginId;
  password.value = sample.password;
});

async function handleLogin() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await auth.login(loginId.value, password.value);
    if (auth.needsFeOnboarding) {
      router.replace({ name: "fe-onboarding" });
      return;
    }
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
      router.push({ name: hqSafeHomeRouteName() });
    } else if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
      router.push({ name: "site-functional-eval" });
    } else if (auth.user?.ui_type === "SITE") {
      router.push({ name: siteMobileOrDesktopHomeName() });
    } else if (auth.user?.ui_type === "HQ_OTHER") {
      router.push({ name: "hq-other-dashboard" });
    } else {
      router.push({ name: hqSafeHomeRouteName() });
    }
  } catch (err) {
    errorMessage.value = formatLoginError(err);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 16px;
  background: #f5f6f8;
}

.login-stack {
  width: 360px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
}

.login-only-logo {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
}

.login-card {
  width: 100%;
  box-sizing: border-box;
}

.login-card-title {
  text-align: center;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.login-label {
  font-size: 12px;
  margin-bottom: 2px;
}

.login-error {
  color: #dc2626;
  font-size: 12px;
  margin: 0;
}

.login-issue-block {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
  text-align: center;
}

.login-issue-text {
  margin: 0 0 8px;
  font-size: 13px;
  color: #64748b;
}

.login-issue-btn {
  width: 100%;
  min-height: 40px;
}
</style>
