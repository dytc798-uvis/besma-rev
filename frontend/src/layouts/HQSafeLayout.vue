<template>
  <div class="hq-safe-shell layout-root" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="layout-sidebar">
      <h1 class="sidebar-brand">BESMA CSMS 안전보건플랫폼 · HQ 안전</h1>
      <nav class="layout-menu">
        <RouterLink to="/hq-safe/dashboard">대시보드</RouterLink>
        <RouterLink :style="menuOrderStyle('tbm-monitor')" to="/hq-safe/tbm-monitor">TBM 모니터</RouterLink>
        <RouterLink :style="menuOrderStyle('risk-library')" to="/hq-safe/risk-library">위험성평가 DB 조회</RouterLink>
        <RouterLink :style="menuOrderStyle('site-search')" to="/hq-safe/site-search">현장 검색</RouterLink>
        <RouterLink :style="menuOrderStyle('document-explorer')" to="/hq-safe/document-explorer">문서 탐색</RouterLink>
        <RouterLink :style="menuOrderStyle('periodic-monitoring')" to="/hq-safe/periodic-monitoring">주기 기반 문서 모니터링</RouterLink>
        <RouterLink :style="menuOrderStyle('documents')" to="/hq-safe/documents" @click="collapseSidebar"
          >문서 취합 현황
          <span v-if="badge.incomplete_count > 0">({{ badge.incomplete_count }})</span></RouterLink
        >
        <RouterLink :style="menuOrderStyle('approvals-inbox')" to="/hq-safe/approvals/inbox">결재함(공사중)</RouterLink>
        <RouterLink :style="menuOrderStyle('approvals-history')" to="/hq-safe/approvals/history">승인/반려 이력</RouterLink>
        <RouterLink :style="menuOrderStyle('opinions')" to="/hq-safe/opinions">운영 아이디어 제안</RouterLink>
        <RouterLink :style="menuOrderStyle('notices')" to="/hq-safe/notices">공지사항</RouterLink>
        <RouterLink :style="menuOrderStyle('safety-policy-goals')" to="/hq-safe/safety-policy-goals">안전보건 방침 및 목표</RouterLink>
        <RouterLink
          v-for="m in dynamicMenus"
          :key="`hq-dyn-${m.slug}`"
          :style="menuOrderStyle(`dynamic:${m.id}`)"
          :to="`/hq-safe/custom-menus/${m.slug}`"
        >
          {{ m.title }}
        </RouterLink>
        <RouterLink :style="menuOrderStyle('safety-education')" to="/hq-safe/safety-education">안전 교육</RouterLink>
        <RouterLink :style="menuOrderStyle('safety-inspections')" to="/hq-safe/safety-inspections">안전 점검</RouterLink>
        <RouterLink :style="menuOrderStyle('nonconformities')" to="/hq-safe/nonconformities">부적합사항</RouterLink>
        <RouterLink :style="menuOrderStyle('worker-voice')" to="/hq-safe/worker-voice">근로자의견청취</RouterLink>
        <RouterLink :style="menuOrderStyle('sites')" to="/hq-safe/sites">현장 관리</RouterLink>
        <RouterLink :style="menuOrderStyle('users')" to="/hq-safe/users">사용자 관리</RouterLink>
        <RouterLink :style="menuOrderStyle('settings')" to="/hq-safe/settings">안전문서 설정관리</RouterLink>
        <RouterLink :style="menuOrderStyle('user-guide')" to="/hq-safe/user-guide">사용설명서</RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header">
        <div class="header-left">
          <button class="sidebar-toggle-btn" @click="toggleSidebar">
            {{ sidebarCollapsed ? "펼치기" : "접기" }}
          </button>
          <div class="header-title">BESMA CSMS 안전보건플랫폼 · HQ_SAFE</div>
        </div>
        <div class="header-right">
          <span class="header-user">
            {{ auth.user?.name }} ({{ auth.user?.login_id }})
            <template v-if="auth.isTestPersonaMode && auth.effectivePersona">
              / Persona: {{ auth.effectivePersona }}
            </template>
          </span>
          <button class="secondary" @click="handleLogout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter, RouterLink, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";

