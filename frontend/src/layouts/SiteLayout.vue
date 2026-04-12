<template>
  <div class="layout-root" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="layout-sidebar">
      <h1>BESMA CSMS 안전보건플랫폼 · 현장</h1>
      <nav class="layout-menu">
        <RouterLink :class="menuLinkClass('dashboard', '/site/dashboard')" to="/site/dashboard">대시보드</RouterLink>
        <RouterLink :class="menuLinkClass('notices', '/site/notices')" :style="menuOrderStyle('notices')" to="/site/notices">공지사항</RouterLink>
        <RouterLink
          v-if="!isMobileViewport"
          :class="menuLinkClass('safety-policy-goals', '/site/safety-policy-goals')"
          :style="menuOrderStyle('safety-policy-goals')"
          to="/site/safety-policy-goals"
        >
          안전보건 방침 및 목표
        </RouterLink>
        <RouterLink
          v-for="m in dynamicMenus"
          :key="`site-dyn-${m.slug}`"
          :class="menuLinkClass(`dynamic:${m.id}`, `/site/custom-menus/${m.slug}`)"
          :style="menuOrderStyle(`dynamic:${m.id}`)"
          :to="`/site/custom-menus/${m.slug}`"
        >
          {{ m.title }}
        </RouterLink>
        <RouterLink :class="menuLinkClass('safety-education', '/site/safety-education')" :style="menuOrderStyle('safety-education')" to="/site/safety-education">안전 교육</RouterLink>
        <RouterLink :class="menuLinkClass('safety-inspections', '/site/safety-inspections')" :style="menuOrderStyle('safety-inspections')" to="/site/safety-inspections">안전 점검</RouterLink>
        <RouterLink :class="menuLinkClass('nonconformities', '/site/nonconformities')" :style="menuOrderStyle('nonconformities')" to="/site/nonconformities">
          <span class="menu-icon" v-if="menuIcon('nonconformities')">{{ menuIcon("nonconformities") }}</span>
          부적합사항
        </RouterLink>
        <RouterLink :class="menuLinkClass('worker-voice', '/site/worker-voice')" :style="menuOrderStyle('worker-voice')" to="/site/worker-voice">
          <span class="menu-icon" v-if="menuIcon('worker-voice')">{{ menuIcon("worker-voice") }}</span>
          근로자의견청취
        </RouterLink>
        <RouterLink :class="menuLinkClass('mobile', '/site/mobile')" :style="menuOrderStyle('mobile')" to="/site/mobile">모바일 운영</RouterLink>
        <RouterLink :class="menuLinkClass('mobile-site-search', '/site/mobile/site-search')" :style="menuOrderStyle('mobile-site-search')" to="/site/mobile/site-search">현장 검색</RouterLink>
        <RouterLink :class="menuLinkClass('document-explorer', '/site/document-explorer')" :style="menuOrderStyle('document-explorer')" to="/site/document-explorer">
          <span class="menu-icon" v-if="menuIcon('document-explorer')">{{ menuIcon("document-explorer") }}</span>
          문서 탐색
        </RouterLink>
        <RouterLink :class="menuLinkClass('risk-library', '/site/risk-library')" :style="menuOrderStyle('risk-library')" to="/site/risk-library">
          <span class="menu-icon" v-if="menuIcon('risk-library')">{{ menuIcon("risk-library") }}</span>
          위험성평가 DB 조회
        </RouterLink>
        <RouterLink :class="menuLinkClass('documents', '/site/documents')" :style="menuOrderStyle('documents')" to="/site/documents">
          <span class="menu-icon" v-if="menuIcon('documents')">{{ menuIcon("documents") }}</span>
          내 현장 문서 <span v-if="badge.incomplete_count > 0">({{ badge.incomplete_count }})</span>
        </RouterLink>
        <RouterLink :class="menuLinkClass('communications', '/site/communications')" :style="menuOrderStyle('communications')" to="/site/communications">
          소통자료 <span v-if="communicationUnreadCount > 0">({{ communicationUnreadCount }})</span>
        </RouterLink>
        <RouterLink :class="menuLinkClass('opinions', '/site/opinions')" :style="menuOrderStyle('opinions')" to="/site/opinions">운영 아이디어 제안</RouterLink>
        <RouterLink :class="menuLinkClass('info', '/site/info')" :style="menuOrderStyle('info')" to="/site/info">설정</RouterLink>
        <RouterLink :class="menuLinkClass('user-guide', '/site/user-guide')" :style="menuOrderStyle('user-guide')" to="/site/user-guide">사용설명서</RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header">
        <div class="layout-header-left">
          <button class="sidebar-toggle-btn" @click="toggleSidebar">
            {{ sidebarCollapsed ? "펼치기" : "접기" }}
          </button>
          <span>BESMA CSMS 안전보건플랫폼 · SITE</span>
        </div>
        <div class="layout-header-center">
          {{ headerSiteLabel }}
        </div>
        <div>
          <span style="margin-right: 8px">
            {{ auth.user?.name }} ({{ auth.user?.login_id }})
            <template v-if="auth.isTestPersonaMode && auth.effectivePersona">
              / Persona: {{ auth.effectivePersona }}
            </template>
          </span>
          <button class="secondary" @click="handleLogout">로그아웃</button>
        </div>
      </header>
      <div v-if="tickerTitles.length > 0" class="notice-ticker">
        <div class="notice-ticker-track">
          <span class="notice-ticker-item" v-for="(title, idx) in tickerTitles" :key="`${idx}-${title}`">
            [공지] {{ title }}
          </span>
        </div>
      </div>
      <main class="layout-main">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter, RouterLink, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const badge = ref({ incomplete_count: 0 });
