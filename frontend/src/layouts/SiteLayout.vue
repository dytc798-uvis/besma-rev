<template>
  <div
    class="layout-root site-shell"
    :class="{
      'sidebar-collapsed': !isMobileViewport && sidebarCollapsed,
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
      <h1>BESMA CSMS 안전보건플랫폼 · 현장</h1>
      <nav v-if="!isMobileViewport" class="layout-menu">
        <RouterLink :class="menuLinkClass('dashboard', '/site/dashboard')" to="/site/dashboard">대시보드</RouterLink>
        <RouterLink :class="menuLinkClass('notices', '/site/notices')" :style="menuOrderStyle('notices')" to="/site/notices">공지사항</RouterLink>
        <RouterLink
          :class="menuLinkClass('safety-policy-goals', '/site/safety-policy-goals')"
          :style="menuOrderStyle('safety-policy-goals')"
          to="/site/safety-policy-goals"
        >
          안전보건 방침 및 목표
        </RouterLink>
        <p v-if="!isMobileViewport" class="site-menu-section-label">주요업무</p>
        <RouterLink :class="menuLinkClass('risk-library', '/site/risk-library')" :style="menuOrderStyle('risk-library')" to="/site/risk-library">
          <span class="menu-icon" v-if="menuIcon('risk-library')">{{ menuIcon("risk-library") }}</span>
          위험성평가 DB 조회
        </RouterLink>
        <RouterLink :class="menuLinkClass('worker-voice', '/site/worker-voice')" :style="menuOrderStyle('worker-voice')" to="/site/worker-voice">
          <span class="menu-icon" v-if="menuIcon('worker-voice')">{{ menuIcon("worker-voice") }}</span>
          근로자의견청취
        </RouterLink>
        <RouterLink :class="menuLinkClass('nonconformities', '/site/nonconformities')" :style="menuOrderStyle('nonconformities')" to="/site/nonconformities">
          <span class="menu-icon" v-if="menuIcon('nonconformities')">{{ menuIcon("nonconformities") }}</span>
          부적합사항
        </RouterLink>
        <RouterLink :class="menuLinkClass('document-explorer', '/site/document-explorer')" :style="menuOrderStyle('document-explorer')" to="/site/document-explorer">
          <span class="menu-icon" v-if="menuIcon('document-explorer')">{{ menuIcon("document-explorer") }}</span>
          문서 탐색
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
        <p class="site-menu-section-label">기타 메뉴</p>
        <RouterLink :class="menuLinkClass('safety-education', '/site/safety-education')" :style="menuOrderStyle('safety-education')" to="/site/safety-education">안전 교육</RouterLink>
        <RouterLink :class="menuLinkClass('safety-inspections', '/site/safety-inspections')" :style="menuOrderStyle('safety-inspections')" to="/site/safety-inspections">안전 점검</RouterLink>
        <RouterLink :class="menuLinkClass('mobile', '/site/mobile')" :style="menuOrderStyle('mobile')" to="/site/mobile">
          일일안전회의(일일위험성평가)
        </RouterLink>
        <RouterLink :class="menuLinkClass('mobile-site-search', '/site/mobile/site-search')" :style="menuOrderStyle('mobile-site-search')" to="/site/mobile/site-search">현장 검색</RouterLink>
        <RouterLink :class="menuLinkClass('documents', '/site/documents')" :style="menuOrderStyle('documents')" to="/site/documents">
          <span class="menu-icon" v-if="menuIcon('documents')">{{ menuIcon("documents") }}</span>
          <span class="menu-link-label">내 현장 문서</span>
          <span v-if="badge.incomplete_count > 0" class="menu-count-badge" aria-label="미완료 문서 수">{{ badge.incomplete_count }}</span>
        </RouterLink>
        <RouterLink :class="menuLinkClass('communications', '/site/communications')" :style="menuOrderStyle('communications')" to="/site/communications">
          소통자료 <span v-if="communicationUnreadCount > 0">({{ communicationUnreadCount }})</span>
        </RouterLink>
        <RouterLink :class="menuLinkClass('opinions', '/site/opinions')" :style="menuOrderStyle('opinions')" to="/site/opinions">
          운영 아이디어 제안
        </RouterLink>
        <RouterLink :class="menuLinkClass('info', '/site/info')" :style="menuOrderStyle('info')" to="/site/info">설정</RouterLink>
        <RouterLink :class="menuLinkClass('user-guide', '/site/user-guide')" :style="menuOrderStyle('user-guide')" to="/site/user-guide">사용설명서</RouterLink>
      </nav>
      <nav v-else class="layout-menu layout-menu-mobile-site">
        <RouterLink :class="menuLinkClass('mobile', '/site/mobile')" to="/site/mobile" @click="closeMobileDrawer">
          일일안전회의(일일위험성평가)
        </RouterLink>
        <RouterLink :class="menuLinkClass('documents', '/site/documents')" to="/site/documents" @click="closeMobileDrawer">
          <span class="menu-link-label">내 현장 문서</span>
          <span v-if="badge.incomplete_count > 0" class="menu-count-badge" aria-label="미완료 문서 수">{{ badge.incomplete_count }}</span>
        </RouterLink>
        <RouterLink
          :class="menuLinkClass('mobile-communications', '/site/mobile/communications')"
          to="/site/mobile/communications"
          @click="closeMobileDrawer"
        >
          소통자료 <span v-if="communicationUnreadCount > 0">({{ communicationUnreadCount }})</span>
        </RouterLink>
        <RouterLink :class="menuLinkClass('opinions', '/site/opinions')" to="/site/opinions" @click="closeMobileDrawer">
          운영 아이디어 제안
        </RouterLink>
        <RouterLink :class="menuLinkClass('notices', '/site/notices')" to="/site/notices" @click="closeMobileDrawer">공지사항</RouterLink>
        <RouterLink
          :class="menuLinkClass('safety-policy-goals', '/site/safety-policy-goals')"
          to="/site/safety-policy-goals"
          @click="closeMobileDrawer"
        >
          안전보건 방침·목표
        </RouterLink>
        <RouterLink :class="menuLinkClass('worker-voice', '/site/worker-voice')" to="/site/worker-voice" @click="closeMobileDrawer">
          근로자의견청취
        </RouterLink>
        <RouterLink
          :class="menuLinkClass('nonconformities', '/site/nonconformities')"
          to="/site/nonconformities"
          @click="closeMobileDrawer"
        >
          부적합사항
        </RouterLink>
        <RouterLink :class="menuLinkClass('risk-library', '/site/risk-library')" to="/site/risk-library" @click="closeMobileDrawer">
          위험성평가 DB
        </RouterLink>
        <RouterLink
          :class="menuLinkClass('mobile-site-search', '/site/mobile/site-search')"
          to="/site/mobile/site-search"
          @click="closeMobileDrawer"
        >
          현장 검색
        </RouterLink>
        <RouterLink class="menu-link menu-link-secondary" to="/change-password" @click="closeMobileDrawer">비밀번호 변경</RouterLink>
        <RouterLink :class="menuLinkClass('info', '/site/info')" to="/site/info" @click="closeMobileDrawer">설정</RouterLink>
        <RouterLink :class="menuLinkClass('user-guide', '/site/user-guide')" to="/site/user-guide" @click="closeMobileDrawer">
          사용설명서
        </RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header" :class="{ 'layout-header-site-mobile': isMobileViewport }">
        <div class="layout-header-left">
          <button type="button" class="sidebar-toggle-btn" :aria-expanded="isMobileViewport ? mobileDrawerOpen : !sidebarCollapsed" @click="toggleSidebar">
            <span v-if="isMobileViewport" class="hamburger-glyph" aria-hidden="true">☰</span>
            <template v-else>{{ sidebarCollapsed ? "펼치기" : "접기" }}</template>
          </button>
          <span class="layout-header-product">BESMA · SITE</span>
        </div>
        <div class="layout-header-center">
          {{ headerSiteLabel }}
        </div>
        <div class="layout-header-actions">
          <span v-if="!isMobileViewport" class="header-user-line">
            {{ auth.user?.name }} ({{ auth.user?.login_id }})
            <template v-if="auth.isTestPersonaMode && auth.effectivePersona"> / Persona: {{ auth.effectivePersona }}</template>
          </span>
          <RouterLink v-if="!isMobileViewport" class="secondary header-link" to="/change-password">비밀번호 변경</RouterLink>
          <button type="button" class="secondary" @click="handleLogout">로그아웃</button>
        </div>
      </header>
      <div v-if="tickerItems.length > 0 || docCommentTickerCount > 0" class="notice-ticker">
        <div
          ref="tickerTrackRef"
          class="notice-ticker-track"
          :style="{ '--ticker-duration': `${tickerDurationSec}s` }"
        >
          <template v-for="cycle in 2" :key="cycle">
            <RouterLink
              v-if="docCommentTickerCount > 0"
              :key="`${cycle}-doc-comment`"
              class="notice-ticker-item notice-ticker-item-link"
              :to="{ name: 'site-documents', query: { focus_comments: '1' } }"
            >
              [문서] 미확인 문서 코멘트 {{ docCommentTickerCount }}건
            </RouterLink>
            <span v-for="item in tickerItems" :key="`${cycle}-${item.id}`" class="notice-ticker-item">
              [공지] {{ item.title }}
            </span>
          </template>
        </div>
      </div>
      <main class="layout-main">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";
