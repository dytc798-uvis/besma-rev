<template>
  <div class="register-page">
    <header class="register-header">
      <RouterLink to="/law-register" class="brand"><img :src="FULL_LOGO_SRC" alt="BOOHYUN 부현전기" /><span>안전보건실</span></RouterLink>
      <div class="header-actions"><a class="mobile-menu-link" href="#public-menu">업무 메뉴</a><RouterLink to="/login" class="login-link">BESMA 로그인</RouterLink></div>
    </header>
    <div class="register-layout">
      <aside id="public-menu"><PublicServiceMenu /><div class="qr-card"><img src="/law-register/qr.png" alt="BESMA 법규등록부 공개 페이지 QR코드" /><p>전 현장 함께 보는 법규등록부</p><a href="/law-register/qr.png" download="부현_법규등록부_QR.png">QR코드 저장</a></div></aside>
      <main id="register-main">
        <div class="register-intro"><span class="public-badge">로그인 없이 열람</span><p class="eyebrow">2026 SECOND HALF</p><h1>안전보건 법규등록부</h1><p>법 분류와 키워드로 찾아보고,<br class="mobile-break" /> 서명된 원문에서 확인하세요.</p></div>
        <p v-if="error" class="load-error" role="alert">{{ error }} <button type="button" @click="loadRegister">다시 불러오기</button></p>
        <p v-else-if="!register" role="status">법규등록부를 불러오는 중입니다.</p>
        <template v-else>
          <div class="document-strip"><span><strong>{{ register.title }}</strong><small>서명본 · {{ register.pages }}쪽 · 등록 {{ register.updatedAt }}</small></span><a :href="register.documentUrl" target="_blank" rel="noopener">PDF 열기 ↗</a><a :href="register.documentUrl" :download="register.filename">다운로드 ↓</a></div>
          <div class="register-tabs" role="tablist" aria-label="법규등록부 보기"><button id="search-tab" role="tab" :aria-selected="tab === 'search'" aria-controls="search-panel" :tabindex="tab === 'search' ? 0 : -1" @click="tab = 'search'" @keydown.right="activateTab('pdf')" @keydown.left="activateTab('pdf')">법 분류·내용 검색</button><button id="pdf-tab" role="tab" :aria-selected="tab === 'pdf'" aria-controls="pdf-panel" :tabindex="tab === 'pdf' ? 0 : -1" @click="tab = 'pdf'" @keydown.right="activateTab('search')" @keydown.left="activateTab('search')">서명본 원문</button></div>
          <section v-if="tab === 'search'" id="search-panel" role="tabpanel" aria-labelledby="search-tab">
            <label class="search-label" for="law-search">법령명·본문 키워드 검색</label><div class="search-box"><span aria-hidden="true">⌕</span><input id="law-search" v-model="query" type="search" maxlength="120" placeholder="예: 위험성평가, 안전난간, 누전차단기" /><button v-if="query" type="button" @click="query = ''">지우기</button></div>
            <label class="category-label">법 분류 <select v-model="category"><option value="">전체 법 분류</option><option v-for="item in categories" :key="item" :value="item">{{ item }}</option></select></label>
            <div class="results-heading"><p role="status">{{ filtered.length }}개 항목 · {{ groups.length }}개 분류</p><button v-if="query || category" type="button" @click="query = ''; category = ''">전체 보기</button></div>
            <p v-if="!filtered.length" class="empty-result">검색 결과가 없습니다. 다른 키워드나 법 분류를 선택해 주세요.</p>
            <div v-for="group in groups" :key="group.category" class="law-group"><h2>{{ group.category }} <span>{{ group.records.length }}</span></h2><details v-for="record in group.records" :key="record.id" :open="Boolean(query.trim())"><summary><span>{{ record.title }}</span><small>{{ record.page }}쪽</small></summary><div class="record-content"><p>{{ record.content }}</p><button type="button" @click="openPage(record.page)">서명본 {{ record.page }}쪽 확인 →</button></div></details></div>
          </section>
          <section v-else id="pdf-panel" role="tabpanel" aria-labelledby="pdf-tab"><LawPdfViewer :url="register.documentUrl" :page="pdfPage" @page="pdfPage = $event" /></section>
          <p class="source-note">검색 내용은 같은 등록부의 한글 자료를 바탕으로 제공합니다. 정확한 내용은 서명본 원문을 확인해 주세요.</p>
        </template>
        <footer>부현전기 · 안전보건실 <span>법규등록부 2026-H2 · 2026.09.23</span></footer>
      </main>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { FULL_LOGO_SRC } from "@/constants/branding";
