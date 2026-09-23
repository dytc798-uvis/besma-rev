<template>
  <nav class="public-service-menu" aria-label="안전보건 업무 메뉴">
    <p class="menu-eyebrow">BESMA · 안전보건실</p>
    <h2>현장 안전보건 메뉴</h2>
    <RouterLink to="/law-register" class="service-link">
      <span class="service-symbol" aria-hidden="true">▤</span>
      <span><strong>법규등록부</strong><small>누구나 열람 · 2026년 하반기</small></span>
      <span aria-hidden="true">›</span>
    </RouterLink>
    <RouterLink to="/services/worker-voice" class="service-link">
      <span class="service-symbol" aria-hidden="true">✎</span>
      <span><strong>근로자의견청취</strong><small>로그인 후 의견 등록·확인</small></span>
      <span aria-hidden="true">›</span>
    </RouterLink>
    <RouterLink to="/services/heat-stress" class="service-link">
      <span class="service-symbol" aria-hidden="true">℃</span>
      <span><strong>체감온도 기록</strong><small>로그인 후 내 현장 기록</small></span>
      <span aria-hidden="true">›</span>
    </RouterLink>
    <RouterLink to="/services/opinions" class="service-link">
      <span class="service-symbol" aria-hidden="true">◇</span>
      <span><strong>운영 아이디어 제안</strong><small>로그인 후 제안 등록·확인</small></span>
      <span aria-hidden="true">›</span>
    </RouterLink>
    <div class="service-coming" role="note">
      <strong>기능인인정제</strong>
      <span>11월에 오픈합니다.</span>
    </div>
    <p class="menu-foot">의견과 측정 기록은 기존 BESMA 계정으로 이용합니다.</p>
  </nav>
</template>

<style scoped>
.public-service-menu { box-sizing: border-box; padding: 26px; background: #fff; border: 1px solid #dae3ed; border-radius: 18px; color: #20354f; }
.menu-eyebrow { color: #376997; font-size: 12px; font-weight: 750; letter-spacing: .08em; margin: 0 0 10px; }
h2 { font-size: 21px; margin: 0 0 22px; letter-spacing: -.04em; }
.service-link { display: flex; gap: 13px; align-items: center; padding: 17px 0; color: inherit; text-decoration: none; border-top: 1px solid #edf1f6; }
.service-link > span:nth-child(2) { flex: 1; }
.service-link strong, .service-link small { display: block; }
.service-link strong { font-size: 15px; }
.service-link small { font-size: 12px; margin-top: 6px; color: #61758a; line-height: 1.5; }
.service-symbol { display: grid; place-items: center; width: 36px; height: 36px; flex-shrink: 0; border-radius: 10px; color: #215f8e; background: #edf5fb; font-size: 20px; }
.service-link:hover strong, .service-link.router-link-active strong { color: #1473ad; }
.service-link:focus-visible { outline: 3px solid #187bac; outline-offset: 3px; }
.service-coming { background: #fff6e8; border: 1px solid #f2dfba; border-radius: 10px; padding: 16px; margin-top: 14px; display: grid; gap: 6px; font-size: 14px; }
.service-coming span { color: #946326; font-size: 13px; }
.menu-foot { color: #6b7c90; font-size: 12px; line-height: 1.7; margin: 16px 0 0; }
</style>
