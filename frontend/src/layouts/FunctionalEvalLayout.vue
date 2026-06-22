<template>
  <div
    class="layout-root functional-eval-shell site-shell"
    :class="{
      'site-mobile-layout': isMobileViewport,
      'mobile-drawer-open': isMobileViewport && mobileDrawerOpen,
    }"
  >
    <div
      v-if="isMobileViewport && mobileDrawerOpen"
      class="mobile-drawer-backdrop"
      aria-hidden="true"
      @click="mobileDrawerOpen = false"
    />
    <aside class="layout-sidebar">
      <h1>기능인 인정제 평가</h1>
      <nav class="layout-menu">
        <p v-if="!navHydrated" class="fe-menu-loading" role="status">메뉴 불러오는 중…</p>
        <template v-else-if="isTeamLeaderNav">
          <button
            type="button"
            class="fe-tl-step fe-tl-step--consent fe-tl-step--done"
            disabled
          >
            ① 동의서 및 비밀번호
          </button>
          <button
            type="button"
            class="fe-tl-step"
            :class="{
              'fe-tl-step--done': teamPhase === 'report' || teamPhase === 'results',
              'fe-tl-step--active': teamPhase === 'evaluate' || isEvaluateRoute,
            }"
            :disabled="teamPhase === 'results'"
            @click="goTeamStep('evaluate')"
          >
            ② 팀원 평가
          </button>
          <button
            type="button"
            class="fe-tl-step"
            :class="{
              'fe-tl-step--active': teamPhase === 'report' && !isEvaluateRoute,
              'fe-tl-step--done': teamPhase === 'results',
            }"
            :disabled="teamPhase === 'evaluate'"
            @click="goTeamStep('report')"
          >
            ③ 평가완료보고서
          </button>
          <button
            type="button"
            class="fe-tl-step"
            :class="{ 'fe-tl-step--active': teamPhase === 'results' }"
            :disabled="teamPhase !== 'results'"
            @click="goTeamStep('results')"
          >
            ④ 팀 평가 결과
          </button>
        </template>
        <template v-else>
          <RouterLink
            class="fe-menu-highlight"
            :class="{ active: isRosterMenuActive }"
            :to="{ name: 'site-functional-eval' }"
            @click="closeMobileDrawer"
          >
            등급현황
          </RouterLink>
          <div class="fe-sidebar-group">
            <div class="fe-sidebar-group-title">분류</div>
            <RouterLink
              v-for="status in evalMenuStatuses"
              :key="`eval-${status.key}`"
              class="fe-menu-subitem"
              :class="{ active: isEvalMenuActive(status.key) }"
              :to="{ name: 'site-functional-eval-evaluate', query: { eval_status: status.key } }"
              @click="closeMobileDrawer"
            >
              {{ status.label }}
            </RouterLink>
          </div>
        </template>
        <RouterLink
          class="fe-menu-subitem fe-menu-guide"
          :class="{ active: isGuideRoute }"
          :to="{ name: 'site-functional-eval-user-guide' }"
          @click="closeMobileDrawer"
        >
          기능인인정제 설명
        </RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header
        v-if="!(isMobileViewport && (consentRequired || consentLoading))"
        class="layout-header layout-header-fe layout-header--branded"
        :class="{ 'layout-header-site-mobile': isMobileViewport }"
      >
        <div class="header-left">
          <button
            v-if="isMobileViewport && (isEvaluateRoute || isGuideRoute)"
            type="button"
            class="fe-header-back"
            @click="goRoster()"
          >
            ← {{ isGuideRoute ? "평가" : "현황" }}
          </button>
          <button
            type="button"
            class="sidebar-toggle-btn sidebar-toggle-btn--mobile"
            :aria-label="mobileDrawerOpen ? '메뉴 닫기' : '메뉴 펼치기'"
            :aria-expanded="mobileDrawerOpen"
            @click="mobileDrawerOpen = !mobileDrawerOpen"
          >
            <span class="hamburger-glyph" aria-hidden="true">☰</span>
            <span class="menu-toggle-label">{{ mobileDrawerOpen ? "메뉴 닫기" : "메뉴 펼치기" }}</span>
          </button>
          <div v-if="isMobileViewport" class="header-title-block header-title-block--mobile">
            <div class="header-sub header-sub--user">{{ auth.user?.name }} ({{ auth.user?.login_id }})</div>
          </div>
        </div>
        <div class="layout-header-brand-center">
          <AppFullLogo :compact="isMobileViewport" />
        </div>
        <div class="header-right">
          <span v-if="!isMobileViewport">{{ auth.user?.name }} ({{ auth.user?.login_id }})</span>
          <button class="stitch-btn-secondary header-logout" type="button" @click="logout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main layout-main-fe">
        <p v-if="consentLoading" class="fe-consent-loading" role="status">동의서·비밀번호 상태 확인 중…</p>
        <FeConsentGate
          v-else-if="consentRequired"
          :open="consentRequired"
          :prefill="consentPrefill"
          :require-password-change="auth.mustChangePassword"
          @completed="onConsentCompleted"
        />
        <RouterView v-else />
      </main>
      <footer v-if="showSiteFooter" class="layout-footer-fe" aria-label="사이트 정보">
        <p class="layout-footer-fe__copy">© BooHyun Electric Co., Ltd</p>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useAuthStore } from "@/stores/auth";
