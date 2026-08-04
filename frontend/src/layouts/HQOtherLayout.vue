<template>
  <div class="layout-root" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="layout-sidebar">
      <h1>BESMA CSMS 안전보건플랫폼 · 본사(타부서)</h1>
      <nav class="layout-menu">
        <RouterLink to="/hq-other/heat-stress">전 현장 체감온도 현황</RouterLink>
        <RouterLink to="/hq-other/field-form-uploads">현장 양식 업로드</RouterLink>
        <RouterLink to="/hq-other/dashboard">대시보드</RouterLink>
        <RouterLink to="/hq-other/documents">조회 가능한 문서</RouterLink>
        <RouterLink to="/hq-other/functional-eval-monitoring">기능인인정제 모니터링</RouterLink>
        <RouterLink to="/hq-other/opinions">운영 아이디어 제안</RouterLink>
        <RouterLink to="/hq-other/settings">설정 (placeholder)</RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header layout-header--branded">
        <div class="layout-header-left">
          <button class="sidebar-toggle-btn" @click="toggleSidebar">
            {{ sidebarCollapsed ? "펼치기" : "접기" }}
          </button>
        </div>
        <div class="layout-header-brand-center">
          <AppFullLogo />
        </div>
        <div class="layout-header-actions">
          <span style="margin-right: 8px">
            {{ auth.user?.name }} ({{ auth.user?.login_id }})
            <template v-if="auth.isTestPersonaMode && auth.effectivePersona">
              / Persona: {{ auth.effectivePersona }}
            </template>
          </span>
          <button v-if="auth.isTestPersonaMode" class="secondary" style="margin-right: 8px" @click="goPersonaSelect">
            페르소나 전환
          </button>
          <RouterLink class="secondary" style="margin-right: 8px; text-decoration: none; display: inline-block" to="/change-password">비밀번호 변경</RouterLink>
          <button class="secondary" @click="handleLogout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main">
        <div v-if="auth.isRolePreviewActive" class="role-preview-banner">
          읽기 전용 검증모드 · 본사 타부서 · 저장·다운로드·승인·삭제가 차단됩니다.
        </div>
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { ref } from "vue";
import { useRouter, RouterLink, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AppFullLogo from "@/components/branding/AppFullLogo.vue";

const auth = useAuthStore();
const router = useRouter();
const sidebarCollapsed = ref(false);

onMounted(() => {
  if (!auth.user) {
    auth.loadMe();
  }
});

function handleLogout() {
  auth.logout();
  router.push({ name: "login" });
}

function goPersonaSelect() {
  router.push({ name: "persona-select" });
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

.layout-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  z-index: 2;
}

.layout-header-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
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

</style>

