<template>
  <div
    class="hq-safe-shell layout-root"
    :class="{
      'sidebar-collapsed': !isMobileViewport && sidebarCollapsed,
      'hq-mobile-layout': isMobileViewport,
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
      <h1 class="sidebar-brand">{{ isFeViewer ? "BESMA · 기능인인정제 조회" : "BESMA CSMS 안전보건 플랫폼 · HQ 안전" }}</h1>
      <nav class="layout-menu layout-menu-hq" @click="onMobileNavClick">
        <template v-if="isFeViewer">
          <RouterLink class="hq-fe-menu-highlight" to="/hq-safe/functional-eval">기능인인정제 평가</RouterLink>
          <RouterLink class="hq-fe-menu-highlight" to="/hq-safe/functional-eval-monitoring">기능인인정제 모니터링</RouterLink>
        </template>
        <template v-else>
        <RouterLink class="hq-menu-dashboard" to="/hq-safe/dashboard">대시보드</RouterLink>

        <div class="hq-menu-group">
          <p class="hq-menu-section-label">주요업무</p>
          <RouterLink
            class="hq-fe-menu-highlight"
            :style="menuOrderPrimaryStyle('functional-eval')"
            to="/hq-safe/functional-eval"
          >
            기능인인정제 평가
          </RouterLink>
          <RouterLink
            class="hq-fe-menu-highlight"
            :style="menuOrderPrimaryStyle('functional-eval-monitoring')"
            to="/hq-safe/functional-eval-monitoring"
          >
            기능인인정제 모니터링
          </RouterLink>
          <RouterLink
            class="hq-fe-menu-highlight"
            to="/hq-safe/tbm-beta"
          >
            TBM(베타테스트)
          </RouterLink>
          <RouterLink
            class="hq-fe-menu-highlight"
            :style="menuOrderPrimaryStyle('functional-eval-rewards-sanctions')"
            to="/hq-safe/functional-eval-rewards-sanctions"
          >
            기능인인정제 안전보건실 승인 및 포상/제재
            <span v-if="feReviewPendingCount > 0" class="hq-menu-count-badge">{{ feReviewPendingCount }}</span>
          </RouterLink>
          <RouterLink
            :style="menuOrderPrimaryStyle('user-guide')"
            to="/hq-safe/user-guide"
          >
            기능인인정제 설명
          </RouterLink>
          <RouterLink :class="hqMenuEmphasisClass('notices')" :style="menuOrderPrimaryStyle('notices')" to="/hq-safe/notices">공지사항</RouterLink>
          <RouterLink
            :class="hqMenuEmphasisClass('safety-policy-goals')"
            :style="menuOrderPrimaryStyle('safety-policy-goals')"
            to="/hq-safe/safety-policy-goals"
          >
            안전보건 방침 및 목표
          </RouterLink>
          <RouterLink :class="hqMenuEmphasisClass('risk-library')" :style="menuOrderPrimaryStyle('risk-library')" to="/hq-safe/risk-library">
            위험성평가 DB 조회
          </RouterLink>
          <RouterLink
            :class="hqMenuEmphasisClass('document-explorer')"
            :style="menuOrderPrimaryStyle('document-explorer')"
            to="/hq-safe/document-explorer"
          >
            문서 검색
          </RouterLink>
          <RouterLink
            :class="hqMenuEmphasisClass('documents')"
            :style="menuOrderPrimaryStyle('documents')"
            to="/hq-safe/documents"
            @click="collapseSidebar"
          >
            문서 취합 현황
          </RouterLink>
          <RouterLink
            :class="hqMenuEmphasisClass('worker-voice')"
            :style="menuOrderPrimaryStyle('worker-voice')"
            to="/hq-safe/worker-voice"
          >
            근로자의견청취
          </RouterLink>
          <RouterLink
            :class="hqMenuEmphasisClass('approvals-history')"
            :style="menuOrderPrimaryStyle('approvals-history')"
            to="/hq-safe/communications"
          >
            본사-현장 소통
            <span v-if="unreadCommunicationCount > 0" class="hq-menu-count-badge">{{ unreadCommunicationCount }}</span>
          </RouterLink>
          <RouterLink :style="menuOrderPrimaryStyle('safety-education')" to="/hq-safe/safety-education">안전교육 및 안전점검</RouterLink>
          <RouterLink v-if="canAccessAccidents" :style="menuOrderPrimaryStyle('accidents')" to="/hq-safe/accidents">사고관리</RouterLink>
          <RouterLink
            v-for="m in dynamicMenus"
            :key="`hq-dyn-${m.slug}`"
            :style="menuOrderPrimaryStyle(`dynamic:${m.id}`)"
            :to="`/hq-safe/custom-menus/${m.slug}`"
          >
            {{ m.title }}
          </RouterLink>
          <RouterLink
            :style="menuOrderPrimaryStyle('new-site-deployment')"
            to="/hq-safe/new-site-deployment"
          >
            신규현장 배포 현황
            <span v-if="deployIncompleteCount > 0" class="hq-menu-count-badge">{{ deployIncompleteCount }}</span>
          </RouterLink>
        </div>

        <div class="hq-menu-group hq-menu-group-secondary">
          <p class="hq-menu-section-label">부가 메뉴</p>
          <RouterLink :style="menuOrderSecondaryStyle('site-search')" to="/hq-safe/site-search">현장 검색</RouterLink>
          <RouterLink :style="menuOrderSecondaryStyle('opinions')" to="/hq-safe/opinions">운영 아이디어 제안</RouterLink>
          <RouterLink :style="menuOrderSecondaryStyle('settings')" to="/hq-safe/settings">문서 설정</RouterLink>
          <RouterLink :style="menuOrderSecondaryStyle('sites')" to="/hq-safe/sites">현장 관리</RouterLink>
          <RouterLink :style="menuOrderSecondaryStyle('users')" to="/hq-safe/users">사용자 관리</RouterLink>
          <RouterLink
            v-if="canAccessPdfSigning"
            :style="menuOrderSecondaryStyle('pdf-signing')"
            to="/hq-safe/pdf-signing"
          >
            PDF 전자서명(임시)
          </RouterLink>
          <RouterLink
            v-if="canSystemBackup"
            class="hq-backup-menu-highlight"
            :style="menuOrderSecondaryStyle('system-backup')"
            to="/hq-safe/system-backup"
          >
            전체 백업
          </RouterLink>
        </div>
        </template>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header layout-header--branded" :class="{ 'layout-header--mobile-fe': isMobileViewport && isFunctionalEvalRoute }">
        <div class="header-left">
          <button
            type="button"
            class="sidebar-toggle-btn sidebar-toggle-btn--mobile"
            :aria-label="mobileDrawerOpen ? '메뉴 닫기' : '메뉴 열기'"
            :aria-expanded="mobileDrawerOpen"
            @click="mobileDrawerOpen = !mobileDrawerOpen"
          >
            <span aria-hidden="true">☰</span>
            <span class="menu-toggle-label">{{ mobileDrawerOpen ? "메뉴 닫기" : "메뉴 열기" }}</span>
          </button>
          <button class="sidebar-toggle-btn sidebar-toggle-btn--desktop" type="button" @click="toggleSidebar">
            {{ sidebarCollapsed ? "펼치기" : "접기" }}
          </button>
        </div>
        <div class="layout-header-brand-center">
          <AppFullLogo :compact="isMobileViewport" />
        </div>
        <div class="header-right">
          <span v-if="!isMobileViewport" class="header-user">
            {{ auth.user?.name }} ({{ auth.user?.login_id }})
            <template v-if="auth.isTestPersonaMode && auth.effectivePersona">
              / Persona: {{ auth.effectivePersona }}
            </template>
          </span>
          <RouterLink
            v-if="!isMobileViewport"
            class="secondary"
            style="margin-right: 8px; text-decoration: none; display: inline-block"
            to="/change-password"
          >
            비밀번호 변경
          </RouterLink>
          <button class="secondary header-logout-btn" type="button" @click="handleLogout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink, RouterView } from "vue-router";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";
