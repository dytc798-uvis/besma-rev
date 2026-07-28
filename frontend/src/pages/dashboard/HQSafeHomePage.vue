<template>
  <main class="home-page">
    <header class="home-heading">
      <p>본사 안전보건</p>
      <h1>업무를 선택하세요</h1>
      <span>필요한 메뉴를 선택한 뒤 해당 업무 정보만 불러옵니다.</span>
    </header>

    <nav class="work-grid" aria-label="본사 주요 업무">
      <RouterLink class="work-card entry-documents" :to="{ name: 'hq-safe-documents' }">
        <span class="icon" aria-hidden="true">📚</span>
        <span class="copy"><strong>문서취합</strong><small>현장 문서 제출·검토 현황</small></span>
        <b aria-hidden="true">→</b>
      </RouterLink>
      <RouterLink class="work-card entry-functional" :to="{ name: 'hq-safe-functional-eval' }">
        <span class="icon" aria-hidden="true">🦺</span>
        <span class="copy"><strong>기능인인정제</strong><small>기능인 평가·승인 업무</small></span>
        <b aria-hidden="true">→</b>
      </RouterLink>
      <RouterLink v-if="canAccessSafetyLedgers" class="work-card entry-card" :to="{ name: 'hq-safe-card-expenses' }">
        <span class="icon" aria-hidden="true">🧾</span>
        <span class="copy"><strong>법인카드</strong><small>영수증 촬영·정산서 작성</small></span>
        <b aria-hidden="true">→</b>
      </RouterLink>
      <RouterLink v-if="canAccessSafetyLedgers" class="work-card entry-vehicle" :to="{ name: 'hq-safe-vehicle-logs' }">
        <span class="icon" aria-hidden="true">🚙</span>
        <span class="copy"><strong>운행기록부</strong><small>계기판 촬영·주행 기록</small></span>
        <b aria-hidden="true">→</b>
      </RouterLink>
      <RouterLink class="work-card entry-search" :to="{ name: 'hq-safe-site-search' }">
        <span class="icon" aria-hidden="true">📍</span>
        <span class="copy"><strong>현장검색</strong><small>전 현장 검색·현재 위치에서 길찾기</small></span>
        <b aria-hidden="true">→</b>
      </RouterLink>
    </nav>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const pilotNames = new Set(["정상익", "엄재복", "박영선", "조동문"]);
const canAccessSafetyLedgers = computed(() => pilotNames.has((auth.user?.name || "").trim()));
</script>

<style scoped>
.home-page {
  width: 100%;
  max-width: 1180px;
  margin: 0 auto;
  padding: clamp(10px, 2vw, 24px);
  box-sizing: border-box;
}

.home-heading {
  margin-bottom: 22px;
}

.home-heading p,
.home-heading h1,
.home-heading span {
  margin: 0;
}

.home-heading p {
  color: #0f6b6d;
  font-size: 13px;
  font-weight: 800;
}

.home-heading h1 {
  margin-top: 5px;
  color: #142033;
  font-size: clamp(25px, 4vw, 34px);
  letter-spacing: -.03em;
}

.home-heading span {
  display: block;
  margin-top: 7px;
  color: #64748b;
  font-size: 14px;
}

.work-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.work-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 13px;
  min-height: 118px;
  padding: 20px;
  border: 1px solid #d5e0e6;
  border-radius: 18px;
  color: #142033;
  text-decoration: none;
  background: #fff;
  box-shadow: 0 9px 25px rgba(31, 53, 71, .07);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
}

.work-card:hover,
.work-card:focus-visible {
  transform: translateY(-2px);
  border-color: #4f8790;
  box-shadow: 0 14px 28px rgba(31, 53, 71, .12);
}

.work-card.entry-search {
  grid-column: span 2;
  background: linear-gradient(145deg, #f2fbf8, #e9f5f2);
}

.icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: 14px;
  background: #e8f7f4;
  font-size: 25px;
}

.copy {
  display: grid;
  gap: 5px;
}

.copy strong {
  font-size: 19px;
}

.copy small {
  color: #64748b;
  font-size: 13px;
  line-height: 1.45;
}

.work-card > b {
  color: #0f6b6d;
  font-size: 22px;
}

@media (max-width: 980px) {
  .work-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .home-page { padding: 4px; }
  .home-heading { margin: 8px 4px 18px; }
  .home-heading span { font-size: 13px; }
  .work-grid { grid-template-columns: 1fr; gap: 11px; }
  .work-card,
  .work-card.entry-search { grid-column: auto; min-height: 92px; padding: 16px; }
  .entry-functional { order: 1; }
  .entry-card { order: 2; }
  .entry-vehicle { order: 3; }
  .entry-documents { order: 4; }
  .entry-search { order: 5; }
}
</style>
