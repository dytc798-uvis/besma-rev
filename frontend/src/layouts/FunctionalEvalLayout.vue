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
      <h1>BESMA · 기능인제 인사고과</h1>
      <nav class="layout-menu">
        <RouterLink class="fe-menu-highlight" to="/site/functional-eval">인사고과</RouterLink>
      </nav>
    </aside>
    <aside v-else class="layout-sidebar">
      <h1>기능인제</h1>
      <nav class="layout-menu">
        <RouterLink class="fe-menu-highlight" to="/site/functional-eval" @click="mobileDrawerOpen = false">인사고과·제재</RouterLink>
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
            <div class="header-title">기능인제 인사고과</div>
            <div v-if="isMobileViewport" class="header-sub">{{ auth.user?.name }} · 현장 {{ auth.user?.login_id }}</div>
          </div>
        </div>
        <div class="header-right">
          <span v-if="!isMobileViewport">{{ auth.user?.name }} (현장 {{ auth.user?.login_id }})</span>
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
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const { isMobileViewport } = useMobileViewport();
const mobileDrawerOpen = ref(false);

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