import { buildHqMenuOrderMaps, isHqSidebarEmphasisKey } from "@/config/hqSidebarMenuGroups";
import { canSystemBackup as userCanSystemBackup } from "@/utils/systemBackupAccess";
import AppFullLogo from "@/components/branding/AppFullLogo.vue";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const { isMobileViewport } = useMobileViewport();
const mobileDrawerOpen = ref(false);
const badge = ref({ incomplete_count: 0 });
const unreadCommunicationCount = ref(0);
const sidebarCollapsed = ref(false);
const dynamicMenus = ref<Array<{ id: number; slug: string; title: string }>>([]);
const menuOrderPrimary = ref<Record<string, number>>({});
const menuOrderSecondary = ref<Record<string, number>>({});
const canAccessAccidents = computed(() =>
  ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "ACCIDENT_ADMIN"].includes(auth.user?.role ?? ""),
);
const canAccessPdfSigning = computed(() =>
  ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "ACCIDENT_ADMIN"].includes(auth.user?.role ?? ""),
);
const isFeViewer = computed(() => auth.user?.role === "FUNCTIONAL_EVAL_VIEWER");
const canSystemBackup = computed(() => userCanSystemBackup(auth.user));
const deployIncompleteCount = ref(0);
const feReviewPendingCount = ref(0);