import FeConsentGate from "@/components/functional-eval/FeConsentGate.vue";
import AppFullLogo from "@/components/branding/AppFullLogo.vue";
import { useFeConsentCheck } from "@/composables/useFeConsentCheck";
import { useFeSiteSessionStore } from "@/stores/feSiteSession";
import { clearFeSessionCache } from "@/utils/feSessionCache";

const auth = useAuthStore();
const feSiteSession = useFeSiteSessionStore();
const router = useRouter();
const route = useRoute();
const { isMobileViewport } = useMobileViewport();
const mobileDrawerOpen = ref(false);
const {
  consentLoading,
  consentRequired,
  consentPrefill,
  checkConsent,
  onConsentCompleted,
} = useFeConsentCheck();

onMounted(() => {
  const loginId = (auth.user?.login_id || "").trim();
  if (loginId) feSiteSession.hydrateNavFromCache(loginId);
  void checkConsent();
});

watch(
  () => `${route.query.guidePreview ?? ""}|${route.query.guideScene ?? ""}`,
  () => {
    void checkConsent();
  },
);

const evalMenuStatuses = [
  { key: "incomplete", label: "미평가" },
  { key: "in_progress", label: "진행중" },
  { key: "complete", label: "평가완료" },
];

const isRosterMenuActive = computed(
  () => route.name === "site-functional-eval" || route.name === "site-functional-eval-roster",
);

const navHydrated = computed(() => feSiteSession.navHydrated);
const isTeamLeaderNav = computed(() => feSiteSession.isTeamLeader);
const teamPhase = computed(() => feSiteSession.teamLeaderPhase);
const consentDone = computed(() => !consentLoading.value && !consentRequired.value);
const showSiteFooter = computed(() => !consentLoading.value && !consentRequired.value);

const isEvaluateRoute = computed(() => route.name === "site-functional-eval-evaluate");
const isGuideRoute = computed(() => route.name === "site-functional-eval-user-guide");

function isEvalMenuActive(statusKey: string) {
  return route.name === "site-functional-eval-evaluate" && route.query.eval_status === statusKey;
}

function goRoster() {
  mobileDrawerOpen.value = false;
  void router.push({ name: "site-functional-eval" });
}

function goTeamStep(step: "evaluate" | "report" | "results") {
  closeMobileDrawer();
  if (step === "evaluate") {
    void router.push({ name: "site-functional-eval-evaluate" });
    return;
  }
  void router.push({ name: "site-functional-eval", query: { team_step: step } });
}

function closeMobileDrawer() {
  if (isMobileViewport.value) {
    mobileDrawerOpen.value = false;
  }
}

watch(
  () => route.path,
  () => {
    mobileDrawerOpen.value = false;
  },
);

function logout() {
  clearFeSessionCache(auth.user?.login_id);
  feSiteSession.reset();
  auth.logout();
  router.push({ name: "login" });
}
</script>

<style scoped>
.functional-eval-shell {
  min-height: 100vh;
}

.layout-header-fe {
  gap: 8px;
  flex-wrap: wrap;
  min-height: 48px;
  height: auto;
  padding: 8px 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  z-index: 2;
}

.header-title-block--mobile {
  min-width: 0;
}

.header-right {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
  z-index: 2;
}

.sidebar-toggle-btn {
  flex-shrink: 0;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  padding: 0 10px;
}

.sidebar-toggle-btn--mobile {
  display: none;
}

.menu-toggle-label {
  line-height: 1;
}

.header-sub--user {
  display: none;
}

