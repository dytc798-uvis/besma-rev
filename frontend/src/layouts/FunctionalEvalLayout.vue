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
    <aside v-if="!isMobileViewport" class="layout-sidebar">
      <h1>기능인정제 평가</h1>
      <nav class="layout-menu">
        <RouterLink
          class="fe-menu-highlight"
          :class="{ active: isRosterMenuActive }"
          :to="{ name: 'site-functional-eval' }"
        >
          등급현황
        </RouterLink>
        <div class="fe-sidebar-group">
          <div class="fe-sidebar-group-title">평가</div>
          <RouterLink
            v-for="status in evalMenuStatuses"
            :key="`eval-${status}`"
            class="fe-menu-subitem"
            :class="{ active: isEvalMenuActive(status) }"
            :to="{ name: 'site-functional-eval-evaluate', query: { eval_status: status } }"
          >
            {{ status }}
          </RouterLink>
        </div>
      </nav>
    </aside>
    <aside v-else class="layout-sidebar">
      <h1>기능인정제 평가</h1>
      <nav class="layout-menu">
        <RouterLink
          class="fe-menu-highlight"
          :class="{ active: isRosterMenuActive }"
          :to="{ name: 'site-functional-eval' }"
          @click="mobileDrawerOpen = false"
        >
          등급현황
        </RouterLink>
        <div class="fe-sidebar-group">
          <div class="fe-sidebar-group-title">평가</div>
          <RouterLink
            v-for="status in evalMenuStatuses"
            :key="`eval-mobile-${status}`"
            class="fe-menu-subitem"
            :class="{ active: isEvalMenuActive(status) }"
            :to="{ name: 'site-functional-eval-evaluate', query: { eval_status: status } }"
            @click="mobileDrawerOpen = false"
          >
            {{ status }}
          </RouterLink>
        </div>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header layout-header-fe" :class="{ 'layout-header-site-mobile': isMobileViewport }">
        <div class="header-left">
          <button
            v-if="isMobileViewport"
            type="button"
            class="sidebar-toggle-btn"
            aria-label="메뉴"
            :aria-expanded="mobileDrawerOpen"
            @click="mobileDrawerOpen = !mobileDrawerOpen"
          >
            <span class="hamburger-glyph" aria-hidden="true">☰</span>
          </button>
          <div class="header-title-block">
            <div class="header-title">기능인정제 평가</div>
            <div v-if="isMobileViewport" class="header-sub">{{ auth.user?.name }} (아이디 {{ auth.user?.login_id }})</div>
          </div>
        </div>
        <div class="header-right">
          <span v-if="!isMobileViewport">{{ auth.user?.name }} (아이디 {{ auth.user?.login_id }})</span>
          <button class="stitch-btn-secondary header-logout" type="button" @click="logout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main layout-main-fe">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const { isMobileViewport } = useMobileViewport();
const mobileDrawerOpen = ref(false);

const evalMenuStatuses = ["미평가", "진행중", "평가완료"];

const isRosterMenuActive = computed(
  () => route.name === "site-functional-eval" || route.name === "site-functional-eval-roster",
);

function isEvalMenuActive(status: string) {
  return route.name === "site-functional-eval-evaluate" && route.query.eval_status === status;
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
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 18px;
  padding: 0;
}

.hamburger-glyph {
  line-height: 1;
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
}
</style>
