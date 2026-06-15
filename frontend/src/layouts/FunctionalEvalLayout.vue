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
        <RouterLink
          class="fe-menu-subitem fe-menu-guide"
          :to="{ name: 'site-user-guide' }"
          @click="closeMobileDrawer"
        >
          기능인인정제 설명
        </RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header
        v-if="!(isMobileViewport && (consentRequired || consentLoading))"
        class="layout-header layout-header-fe"
        :class="{ 'layout-header-site-mobile': isMobileViewport }"
      >
        <div class="header-left">
          <button
            v-if="isMobileViewport && isEvaluateRoute"
            type="button"
            class="fe-header-back"
            @click="goRoster"
          >
            ← 현황
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
          <div class="header-title-block">
            <div class="header-title">기능인 인정제 평가</div>
            <div class="header-sub header-sub--user">{{ auth.user?.name }} ({{ auth.user?.login_id }})</div>
          </div>
        </div>
        <div class="header-right">
          <span v-if="!isMobileViewport">{{ auth.user?.name }} ({{ auth.user?.login_id }})</span>
          <button class="stitch-btn-secondary header-logout" type="button" @click="logout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main layout-main-fe">
        <p v-if="consentLoading" class="fe-consent-loading" role="status">동의서 확인 중…</p>
        <FeConsentGate
          v-else-if="consentRequired"
          :open="consentRequired"
          :prefill="consentPrefill"
          @completed="onConsentCompleted"
        />
        <RouterView v-else />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useAuthStore } from "@/stores/auth";
import FeConsentGate from "@/components/functional-eval/FeConsentGate.vue";
import { useFeConsentCheck } from "@/composables/useFeConsentCheck";

const auth = useAuthStore();
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
  void checkConsent();
});

const evalMenuStatuses = [
  { key: "incomplete", label: "미평가" },
  { key: "in_progress", label: "진행중" },
  { key: "complete", label: "평가완료" },
];

const isRosterMenuActive = computed(
  () => route.name === "site-functional-eval" || route.name === "site-functional-eval-roster",
);

const isEvaluateRoute = computed(() => route.name === "site-functional-eval-evaluate");

function isEvalMenuActive(statusKey: string) {
  return route.name === "site-functional-eval-evaluate" && route.query.eval_status === statusKey;
}

function goRoster() {
  mobileDrawerOpen.value = false;
  void router.push({ name: "site-functional-eval" });
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

.layout-header-site-mobile .header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.header-title-block {
  min-width: 0;
}

.header-title {
  font-weight: 600;
  font-size: 15px;
  line-height: 1.3;
}

.header-sub {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.header-right {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
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
  }

  .layout-main-fe {
    padding: 20px;
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

