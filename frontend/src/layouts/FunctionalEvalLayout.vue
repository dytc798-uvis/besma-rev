<template>
  <div class="layout-root functional-eval-shell">
    <aside class="layout-sidebar">
      <h1>BESMA · 기능인제 인사고과</h1>
      <nav class="layout-menu">
        <RouterLink to="/site/functional-eval">인사고과·제재</RouterLink>
      </nav>
    </aside>
    <section class="layout-content">
      <header class="layout-header">
        <div class="header-title">기능인제 일용직 인사고과</div>
        <div class="header-right">
          <span>{{ auth.user?.name }} (현장 {{ auth.user?.login_id }})</span>
          <button class="stitch-btn-secondary" type="button" @click="logout">로그아웃</button>
        </div>
      </header>
      <main class="layout-main">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";

const auth = useAuthStore();
const router = useRouter();

function logout() {
  auth.logout();
  router.push({ name: "login" });
}
</script>

<style scoped>
.functional-eval-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}
.layout-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #e5e7eb;
}
.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}
.layout-main {
  padding: 20px;
}
</style>