const auth = useAuthStore();
const router = useRouter();
const badge = ref({ incomplete_count: 0 });
const sidebarCollapsed = ref(false);
const dynamicMenus = ref<Array<{ id: number; slug: string; title: string }>>([]);
const menuOrderMap = ref<Record<string, number>>({});
const HQ_FIXED_MENU_KEYS = [
  "tbm-monitor",
  "risk-library",
  "site-search",
  "document-explorer",
  "periodic-monitoring",
  "documents",
  "approvals-inbox",
  "approvals-history",
  "opinions",
  "notices",
  "safety-policy-goals",
  "safety-education",
  "safety-inspections",
  "nonconformities",
  "worker-voice",
  "sites",
  "users",
  "settings",
  "user-guide",
] as const;

onMounted(() => {
  if (!auth.user) {
    auth.loadMe();
  }
  loadBadge();
  loadDynamicMenus();
  window.addEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
});

onUnmounted(() => {
  window.removeEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
});

async function loadBadge() {
  try {
    const res = await api.get("/documents/badges/hq", {
      params: { date: new Date().toISOString().slice(0, 10) },
    });
    badge.value = res.data;
  } catch {
    badge.value = { incomplete_count: 0 };
  }
}

async function loadDynamicMenus() {
  try {
    const res = await api.get("/dynamic-menus/sidebar", { params: { ui_type: "HQ_SAFE" } });
    dynamicMenus.value = res.data?.items ?? [];
    await loadMenuOrder();
  } catch {
    dynamicMenus.value = [];
    menuOrderMap.value = {};
  }
}

async function loadMenuOrder() {
  const dynamicKeys = dynamicMenus.value.map((m) => `dynamic:${m.id}`);
  const fallback = [...HQ_FIXED_MENU_KEYS, ...dynamicKeys];
  try {
    const res = await api.get("/dynamic-menus/menu-order/HQ_SAFE");
    const ordered = Array.isArray(res.data?.ordered_keys) ? (res.data.ordered_keys as string[]) : [];
    const merged = [...ordered, ...fallback.filter((k) => !ordered.includes(k))];
    menuOrderMap.value = Object.fromEntries(merged.map((k, idx) => [k, idx + 1]));
  } catch {
    menuOrderMap.value = Object.fromEntries(fallback.map((k, idx) => [k, idx + 1]));
  }
}

function menuOrderStyle(key: string) {
  const order = menuOrderMap.value[key];
  if (!order) return undefined;
  return { order };
}

function handleMenuOrderUpdated(event: Event) {
  const uiType = (event as CustomEvent<{ uiType?: string }>).detail?.uiType;
  if (uiType === "HQ_SAFE") {
    void loadMenuOrder();
  }
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function collapseSidebar() {
  sidebarCollapsed.value = true;
}

function handleLogout() {
  auth.logout();
  router.push({ name: "login" });
}
</script>

<style scoped>
.hq-safe-shell.layout-root {
  display: flex;
  height: 100vh;
}

.hq-safe-shell .layout-sidebar {
  width: 240px;
  background: #f8fafc;
  color: #0f172a;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e2e8f0;
  transition: width 0.2s ease;
}

.hq-safe-shell.sidebar-collapsed .layout-sidebar {
  width: 0;
  overflow: hidden;
  border-right: 0;
}

.sidebar-brand {
  font-size: 15px;
  font-weight: 700;
  padding: 18px 16px;
  margin: 0;
  border-bottom: 1px solid #e2e8f0;
  color: #0f172a;
}

.hq-safe-shell .layout-menu {
  flex: 1;
  padding: 10px 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.hq-safe-shell .layout-menu a {
  display: block;
  margin: 2px 10px;
  padding: 10px 14px;
  color: #475569;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.hq-safe-shell .layout-menu a:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.hq-safe-shell .layout-menu a.router-link-active {
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.25);
}

.hq-safe-shell .layout-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.hq-safe-shell .layout-header {
  height: 52px;
  background-color: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  font-size: 13px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
}

.header-title {
  font-weight: 600;
  color: #334155;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-toggle-btn {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-user {
  color: #475569;
}

.hq-safe-shell .layout-main {
  flex: 1;
  padding: 24px;
  overflow: auto;
  background: #f1f5f9;
}

</style>