const isFunctionalEvalRoute = computed(() => route.path.includes("/functional-eval"));
const headerTitle = computed(() => {
  if (isMobileViewport.value && isFunctionalEvalRoute.value) return "기능인인정제";
  if (isMobileViewport.value) return "HQ 안전";
  return "BESMA CSMS 안전보건 플랫폼 · HQ_SAFE";
});

function onMobileNavClick(event: MouseEvent) {
  if (!isMobileViewport.value) return;
  const target = event.target as HTMLElement | null;
  if (target?.closest("a")) {
    mobileDrawerOpen.value = false;
  }
}

watch(
  () => route.path,
  () => {
    mobileDrawerOpen.value = false;
  },
);

onMounted(() => {
  if (!auth.user) {
    auth.loadMe();
  }
  loadBadge();
  void loadUnreadCommunications();
  loadDynamicMenus();
  void loadDeploymentMenuStatus();
  void loadFunctionalEvalReviewCount();
  window.addEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
  window.addEventListener("besma-hq-communication-read", handleCommunicationRead as EventListener);
  window.addEventListener("besma-nsd-updated", loadDeploymentMenuStatus as EventListener);
  window.addEventListener("besma-fe-review-updated", loadFunctionalEvalReviewCount as EventListener);
});

onUnmounted(() => {
  window.removeEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
  window.removeEventListener("besma-hq-communication-read", handleCommunicationRead as EventListener);
  window.removeEventListener("besma-nsd-updated", loadDeploymentMenuStatus as EventListener);
  window.removeEventListener("besma-fe-review-updated", loadFunctionalEvalReviewCount as EventListener);
});

async function loadBadge() {
  try {
    const res = await api.get("/documents/badges/hq", {
      params: { date: todayKst() },
    });
    badge.value = res.data;
  } catch {
    badge.value = { incomplete_count: 0 };
  }
}

function handleCommunicationRead() {
  void loadUnreadCommunications();
}

async function loadUnreadCommunications() {
  try {
    const res = await api.get("/documents/hq-communications", { params: { limit: 120 } });
    const items = (res.data?.items ?? []) as Array<{ is_read?: boolean }>;
    unreadCommunicationCount.value = items.filter((row) => !row.is_read).length;
  } catch {
    unreadCommunicationCount.value = 0;
  }
}

async function loadDeploymentMenuStatus() {
  try {
    const res = await api.get("/new-site-deployment/menu-status");
    deployIncompleteCount.value = res.data?.incomplete_count ?? 0;
  } catch {
    deployIncompleteCount.value = 0;
  }
}

