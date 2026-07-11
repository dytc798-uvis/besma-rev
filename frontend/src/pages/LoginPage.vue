<template>
  <div class="login-page">
    <div class="login-hero" aria-hidden="true">
      <img :src="ONLY_LOGO_SRC" alt="" class="login-bg-logo" />
    </div>

    <div class="login-stack">
      <div class="login-card">
        <div class="login-card-title">안전보건플랫폼 로그인</div>
        <form class="login-form" @submit.prevent="handleLogin">
          <label>
            <div class="login-label">로그인 ID</div>
            <input
              v-model="loginId"
              type="text"
              autocomplete="username"
              placeholder="BESMA 아이디 또는 ERP 아이디"
            />
          </label>
          <label>
            <div class="login-label">비밀번호</div>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="기존 비밀번호 또는 초기 비밀번호"
            />
          </label>
          <button class="primary login-submit" type="submit" :disabled="loading">
            {{ loading ? "로그인 중..." : "로그인" }}
          </button>
          <p class="login-mobile-tip">
            현장 소장님은 BESMA 아이디 또는 ERP 아이디로 로그인할 수 있습니다. 비밀번호는 기존 BESMA 비밀번호 또는 안내받은 초기 비밀번호를 입력해 주세요.
          </p>
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
import { ONLY_LOGO_SRC } from "@/constants/branding";
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
  auth.prepareLoginPage();
  if (!isFeGuidePreview()) return;
  const role = typeof route.query.guideRole === "string" ? route.query.guideRole : "team";
  const sample = FE_GUIDE_SAMPLE_LOGIN[role as keyof typeof FE_GUIDE_SAMPLE_LOGIN] ?? FE_GUIDE_SAMPLE_LOGIN.team;
  loginId.value = sample.loginId;
  password.value = sample.password;
});

async function handleLogin() {
  if (loading.value) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    await auth.login(loginId.value, password.value);
    if (!auth.user) {
      errorMessage.value = "로그인은 되었으나 사용자 정보를 불러오지 못했습니다. 다시 시도해 주세요.";
      return;
    }
    if (auth.needsFeOnboarding) {
      await router.replace({ name: "fe-onboarding" });
      return;
    }
    if (auth.user?.must_change_password) {
      await router.replace({ name: "change-password" });
      return;
    }
    const redirectPath = typeof route.query.redirect === "string" ? route.query.redirect : "";
    if (redirectPath) {
      await router.push(redirectPath);
    } else if (auth.user?.role === "WORKER") {
      await router.push({ name: "worker-mobile-list" });
    } else if (auth.user?.ui_type === "HQ_SAFE") {
      await router.push({ name: hqSafeHomeRouteName() });
    } else if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
      await router.push({ name: "site-functional-eval-field-form-uploads" });
    } else if (auth.user?.ui_type === "SITE") {
      await router.push({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
    } else if (auth.user?.ui_type === "HQ_OTHER") {
      await router.push({ name: "hq-other-field-form-uploads" });
    } else {
      await router.push({ name: hqSafeHomeRouteName() });
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
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 24px 16px;
  overflow: hidden;
  background:
    radial-gradient(ellipse 80% 60% at 50% 38%, rgba(255, 255, 255, 0.9) 0%, transparent 70%),
    linear-gradient(165deg, #e8edf5 0%, #f4f6fa 42%, #eef2f8 100%);
}

.login-hero {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 0;
}

.login-bg-logo {
  width: min(94vw, 620px);
  max-height: min(72vh, 620px);
  object-fit: contain;
  opacity: 0.38;
  transform: translateY(-6%);
  filter: drop-shadow(0 18px 48px rgba(15, 23, 42, 0.08));
}

.login-stack {
  position: relative;
  z-index: 1;
  width: min(100%, 380px);
}

.login-card {
  box-sizing: border-box;
  width: 100%;
  padding: 22px 20px 18px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.58);
  background: rgba(255, 255, 255, 0.56);
  backdrop-filter: blur(18px) saturate(1.25);
  -webkit-backdrop-filter: blur(18px) saturate(1.25);
  box-shadow:
    0 10px 40px rgba(15, 23, 42, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
}

.login-card-title {
  text-align: center;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 14px;
  letter-spacing: -0.02em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.login-form label {
  display: block;
}

.login-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 4px;
}

.login-form :deep(input[type="text"]),
.login-form :deep(input[type="password"]) {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(148, 163, 184, 0.55);
  background: rgba(255, 255, 255, 0.88);
  color: #0f172a;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.04);
}

.login-form :deep(input[type="text"]:focus),
.login-form :deep(input[type="password"]:focus) {
  outline: none;
  border-color: rgba(37, 99, 235, 0.65);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}

.login-submit {
  margin-top: 4px;
  min-height: 42px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
}

.login-mobile-tip {
  margin: 2px 0 0;
  padding: 9px 10px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  background: rgba(239, 246, 255, 0.68);
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.45;
  word-break: keep-all;
}

.login-error {
  color: #dc2626;
  font-size: 12px;
  font-weight: 500;
  margin: 0;
}

.login-issue-block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.28);
  text-align: center;
}

.login-issue-text {
  margin: 0 0 8px;
  font-size: 13px;
  color: #475569;
}

.login-issue-btn {
  width: 100%;
  min-height: 40px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.45);
  font-weight: 600;
}

@media (max-width: 420px) {
  .login-bg-logo {
    width: min(108vw, 520px);
    opacity: 0.32;
  }

  .login-card {
    padding: 20px 16px 16px;
    border-radius: 16px;
  }
}
</style>


