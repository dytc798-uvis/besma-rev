<template>
  <div class="onboarding-shell">
    <div class="card onboarding-card">
      <p v-if="consentLoading" class="onboarding-lead">{{ copy.loading }}</p>

      <template v-else-if="consentRequired">
        <FeConsentGate
          :open="true"
          :prefill="consentPrefill"
          :require-password-change="auth.mustChangePassword"
          @completed="handleConsentCompleted"
        />
      </template>

      <template v-else>
        <div class="card-title">{{ copy.completeTitle }}</div>
        <div class="onboarding-ascii-title">Ready</div>
        <p v-if="evaluationOpen" class="onboarding-lead">{{ copy.openLead }}</p>
        <p v-else class="onboarding-lead">{{ copy.closedLead }}</p>
        <p class="onboarding-ascii">
          If Korean text is broken, close this browser tab completely and open www.besma.co.kr again.
        </p>
        <p v-if="evaluationOpen" class="onboarding-sub">{{ copy.openSub }}</p>
        <p v-else class="onboarding-sub">
          {{ copy.evalDatePrefix }} <strong>{{ evaluationOpensAtLabel || copy.evalDateFallback }}</strong>{{ copy.evalDateSuffix }}
          {{ copy.closedSub }}
        </p>
        <button class="primary onboarding-done-btn" type="button" @click="goHome">
          {{ evaluationOpen ? copy.startButton : copy.confirmButton }}
        </button>
      </template>

      <p class="onboarding-logout">
        <button type="button" class="secondary" @click="handleLogout">{{ copy.logoutButton }}</button>
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
import { safeKo } from "@/utils/textSafety";

const copy = {
  loading: safeKo("\ub3d9\uc758\uc11c\u00b7\ube44\ubc00\ubc88\ud638 \uc0c1\ud0dc \ud655\uc778 \uc911...", "\ub3d9\uc758\uc11c\u00b7\ube44\ubc00\ubc88\ud638 \uc0c1\ud0dc \ud655\uc778 \uc911..."),
  completeTitle: safeKo("\uc644\ub8cc", "\uc644\ub8cc"),
  openLead: safeKo("\ub3d9\uc758\uac00 \uc644\ub8cc\ub418\uc5b4 \uae30\ub2a5\uc778\uc778\uc815\uc81c \uc811\uc18d\uc774 \uac00\ub2a5\ud569\ub2c8\ub2e4.", "\ub3d9\uc758\uac00 \uc644\ub8cc\ub418\uc5b4 \uae30\ub2a5\uc778\uc778\uc815\uc81c \uc811\uc18d\uc774 \uac00\ub2a5\ud569\ub2c8\ub2e4."),
  closedLead: safeKo("\ub3d9\uc758\uac00 \uc544\uc9c1 \ubc18\uc601\ub418\uc9c0 \uc54a\uc544 \ub098\uc911\uc5d0 \uc811\uc18d \uac00\ub2a5\ud569\ub2c8\ub2e4.", "\ub3d9\uc758\uac00 \uc544\uc9c1 \ubc18\uc601\ub418\uc9c0 \uc54a\uc544 \ub098\uc911\uc5d0 \uc811\uc18d \uac00\ub2a5\ud569\ub2c8\ub2e4."),
  openSub: safeKo("\uc785\ub825 \uc644\ub8cc \ud6c4 \uae30\ub2a5\uc778\uc778\uc815\uc81c \ud654\uba74\uc73c\ub85c \uc774\ub3d9\ud569\ub2c8\ub2e4.", "\uc785\ub825 \uc644\ub8cc \ud6c4 \uae30\ub2a5\uc778\uc778\uc815\uc81c \ud654\uba74\uc73c\ub85c \uc774\ub3d9\ud569\ub2c8\ub2e4."),
  evalDatePrefix: safeKo("\ud3c9\uac00\uc77c\uc740", "\ud3c9\uac00\uc77c\uc740"),
  evalDateFallback: safeKo("6/16 \uc774\ud6c4", "6/16 \uc774\ud6c4"),
  evalDateSuffix: safeKo(" \uc785\ub2c8\ub2e4.", " \uc785\ub2c8\ub2e4."),
  closedSub: safeKo("\uae30\ub2a5\uc778\uc778\uc815\uc81c \uc811\uc18d\uc740 \ud574\ub2f9 \uc2dc\uc810 \uc774\ud6c4\uc5d0 \uac00\ub2a5\ud569\ub2c8\ub2e4.", "\uae30\ub2a5\uc778\uc778\uc815\uc81c \uc811\uc18d\uc740 \ud574\ub2f9 \uc2dc\uc810 \uc774\ud6c4\uc5d0 \uac00\ub2a5\ud569\ub2c8\ub2e4."),
  startButton: safeKo("\uc2dc\uc791\ud558\uae30", "\uc2dc\uc791\ud558\uae30"),
  confirmButton: safeKo("\ud655\uc778", "\ud655\uc778"),
  logoutButton: safeKo("\ub85c\uadf8\uc544\uc6c3", "\ub85c\uadf8\uc544\uc6c3"),
};

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
    await router.replace({ name: "site-heat-stress" });
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
.onboarding-ascii-title {
  margin-top: 2px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}
.onboarding-lead {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.55;
  color: #334155;
}
.onboarding-ascii {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
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
