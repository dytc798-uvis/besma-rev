<template>
  <div class="onboarding-shell">
    <div class="card onboarding-card">
      <p v-if="consentLoading" class="onboarding-lead">동의서·비밀번호 상태 확인 중…</p>

      <template v-else-if="consentRequired">
        <FeConsentGate
          :open="true"
          :prefill="consentPrefill"
          :require-password-change="auth.mustChangePassword"
          @completed="handleConsentCompleted"
        />
      </template>

      <template v-else>
        <div class="card-title">완료</div>
        <p v-if="evaluationOpen" class="onboarding-lead">동의가 완료되어 기능인정제 접속이 가능합니다.</p>
        <p v-else class="onboarding-lead">동의가 아직 반영되지 않아 나중에 접속 가능합니다.</p>
        <p v-if="evaluationOpen" class="onboarding-sub">입력 완료 후 기능인정제 화면으로 이동합니다.</p>
        <p v-else class="onboarding-sub">
          평가일은 <strong>{{ evaluationOpensAtLabel || "6/16 이후" }}</strong> 입니다.
          기능인정제 접속은 해당 시점 이후에 가능합니다.
        </p>
        <button class="primary onboarding-done-btn" type="button" @click="goHome">{{ evaluationOpen ? "시작하기" : "확인" }}</button>
      </template>

      <p class="onboarding-logout">
        <button type="button" class="secondary" @click="handleLogout">로그아웃</button>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import FeConsentGate from "@/components/functional-eval/FeConsentGate.vue";
import { useFeConsentCheck } from "@/composables/useFeConsentCheck";
import { siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";
import { hqSafeHomeRouteName } from "@/utils/hqHomeRoute";

const router = useRouter();
const auth = useAuthStore();
const {
  consentPrefill,
  consentLoading,
  consentRequired,
  checkConsent,
  onConsentCompleted: markConsentDone,
  evaluationOpen,
  evaluationOpensAtLabel,
} = useFeConsentCheck();

onMounted(async () => {
  if (!auth.user) {
    await auth.loadMe({ skipAuthRedirect: true });
  }
  await checkConsent();
  if (!auth.mustChangePassword && !consentRequired.value) {
    void goHome();
  }
});

async function handleConsentCompleted() {
  markConsentDone();
  await auth.loadMe({ skipAuthRedirect: true });
  if (!consentRequired.value) {
    await goHome();
  }
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
