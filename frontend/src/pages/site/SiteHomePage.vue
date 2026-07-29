<template>
  <div class="site-home">
    <header>
      <p class="eyebrow">{{ auth.user?.name }}님 · {{ isMobileViewport ? "모바일 간편업무" : "현장 업무" }}</p>
      <h1>오늘 필요한 업무를 선택하세요</h1>
      <p>한 번 기록한 내용은 본사 확인과 출력에 그대로 사용됩니다.</p>
    </header>
    <section class="home-grid" aria-label="현장 주요 업무">
      <RouterLink class="home-card heat" to="/site/heat-stress">
        <span class="icon">℃</span><strong>체감온도 기록</strong><small>측정 · 조치 · 서명 · 출력</small>
      </RouterLink>
      <RouterLink class="home-card" to="/site/functional-eval/roster">
        <span class="icon">인</span><strong>기능인인정제</strong><small>평가 및 현황 확인</small>
      </RouterLink>
      <RouterLink class="home-card" :to="isMobileViewport ? '/site/mobile/communications' : '/site/communications'">
        <span class="icon">↔</span><strong>본사–현장 소통</strong><small>요청과 답변을 한곳에서</small>
      </RouterLink>
      <RouterLink v-if="!isMobileViewport" class="home-card" to="/site/documents">
        <span class="icon">문</span><strong>내 현장문서</strong><small>제출현황과 문서관리</small>
      </RouterLink>
      <RouterLink v-if="!isMobileViewport" class="home-card" to="/site/document-explorer">
        <span class="icon">⌕</span><strong>문서탐색</strong><small>필요한 문서를 빠르게 검색</small>
      </RouterLink>
    </section>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useMobileViewport } from "@/composables/useMobileViewport";

const auth = useAuthStore();
const { isMobileViewport } = useMobileViewport();
</script>

<style scoped>
.site-home{max-width:1050px;margin:0 auto;padding:12px}.site-home header{padding:24px 4px}.eyebrow{color:#0f766e;font-weight:800;margin:0 0 8px}.site-home h1{font-size:clamp(25px,4vw,38px);margin:0 0 8px;color:#0f172a}.site-home header p:last-child{color:#64748b;margin:0}.home-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.home-card{min-height:160px;padding:24px;border:1px solid #dbe4ee;border-radius:20px;background:#fff;text-decoration:none;color:#0f172a;display:flex;flex-direction:column;gap:8px;box-shadow:0 8px 25px rgba(15,23,42,.06);transition:.18s}.home-card:hover{transform:translateY(-2px);border-color:#5eead4}.home-card.heat{background:linear-gradient(145deg,#ecfeff,#fff7ed);border-color:#99f6e4}.icon{width:48px;height:48px;border-radius:14px;background:#0f766e;color:#fff;display:grid;place-items:center;font-size:21px;font-weight:900}.home-card strong{font-size:19px}.home-card small{color:#64748b;font-size:14px}@media(max-width:768px){.site-home{padding:4px}.site-home header{padding:16px 4px}.home-grid{grid-template-columns:1fr;gap:12px}.home-card{min-height:104px;padding:17px;display:grid;grid-template-columns:48px 1fr;grid-template-rows:auto auto;column-gap:14px}.home-card .icon{grid-row:1/3}.home-card strong{align-self:end}.home-card small{align-self:start}}
</style>