const communicationUnreadCount = ref(0);
const siteName = ref<string>("");
const tickerTitles = ref<string[]>([]);
const dynamicMenus = ref<Array<{ id: number; slug: string; title: string }>>([]);
const menuOrderMap = ref<Record<string, number>>({});
const SITE_FIXED_MENU_KEYS = [
  "notices",
  "safety-policy-goals",
  "safety-education",
  "safety-inspections",
  "nonconformities",
  "worker-voice",
  "mobile",
  "mobile-site-search",
  "document-explorer",
  "risk-library",
  "documents",
  "communications",
  "opinions",
  "info",
  "user-guide",
] as const;
const sidebarCollapsed = ref(false);
const isMobileViewport = ref(false);
let unreadTimer: number | null = null;
const headerSiteLabel = computed(() => (siteName.value ? `현장: ${siteName.value}` : "현장: -"));
const PRIMARY_MENUS = ["documents", "risk-library", "worker-voice", "document-explorer", "nonconformities"] as const;

onMounted(() => {
  initializeLayout();
  syncViewport();
  window.addEventListener("resize", syncViewport);
  window.addEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
  unreadTimer = window.setInterval(() => {
    void Promise.all([loadCommunicationUnreadCount(), loadNoticeTicker()]);
  }, 30000);
});

onUnmounted(() => {
  window.removeEventListener("resize", syncViewport);
  window.removeEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
  if (unreadTimer) {
    window.clearInterval(unreadTimer);
    unreadTimer = null;
  }
});

function syncViewport() {
  isMobileViewport.value = window.innerWidth <= 768;
}

async function initializeLayout() {
  if (auth.token) {
    await auth.loadMe();
  }
  await Promise.all([loadBadge(), loadSiteName()]);
  await Promise.all([loadCommunicationUnreadCount(), loadNoticeTicker(), loadDynamicMenus()]);
}

async function loadBadge() {
  try {
    const res = await api.get("/documents/badges/site", {
      params: { date: todayKst() },
    });
    badge.value = res.data;
  } catch {
    badge.value = { incomplete_count: 0 };
  }
}

async function loadCommunicationUnreadCount() {
  if (auth.user?.role !== "SITE") {
    communicationUnreadCount.value = 0;
    return;
  }
  try {
    const res = await api.get("/communications/unread-count");
    communicationUnreadCount.value = Number(res.data?.unread_count ?? 0);
  } catch {
    communicationUnreadCount.value = 0;
  }
}