import { getTickerReadNoticeIds } from "@/utils/noticeTickerRead";
import { getDocCommentTickerAfterIso } from "@/utils/documentCommentTickerRead";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const badge = ref({ incomplete_count: 0 });
const communicationUnreadCount = ref(0);
const siteName = ref<string>("");
const tickerItems = ref<Array<{ id: number; title: string }>>([]);
const docCommentTickerCount = ref(0);
const tickerTrackRef = ref<HTMLElement | null>(null);
/** 한 세트(공지 목록 한 바퀴)를 지나가는 데 걸리는 시간 — 내용 너비에 맞춤 */
const tickerDurationSec = ref(18);
const dynamicMenus = ref<Array<{ id: number; slug: string; title: string }>>([]);
const menuOrderMap = ref<Record<string, number>>({});
const SITE_FIXED_MENU_KEYS = [
  "notices",
  "safety-policy-goals",
  "risk-library",
  "worker-voice",
  "nonconformities",
  "document-explorer",
  "safety-education",
  "safety-inspections",
  "mobile",
  "mobile-site-search",
  "documents",
  "communications",
  "opinions",
  "info",
  "user-guide",
] as const;
const sidebarCollapsed = ref(false);
const isMobileViewport = ref(false);
const mobileDrawerOpen = ref(false);
let unreadTimer: number | null = null;
const headerSiteLabel = computed(() => (siteName.value ? `현장: ${siteName.value}` : "현장: -"));
const PRIMARY_MENUS = [
  "mobile",
  "safety-policy-goals",
  "risk-library",
  "worker-voice",
  "nonconformities",
  "document-explorer",
  "documents",
] as const;