async function loadFunctionalEvalReviewCount() {
  try {
    const [approvalRes, rewardRes, sanctionRes] = await Promise.allSettled([
      api.get("/functional-eval/hq/approvals/pending"),
      api.get("/functional-eval/hq/customer-rewards/pending"),
      api.get("/functional-eval/hq/sanctions/pending"),
    ]);
    const approvalCount =
      approvalRes.status === "fulfilled" && Array.isArray(approvalRes.value.data?.items)
        ? approvalRes.value.data.items.length
        : 0;
    const rewardCount =
      rewardRes.status === "fulfilled" && Array.isArray(rewardRes.value.data?.items)
        ? rewardRes.value.data.items.length
        : 0;
    const sanctionCount =
      sanctionRes.status === "fulfilled" && Array.isArray(sanctionRes.value.data?.items)
        ? sanctionRes.value.data.items.length
        : 0;
    feReviewPendingCount.value = approvalCount + rewardCount + sanctionCount;
  } catch {
    feReviewPendingCount.value = 0;
  }
}

async function loadDynamicMenus() {
  try {
    const res = await api.get("/dynamic-menus/sidebar", { params: { ui_type: "HQ_SAFE" } });
    dynamicMenus.value = res.data?.items ?? [];
    await loadMenuOrder();
  } catch {
    dynamicMenus.value = [];
    menuOrderPrimary.value = {};
    menuOrderSecondary.value = {};
  }
}

async function loadMenuOrder() {
  const dynamicKeys = dynamicMenus.value.map((m) => `dynamic:${m.id}`);
  try {
    const res = await api.get("/dynamic-menus/menu-order/HQ_SAFE");
    const ordered = Array.isArray(res.data?.ordered_keys) ? (res.data.ordered_keys as string[]) : [];
    const maps = buildHqMenuOrderMaps(ordered, dynamicKeys);
    menuOrderPrimary.value = maps.primary;
    menuOrderSecondary.value = maps.secondary;
  } catch {
    const maps = buildHqMenuOrderMaps(null, dynamicKeys);
    menuOrderPrimary.value = maps.primary;
    menuOrderSecondary.value = maps.secondary;
  }
}

function menuOrderPrimaryStyle(key: string) {
  const order = menuOrderPrimary.value[key];
  if (!order) return undefined;
  return { order };
}

function menuOrderSecondaryStyle(key: string) {
  const order = menuOrderSecondary.value[key];
  if (!order) return undefined;
  return { order };
}

function hqMenuEmphasisClass(key: string) {
  return { "hq-menu-link-emphasis": isHqSidebarEmphasisKey(key) };
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

.layout-menu-hq {
  gap: 10px;
}

.hq-menu-dashboard {
  display: block;
  margin: 2px 10px 4px;
  padding: 10px 14px;
  color: #475569;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  border-radius: 8px;
}

.hq-menu-dashboard:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.hq-menu-dashboard.router-link-active {
  background: #2563eb;
  color: #fff;
}

.hq-menu-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hq-menu-group-secondary {
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
}

.hq-menu-section-label {
  margin: 0 10px 6px;
  padding: 0 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #94a3b8;
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

.hq-safe-shell .layout-menu a.hq-menu-link-emphasis:not(.router-link-active) {
  font-weight: 700;
  background: #eff6ff;
  color: #1e3a8a;
  border-left: 3px solid #2563eb;
  margin-left: 8px;
  padding-left: 11px;
}

.hq-menu-count-badge {
  margin-left: 8px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #dc2626;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
  display: inline-block;
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
  flex: 1;
  z-index: 2;
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
  z-index: 2;
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

.hq-backup-menu-highlight {
  border-left: 3px solid #dc2626 !important;
  font-weight: 700;
}

.sidebar-toggle-btn--menu {
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  padding: 0 10px;
}

.sidebar-toggle-btn--mobile {
  display: none;
}

.menu-toggle-label {
  line-height: 1;
}

.layout-header--mobile-fe {
  min-height: 44px;
  height: auto;
  padding: 6px 10px;
}

.header-logout-btn {
  min-height: 40px;
}

@media (max-width: 768px) {
  .hq-safe-shell .layout-main {
    padding: 10px;
  }

  .hq-safe-shell .layout-header {
    padding: 6px 10px;
    min-height: 44px;
    height: auto;
  }

  .header-title {
    font-size: 15px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hq-safe-shell .sidebar-toggle-btn--mobile {
    display: inline-flex;
  }

  .hq-safe-shell .sidebar-toggle-btn--desktop {
    display: none;
  }
}

</style>