async function loadSiteName() {
  const siteId = auth.effectiveSiteId;
  if (!siteId) {
    siteName.value = "";
    return;
  }
  try {
    const res = await api.get(`/sites/${siteId}`);
    siteName.value = res.data?.site_name ?? "";
  } catch {
    siteName.value = "";
  }
}

async function loadNoticeTicker() {
  try {
    const res = await api.get("/notices/latest", { params: { limit: 2 } });
    tickerTitles.value = (res.data?.items ?? []).map((row: { title?: string }) => row.title || "").filter(Boolean);
  } catch {
    tickerTitles.value = [];
  }
}

async function loadDynamicMenus() {
  try {
    const res = await api.get("/dynamic-menus/sidebar", { params: { ui_type: "SITE" } });
    dynamicMenus.value = res.data?.items ?? [];
    await loadMenuOrder();
  } catch {
    dynamicMenus.value = [];
    menuOrderMap.value = {};
  }
}

async function loadMenuOrder() {
  const dynamicKeys = dynamicMenus.value.map((m) => `dynamic:${m.id}`);
  const fallback = [...SITE_FIXED_MENU_KEYS, ...dynamicKeys];
  try {
    const res = await api.get("/dynamic-menus/menu-order/SITE");
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
  if (uiType === "SITE") {
    void loadMenuOrder();
  }
}

function handleLogout() {
  auth.logout();
  router.push({ name: "login" });
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function isPrimaryMenu(key: string) {
  return PRIMARY_MENUS.includes(key as (typeof PRIMARY_MENUS)[number]);
}

function isMenuActive(path: string) {
  return route.path === path;
}

function menuLinkClass(key: string, path: string) {
  return {
    "menu-link": true,
    "menu-link-primary": isPrimaryMenu(key),
    "menu-link-secondary": !isPrimaryMenu(key),
    "menu-link-active": isMenuActive(path),
  };
}

function menuIcon(key: string) {
  const iconMap: Record<string, string> = {
    documents: "📄",
    "risk-library": "⚠️",
    "worker-voice": "🗣",
    "document-explorer": "🔍",
    nonconformities: "🚨",
  };
  return iconMap[key] ?? "";
}

</script>

<style scoped>
.layout-root {
  display: flex;
}

.layout-sidebar {
  transition: width 0.2s ease;
}

.layout-root.sidebar-collapsed .layout-sidebar {
  width: 0;
  overflow: hidden;
}

.layout-menu {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.menu-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 10px;
  border-left: 4px solid transparent;
  text-decoration: none;
  color: #eff6ff;
  transition: background-color 0.15s ease, color 0.15s ease, opacity 0.15s ease, border-color 0.15s ease;
}

.menu-link-primary {
  font-weight: 600;
  background: rgba(255, 255, 255, 0.08);
  border-left-color: rgba(191, 219, 254, 0.9);
}

.menu-link-secondary {
  opacity: 1;
}

.menu-link:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
}

.menu-link-active {
  background: #2563eb;
  color: #ffffff;
  border-left-color: #93c5fd;
  opacity: 1;
  font-weight: 700;
}

.menu-icon {
  width: 18px;
  text-align: center;
  flex: 0 0 18px;
}

.layout-header {
  position: relative;
}

.layout-header-left {
  min-width: 96px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.layout-header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
  max-width: 48%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notice-ticker {
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  background: #fff7ed;
  overflow: hidden;
  white-space: nowrap;
}

.notice-ticker-track {
  display: inline-flex;
  min-width: 100%;
  gap: 36px;
  padding: 6px 12px;
  animation: ticker-move 18s linear infinite;
}

.notice-ticker-item {
  color: #b91c1c;
  font-weight: 700;
  animation: ticker-blink 1s step-start infinite;
}

@keyframes ticker-move {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

@keyframes ticker-blink {
  0%, 50%, 100% { opacity: 1; }
  25%, 75% { opacity: 0.35; }
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
</style>