onMounted(() => {
  initializeLayout();
  syncViewport();
  window.addEventListener("resize", syncViewport);
  window.addEventListener("resize", scheduleTickerDurationDebounced);
  window.addEventListener("besma-notice-ticker-read", handleNoticeTickerRead as EventListener);
  window.addEventListener("besma-doc-comment-ticker-ack", handleDocCommentTickerAck as EventListener);
  window.addEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
  unreadTimer = window.setInterval(() => {
    void Promise.all([loadCommunicationUnreadCount(), loadNoticeTicker(), loadDocCommentTicker()]);
  }, 30000);
});

watch(
  () => route.path,
  () => {
    if (isMobileViewport.value) {
      mobileDrawerOpen.value = false;
    }
  },
);

let tickerDurationDebounce: number | null = null;
function scheduleTickerDurationDebounced() {
  if (tickerDurationDebounce) {
    window.clearTimeout(tickerDurationDebounce);
  }
  tickerDurationDebounce = window.setTimeout(() => {
    tickerDurationDebounce = null;
    void scheduleTickerDuration();
  }, 150);
}

async function scheduleTickerDuration() {
  await nextTick();
  const el = tickerTrackRef.value;
  if (!el || (tickerItems.value.length === 0 && docCommentTickerCount.value === 0)) return;
  const fullW = el.scrollWidth;
  if (fullW < 8) return;
  const oneCopyW = fullW / 2;
  const pxPerSec = 52;
  const sec = oneCopyW / pxPerSec;
  tickerDurationSec.value = Math.min(55, Math.max(10, Math.round(sec * 10) / 10));
}

watch(
  [tickerItems, docCommentTickerCount],
  () => {
    void scheduleTickerDuration();
  },
  { flush: "post" },
);

function handleNoticeTickerRead() {
  void loadNoticeTicker();
}

function handleDocCommentTickerAck() {
  void loadDocCommentTicker();
}

watch(
  () => auth.user?.login_id,
  () => {
    void loadNoticeTicker();
    void loadDocCommentTicker();
  },
);

onUnmounted(() => {
  window.removeEventListener("resize", syncViewport);
  window.removeEventListener("resize", scheduleTickerDurationDebounced);
  window.removeEventListener("besma-notice-ticker-read", handleNoticeTickerRead as EventListener);
  window.removeEventListener("besma-doc-comment-ticker-ack", handleDocCommentTickerAck as EventListener);
  window.removeEventListener("besma-menu-order-updated", handleMenuOrderUpdated as EventListener);
  if (tickerDurationDebounce) {
    window.clearTimeout(tickerDurationDebounce);
    tickerDurationDebounce = null;
  }
  if (unreadTimer) {
    window.clearInterval(unreadTimer);
    unreadTimer = null;
  }
});

