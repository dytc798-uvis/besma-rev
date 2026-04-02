<template>
  <div class="hq-safe-shell layout-root" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="layout-sidebar">
      <h1 class="sidebar-brand">BESMA 임시플랫폼 · HQ 안전</h1>
      <nav class="layout-menu">
        <RouterLink to="/hq-safe/dashboard">대시보드</RouterLink>
        <RouterLink to="/hq-safe/tbm-monitor">TBM 모니터</RouterLink>
        <RouterLink to="/hq-safe/risk-library">위험성평가 DB 조회</RouterLink>
        <RouterLink to="/hq-safe/site-search">현장 검색</RouterLink>
        <RouterLink to="/hq-safe/document-explorer">문서 탐색</RouterLink>
        <RouterLink to="/hq-safe/documents" @click="collapseSidebar"
          >문서 취합 현황
          <span v-if="badge.incomplete_count > 0">({{ badge.incomplete_count }})</span></RouterLink
        >
        <RouterLink to="/hq-safe/approvals/inbox">결재함(공사중)</RouterLink>
        <RouterLink to="/hq-safe/approvals/history">승인/반려 이력</RouterLink>
        <RouterLink to="/hq-safe/opinions">운영 아이디어 제안</RouterLink>
        <RouterLink to="/hq-safe/sites">현장 관리</RouterLink>
        <RouterLink to="/hq-safe/users">사용자 관리</RouterLink>
        <RouterLink to="/hq-safe/settings">안전문서 설정관리</RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header">
        <div class="header-left">
          <button class="sidebar-toggle-btn" @click="toggleSidebar">
            {{ sidebarCollapsed ? "펼치기" : "접기" }}
          </button>
          <div class="header-title">BESMA 임시플랫폼 · HQ_SAFE</div>
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
import { onMounted, ref } from "vue";
import { useRouter, RouterLink, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";

const auth = useAuthStore();
const router = useRouter();
const badge = ref({ incomplete_count: 0 });
const sidebarCollapsed = ref(false);

onMounted(() => {
  if (!auth.user) {
    auth.loadMe();
  }
  loadBadge();
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