.hamburger-glyph {
  line-height: 1;
}

.fe-header-back {
  flex-shrink: 0;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.layout-main-fe {
  padding: 12px;
  max-width: none;
}

.functional-eval-shell .layout-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.layout-footer-fe {
  flex-shrink: 0;
  padding: 10px 16px calc(12px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid #fed7aa;
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
  text-align: center;
}

.layout-footer-fe__copy {
  margin: 0;
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  letter-spacing: 0.02em;
}

.fe-sidebar-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 10px;
}

.fe-sidebar-group-title {
  margin: 0 10px;
  padding: 2px 4px;
  font-size: 12px;
  color: #64748b;
  font-weight: 700;
}

.fe-menu-subitem {
  display: block;
  margin: 0 10px 0 22px;
  padding: 9px 12px;
  color: #475569;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
}

.fe-menu-subitem.active,
.fe-menu-subitem.router-link-active {
  background: linear-gradient(90deg, #ea580c 0%, #c2410c 100%);
  color: #fff;
  font-weight: 600;
}

.fe-step-link {
  display: block;
  width: calc(100% - 20px);
  margin: 0 10px;
  text-align: left;
  cursor: pointer;
  border: none;
  font-family: inherit;
}

/* 팀장 좌측 단계 메뉴 — 상단 stepbar(①~④)와 동일 규칙 */
.fe-tl-step {
  display: block;
  width: calc(100% - 20px);
  margin: 5px 10px;
  padding: 11px 14px;
  text-align: left;
  cursor: pointer;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  color: #64748b;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.35;
  font-family: inherit;
  box-sizing: border-box;
}

.fe-tl-step--done {
  border-color: #86efac;
  background: #f0fdf4;
  color: #166534;
}

.fe-tl-step--active {
  border-color: #ea580c;
  background: #fff7ed;
  color: #c2410c;
  box-shadow: 0 0 0 1px rgba(234, 88, 12, 0.15);
}

.fe-tl-step:disabled {
  cursor: not-allowed;
}

.fe-tl-step:disabled:not(.fe-tl-step--done):not(.fe-tl-step--active) {
  opacity: 0.72;
}

.fe-tl-step--consent.fe-tl-step--done,
.fe-tl-step--done:disabled,
.fe-tl-step--active:disabled {
  opacity: 1;
}

.fe-menu-loading {
  margin: 8px 10px;
  padding: 10px 12px;
  font-size: 13px;
  color: #64748b;
}

.fe-step-link.active {
  background: linear-gradient(90deg, #ea580c 0%, #c2410c 100%);
  color: #fff;
  font-weight: 600;
  border-radius: 8px;
}

.fe-menu-highlight.active,
.fe-menu-highlight.router-link-active {
  background: linear-gradient(90deg, #ea580c 0%, #c2410c 100%);
  color: #fff;
  font-weight: 600;
}

@media (min-width: 769px) {
  .functional-eval-shell {
    display: grid;
    grid-template-columns: 240px 1fr;
    height: 100vh;
    min-height: 100vh;
    overflow: hidden;
  }

  .functional-eval-shell .layout-content {
    min-height: 0;
    overflow: hidden;
  }

  .layout-main-fe {
    padding: 20px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
}

@media (max-width: 768px) {
  .header-logout {
    min-height: 40px;
    padding: 8px 12px;
    font-size: 13px;
  }

  .functional-eval-shell.site-mobile-layout .layout-main-fe {
    padding: 8px 10px;
  }

  .functional-eval-shell.site-mobile-layout .layout-footer-fe {
    padding: 8px 12px calc(14px + env(safe-area-inset-bottom, 0px));
  }

  .functional-eval-shell.site-mobile-layout .layout-footer-fe__copy {
    font-size: 10px;
  }

  .functional-eval-shell.site-mobile-layout .layout-header-fe {
    padding: 6px 10px;
    min-height: 44px;
  }

  .functional-eval-shell.site-mobile-layout .header-title {
    font-size: 15px;
  }

  .functional-eval-shell.site-mobile-layout .header-sub--user {
    display: block;
    font-size: 12px;
    color: #64748b;
    margin-top: 2px;
  }

  .functional-eval-shell .sidebar-toggle-btn--mobile {
    display: inline-flex;
  }

  .fe-consent-loading {
    margin: 24px 12px;
    text-align: center;
    color: #64748b;
    font-size: 14px;
  }
}
</style>