function syncViewport() {
  const nextMobile = window.innerWidth <= 768;
  if (nextMobile !== isMobileViewport.value) {
    mobileDrawerOpen.value = false;
  }
  isMobileViewport.value = nextMobile;
}

async function initializeLayout() {
  if (auth.token) {
    await auth.loadMe();
  }
  await Promise.all([loadBadge(), loadSiteName()]);
  await Promise.all([loadCommunicationUnreadCount(), loadNoticeTicker(), loadDocCommentTicker(), loadDynamicMenus()]);
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
    const res = await api.get("/notices/latest", { params: { limit: 3 } });
    const rows = (res.data?.items ?? []) as Array<{ id?: number; title?: string }>;
    const read = getTickerReadNoticeIds(auth.user?.login_id ?? null);
    tickerItems.value = rows
      .filter((row) => row.id != null && typeof row.title === "string")
      .map((row) => ({ id: Number(row.id), title: (row.title || "").trim() }))
      .filter((row) => row.title.length > 0 && !read.has(row.id));
  } catch {
    tickerItems.value = [];
  }
}

async function loadDocCommentTicker() {
  if (auth.user?.role !== "SITE") {
    docCommentTickerCount.value = 0;
    return;
  }
  try {
    const after = getDocCommentTickerAfterIso(auth.user?.login_id ?? null);
    const res = await api.get("/documents/comments/peer-count", {
      params: after ? { after } : {},
    });
    docCommentTickerCount.value = Number(res.data?.peer_comment_count ?? 0);
  } catch {
    docCommentTickerCount.value = 0;
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
  if (isMobileViewport.value) {
    mobileDrawerOpen.value = !mobileDrawerOpen.value;
    return;
  }
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function closeMobileDrawer() {
  mobileDrawerOpen.value = false;
}

function isPrimaryMenu(key: string) {
  return PRIMARY_MENUS.includes(key as (typeof PRIMARY_MENUS)[number]);
}

function isMenuActive(path: string) {
  return route.path === path;
}

/** `/site/mobile` 허브: 작업계획·일지 탭 모두 동일 사이드 메뉴 항목으로 표시 */
function menuItemActive(key: string, path: string) {
  if (key === "mobile") {
    return route.name === "site-mobile-ops" || route.name === "site-mobile-daily-capture";
  }
  if (key === "opinions") {
    return route.path.startsWith("/site/opinions");
  }
  return isMenuActive(path);
}

function menuLinkClass(key: string, path: string) {
  return {
    "menu-link": true,
    "menu-link-primary": isPrimaryMenu(key),
    "menu-link-secondary": !isPrimaryMenu(key),
    "menu-link-active": menuItemActive(key, path),
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
  min-width: 0;
  white-space: normal;
  line-height: 1.3;
  word-break: keep-all;
}

.menu-link-label {
  min-width: 0;
}

.menu-count-badge {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #dc2626;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.28) inset;
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
  min-height: 44px;
  display: flex;
  align-items: center;
}

.notice-ticker-track {
  display: inline-flex;
  width: max-content;
  gap: 36px;
  padding: 10px 16px;
  will-change: transform;
  animation: ticker-scroll linear infinite;
  animation-duration: var(--ticker-duration, 18s);
  font-size: 14px;
  line-height: 1.35;
}

.notice-ticker-item {
  color: #b91c1c;
  font-weight: 700;
  animation: ticker-blink 1s step-start infinite;
}

/* 내용을 두 번 이어 붙인 뒤 0 → -50% 로 한 바퀴(한 세트)만큼만 이동해 끊김·긴 공백 없이 반복 */
@keyframes ticker-scroll {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-50%);
  }
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

.hamburger-glyph {
  display: inline-block;
  font-size: 1.25rem;
  line-height: 1;
}

.layout-header-site-mobile .layout-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.layout-header-site-mobile .layout-header-center {
  max-width: 36%;
}

.layout-header-product {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.layout-header-actions .header-link {
  text-decoration: none;
  display: inline-block;
}

.layout-menu-mobile-site {
  padding-bottom: 24px;
}

.site-menu-section-label {
  margin: 12px 16px 6px;
  padding: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(229, 231, 235, 0.55);
}
</style>
