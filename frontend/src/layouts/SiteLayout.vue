<template>
  <div class="layout-root" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="layout-sidebar">
      <h1>BESMA 임시플랫폼 · 현장</h1>
      <nav class="layout-menu">
        <RouterLink to="/site/dashboard">대시보드</RouterLink>
        <RouterLink to="/site/mobile">모바일 운영</RouterLink>
        <RouterLink to="/site/mobile/site-search">현장 검색</RouterLink>
        <RouterLink to="/site/document-explorer">문서 탐색</RouterLink>
        <RouterLink to="/site/risk-library">위험성평가 DB 조회</RouterLink>
        <RouterLink to="/site/documents"
          >내 현장 문서 <span v-if="badge.incomplete_count > 0">({{ badge.incomplete_count }})</span></RouterLink
        >
        <RouterLink to="/site/communications"
          >소통자료 <span v-if="communicationUnreadCount > 0">({{ communicationUnreadCount }})</span></RouterLink
        >
        <RouterLink to="/site/opinions">운영 아이디어 제안</RouterLink>
        <RouterLink to="/site/info">현장 정보/설정</RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header">
        <div class="layout-header-left">
          <button class="sidebar-toggle-btn" @click="toggleSidebar">
            {{ sidebarCollapsed ? "펼치기" : "접기" }}
          </button>
          <span>BESMA 임시플랫폼 · SITE</span>
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
      <main class="layout-main">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter, RouterLink, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/services/api";

const auth = useAuthStore();
const router = useRouter();
const badge = ref({ incomplete_count: 0 });
const communicationUnreadCount = ref(0);
const siteName = ref<string>("");
const sidebarCollapsed = ref(false);
let unreadTimer: number | null = null;
const headerSiteLabel = computed(() => (siteName.value ? `현장: ${siteName.value}` : "현장: -"));

onMounted(() => {
  initializeLayout();
  unreadTimer = window.setInterval(() => {
    void loadCommunicationUnreadCount();
  }, 30000);
});

onUnmounted(() => {
  if (unreadTimer) {
    window.clearInterval(unreadTimer);
    unreadTimer = null;
  }
});

async function initializeLayout() {
  if (auth.token) {
    await auth.loadMe();
  }
  await Promise.all([loadBadge(), loadSiteName()]);
  await loadCommunicationUnreadCount();
}

async function loadBadge() {
  try {
    const res = await api.get("/documents/badges/site", {
      params: { date: new Date().toISOString().slice(0, 10) },
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

function handleLogout() {
  auth.logout();
  router.push({ name: "login" });
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
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
