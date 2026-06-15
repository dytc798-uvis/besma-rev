<template>
  <div class="onboarding-shell">
    <div class="card onboarding-card">
      <template v-if="step === 'password'">
        <div class="card-title">최초 로그인 설정</div>
        <p class="onboarding-lead">보안을 위해 비밀번호를 변경해 주세요.</p>

        <form class="onboarding-form" @submit.prevent="handleChangePassword">
          <label>
            <span>현재 비밀번호</span>
            <input v-model="currentPassword" type="password" autocomplete="current-password" />
          </label>
          <label>
            <span>새 비밀번호</span>
            <input v-model="newPassword" type="password" autocomplete="new-password" />
          </label>
          <label>
            <span>새 비밀번호 확인</span>
            <input v-model="newPasswordConfirm" type="password" autocomplete="new-password" />
          </label>
          <button class="primary" type="submit" :disabled="loading">
            {{ loading ? "변경 중…" : consentNext ? "다음" : "완료" }}
          </button>
          <p v-if="errorMessage" class="onboarding-error" role="alert">{{ errorMessage }}</p>
        </form>
      </template>

      <template v-else-if="step === 'consent'">
        <div class="card-title">{{ consentTitle }}</div>
        <p class="onboarding-lead">{{ consentLead }}</p>
        <FeConsentGate :open="true" :prefill="consentPrefill" @completed="handleConsentCompleted" />
      </template>

      <template v-else>
        <div class="card-title">설정 완료</div>
        <p class="onboarding-lead">비밀번호 변경 및 동의서 서명이 완료되었습니다.</p>
        <p class="onboarding-sub">이제 기능인인정제를 이용할 수 있습니다.</p>
        <button class="primary onboarding-done-btn" type="button" @click="goHome">시작하기</button>
      </template>

      <p class="onboarding-logout">
        <button type="button" class="secondary" @click="handleLogout">다른 계정으로 로그인</button>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import FeConsentGate from "@/components/functional-eval/FeConsentGate.vue";
import { useFeConsentCheck } from "@/composables/useFeConsentCheck";
import { siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";
import { hqSafeHomeRouteName } from "@/utils/hqHomeRoute";

const router = useRouter();
const auth = useAuthStore();
const { consentPrefill, checkConsent, onConsentCompleted: markConsentDone } = useFeConsentCheck();

const currentPassword = ref("");
const newPassword = ref("");
const newPasswordConfirm = ref("");
const loading = ref(false);
const errorMessage = ref("");
const step = ref<"password" | "consent" | "done">("password");

const consentNext = computed(() => auth.needsFeConsent && auth.feConsentRequired);

const isFeViewer = computed(() => auth.user?.role === "FUNCTIONAL_EVAL_VIEWER");
const consentTitle = computed(
  () =>
    (consentPrefill.value?.consent_title as string | undefined) ||
    (isFeViewer.value
      ? "기능인인정제 평가정보 조회 및 비밀유지 동의서"
      : "기능인인정제 평가 수행 및 전자서명 동의서"),
);
const consentLead = computed(() =>
  isFeViewer.value
    ? "조회한 평가정보를 무단 복사·배포하지 않으며, 업무 목적 범위 내에서만 조회함을 확인합니다."
    : "평가 업무 수행, 전자서명 및 평가 내용에 대한 책임 사항을 확인하였으며 이에 동의합니다.",
);

function resolveStep() {
  if (auth.mustChangePassword) {
    step.value = "password";
    return;
  }
  if (auth.needsFeConsent && auth.feConsentRequired) {
    step.value = "consent";
    return;
  }
  step.value = "done";
}

onMounted(async () => {
  if (!auth.user) {
    await auth.loadMe({ skipAuthRedirect: true });
  }
  resolveStep();
  if (step.value === "consent") {
    await checkConsent();
  }
  if (step.value === "done") {
    void goHome();
  }
});

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data?.detail;
    if (typeof d === "string") {
      if (d === "CURRENT_PASSWORD_INCORRECT") return "현재 비밀번호가 올바르지 않습니다.";
      if (d === "NEW_PASSWORD_CONFIRM_MISMATCH") return "새 비밀번호 확인이 일치하지 않습니다.";
      return d;
    }
  }
  return "요청을 처리할 수 없습니다.";
}

async function handleChangePassword() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await api.post("/auth/change-password", {
      current_password: currentPassword.value,
      new_password: newPassword.value,
      new_password_confirm: newPasswordConfirm.value,
    });
    await auth.loadMe({ skipAuthRedirect: true });
    if (auth.needsFeConsent && auth.feConsentRequired) {
      step.value = "consent";
      await checkConsent();
      return;
    }
    step.value = "done";
    await goHome();
  } catch (e) {
    errorMessage.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function handleConsentCompleted() {
  markConsentDone();
  await auth.loadMe({ skipAuthRedirect: true });
  step.value = "done";
}

async function goHome() {
  await auth.loadMe({ skipAuthRedirect: true });
  if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
    await router.replace({ name: "site-functional-eval" });
    return;
  }
  if (auth.user?.ui_type === "HQ_SAFE") {
    await router.replace({ name: hqSafeHomeRouteName() });
    return;
  }
  if (auth.user?.ui_type === "SITE") {
    await router.replace({ name: siteMobileOrDesktopHomeName() });
    return;
  }
  await router.replace({ name: "login" });
}

async function handleLogout() {
  try {
    await api.post("/auth/logout");
  } catch {
    /* ignore */
  }
  auth.logout();
  await router.replace({ name: "login" });
}
</script>

<style scoped>
.onboarding-shell {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  min-height: 100vh;
  padding: 20px 16px;
  background: #f5f6f8;
}
.onboarding-card {
  width: min(520px, 100%);
}
.onboarding-lead {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.55;
  color: #334155;
}
.onboarding-sub {
  margin: 0 0 16px;
  font-size: 13px;
  color: #64748b;
}
.onboarding-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.onboarding-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #475569;
}
.onboarding-form input {
  font-size: 16px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}
.onboarding-error {
  margin: 0;
  color: #b91c1c;
  font-size: 13px;
}
.onboarding-done-btn {
  width: 100%;
  min-height: 44px;
}
.onboarding-logout {
  margin: 16px 0 0;
}
.onboarding-logout .secondary {
  width: 100%;
}
</style>