import PublicServiceMenu from "@/components/public/PublicServiceMenu.vue";
import LawPdfViewer from "@/components/public/LawPdfViewer.vue";
interface LawRecord { id: string; page: number; category: string; title: string; content: string; }
interface Register { title: string; pages: number; updatedAt: string; filename: string; documentUrl: string; records: LawRecord[]; }
const register = ref<Register | null>(null);
const error = ref("");
const query = ref("");
const category = ref("");
const tab = ref<'search' | 'pdf'>('search');
const pdfPage = ref(1);
const categories = computed(() => [...new Set(register.value?.records.map(r => r.category) || [])]);
const filtered = computed(() => {
  const terms = query.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return (register.value?.records || []).filter(r => (!category.value || category.value === r.category) && terms.every(term => `${r.category} ${r.title} ${r.content}`.toLocaleLowerCase().includes(term)));
});
const groups = computed(() => categories.value.map(category => ({ category, records: filtered.value.filter(r => r.category === category) })).filter(g => g.records.length));
async function loadRegister() {
  error.value = "";
  try {
    const response = await fetch('/law-register/register.json', { cache: 'no-cache', credentials: 'omit' });
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (!Array.isArray(data.records) || !data.documentUrl?.startsWith('/law-register/')) throw new Error();
    register.value = data;
  } catch { error.value = "등록부를 불러오지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요."; }
}
async function activateTab(value: 'search' | 'pdf') { tab.value = value; await nextTick(); document.getElementById(`${value}-tab`)?.focus(); }
async function openPage(page: number) { pdfPage.value = page; await activateTab('pdf'); document.getElementById('pdf-panel')?.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
onMounted(loadRegister);
</script>
<style scoped>
.register-page { min-height: 100vh; background: #f4f7fb; color: #20354f; }
.header-actions { display: flex; align-items: center; gap: 12px; }.mobile-menu-link { display: none; color: #3a6283; font-size: 12px; }
@media(max-width: 700px) { .mobile-menu-link { display: inline; } }
.register-header { height: 82px; padding: 0 max(24px, calc((100vw - 1370px) / 2)); display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e1e8f0; background: white; gap: 16px; }
.brand { display: flex; align-items: center; gap: 20px; text-decoration: none; color: #66798c; font-size: 13px; }
.brand img { width: 156px; height: 48px; object-fit: contain; }.brand span { border-left: 1px solid #dce4eb; padding-left: 20px; }
.login-link { border: 1px solid #ccd8e4; border-radius: 8px; padding: 10px 16px; text-decoration: none; color: #234969; font-size: 13px; white-space: nowrap; }
.register-layout { max-width: 1370px; margin: auto; padding: 34px 24px; display: grid; grid-template-columns: 285px minmax(0,1fr); gap: 36px; }
aside { min-width: 0; } main { min-width: 0; }.qr-card { margin-top: 18px; padding: 20px; text-align: center; color: #64798c; font-size: 12px; }.qr-card img { width: 120px; height: 120px; }.qr-card a { color: #24658f; }
.register-intro { position: relative; padding: 14px 0 24px; }.eyebrow { font-size: 11px; letter-spacing: .16em; color: #4380a4; font-weight: 750; margin: 0 0 10px; } h1 { font-size: clamp(26px,3vw,36px); line-height: 1.4; margin: 0 0 12px; letter-spacing: -.06em; }.register-intro > p:last-child { color: #66798b; font-size: 14px; line-height: 1.8; margin: 0; }.public-badge { float: right; padding: 7px 10px; border-radius: 18px; background: #e6f3ee; color: #277c61; font-size: 11px; }.mobile-break { display: none; }
.document-strip { background: white; border: 1px solid #dce5ee; padding: 20px; border-radius: 12px; display: flex; align-items: center; gap: 20px; }.document-strip > span { flex: 1; }.document-strip strong { display: block; font-size: 14px; }.document-strip small { display: block; margin-top: 7px; font-size: 12px; color: #728194; }.document-strip a { font-size: 12px; color: #226692; white-space: nowrap; }
.register-tabs { display: flex; gap: 24px; border-bottom: 1px solid #d5e0ec; margin: 24px 0; }.register-tabs button { border: 0; border-bottom: 3px solid transparent; padding: 14px 0; background: transparent; color: #738298; font-size: 14px; font-weight: 700; border-radius: 0; }.register-tabs button[aria-selected=true] { color: #1a648f; border-bottom-color: #267aa8; }
.search-label { display: block; font-size: 13px; font-weight: 700; margin-bottom: 9px; }.search-box { display: flex; align-items: center; gap: 12px; background: #fff; border: 1px solid #cbd9e6; padding: 6px 15px; border-radius: 10px; }.search-box > span { font-size: 28px; color: #53789b; }.search-box input { width: 100%; border: none; background: transparent; font-size: 14px; min-width: 0; padding: 10px 0; box-shadow: none; }.search-box button { flex-shrink: 0; border: none; background: #eff4f8; color: #486883; font-size: 12px; }
.category-label { display: flex; align-items: center; gap: 12px; font-size: 12px; color: #61768a; margin-top: 12px; }.category-label select { width: auto; max-width: 100%; font-size: 13px; padding: 8px; border: 1px solid #d7e2eb; border-radius: 6px; background: white; }.results-heading { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #677c91; padding: 12px 0; }.results-heading button { background: transparent; border: none; color: #246990; }
.law-group { background: #fff; border: 1px solid #dce5ee; border-radius: 12px; margin-bottom: 15px; overflow: hidden; }.law-group h2 { display: flex; gap: 10px; align-items: center; font-size: 15px; padding: 17px 20px; margin: 0; background: #eef4f9; }.law-group h2 span { border-radius: 20px; font-size: 11px; background: #dce9f3; color: #42678a; padding: 3px 7px; }.law-group details { border-top: 1px solid #edf1f5; }.law-group summary { display: flex; align-items: center; gap: 12px; cursor: pointer; padding: 17px 20px; font-size: 13px; line-height: 1.6; list-style: none; }.law-group summary:before { content: '+'; color: #6086a5; font-size: 18px; }.law-group details[open] summary:before { content: '−'; }.law-group summary span { flex: 1; }.law-group summary small { font-size: 11px; color: #6f8296; white-space: nowrap; }.record-content { padding: 0 20px 20px; }.record-content p { white-space: pre-wrap; font-size: 13px; line-height: 1.95; color: #41576c; overflow-wrap: anywhere; }.record-content button { border: 1px solid #d4e2ed; border-radius: 6px; padding: 9px 12px; background: #f2f7fb; color: #226a97; font-size: 12px; }
.source-note, footer { font-size: 12px; color: #718497; line-height: 1.8; }.source-note { margin: 22px 0; }footer { border-top: 1px solid #dce5ee; padding-top: 20px; display: flex; justify-content: space-between; gap: 12px; }.load-error,.empty-result { padding: 24px; background: white; border-radius: 12px; line-height: 1.8; }
button, a, summary { touch-action: manipulation; }button:focus-visible, a:focus-visible, summary:focus-visible { outline: 3px solid #2482b9; outline-offset: 3px; }
@media(max-width: 960px) { .register-layout { grid-template-columns: 240px minmax(0,1fr); gap: 20px; padding: 24px 16px; }.document-strip { flex-wrap: wrap; }.document-strip > span { flex-basis: 100%; }.public-badge { float: none; display: inline-block; margin-bottom: 12px; } }
@media(max-width: 700px) { .register-header { height: 70px; padding: 0 16px; }.brand img { width: 120px; }.brand span { display: none; }.register-layout { display: flex; flex-direction: column; padding: 18px 14px; }.register-layout > aside { order: 2; }.register-intro { padding-top: 4px; }.qr-card { display: none; }.register-tabs { gap: 22px; }.mobile-break { display: block; }.document-strip { padding: 16px; gap: 14px; }.law-group summary { padding: 15px; }.law-group h2 { padding: 16px; }.category-label select { min-width: 0; flex: 1; }footer { flex-direction: column; }.login-link { font-size: 12px; padding: 9px 11px; } }
</style>
