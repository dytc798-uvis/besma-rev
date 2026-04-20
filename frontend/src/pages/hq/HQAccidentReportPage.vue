<template>
  <div class="report-page">
    <div class="report-toolbar no-print">
      <RouterLink class="secondary-link" :to="{ name: 'hq-safe-accident-detail', params: { id: String(accidentId) } }">
        상세로 돌아가기
      </RouterLink>
      <button type="button" class="secondary" @click="previewPrint">보고서 출력</button>
    </div>

    <p v-if="loading" class="muted">불러오는 중…</p>
    <p v-else-if="errorMessage" class="error">{{ errorMessage }}</p>

    <article v-else-if="detail" class="report-paper report-print-root">
      <header class="report-header">
        <div>
          <h1>사고 보고서</h1>
          <p class="subtitle">웹 사고관리 시스템 출력본</p>
        </div>
        <dl class="header-meta">
          <div>
            <dt>사고ID</dt>
            <dd>{{ detail.accident_id }}</dd>
          </div>
          <div>
            <dt>출력일시</dt>
            <dd>{{ formatDateTime(new Date().toISOString()) }}</dd>
          </div>
        </dl>
      </header>

      <section class="report-section">
        <h2>기본정보</h2>
        <dl class="info-grid">
          <div><dt>사고ID</dt><dd>{{ detail.accident_id }}</dd></div>
          <div><dt>현장명</dt><dd>{{ detail.site_standard_name || detail.site_name || "—" }}</dd></div>
          <div><dt>보고자</dt><dd>{{ nz(detail.reporter_name) }}</dd></div>
          <div><dt>사고일시</dt><dd>{{ formatAccidentMoment(detail.accident_datetime, detail.accident_datetime_text) }}</dd></div>
          <div class="full-row"><dt>사고장소</dt><dd>{{ nz(detail.accident_place) }}</dd></div>
        </dl>
      </section>

      <section class="report-section">
        <h2>사고내용</h2>
        <dl class="info-grid">
          <div class="full-row"><dt>작업내용</dt><dd>{{ nz(detail.work_content) }}</dd></div>
          <div><dt>재해자</dt><dd>{{ nz(detail.injured_person_name) }}</dd></div>
          <div class="full-row text-block"><dt>사고경위</dt><dd>{{ nz(detail.accident_circumstance || detail.initial_report_template) }}</dd></div>
          <div class="full-row text-block"><dt>사고원인</dt><dd>{{ nz(detail.accident_reason) }}</dd></div>
        </dl>
      </section>

      <section class="report-section two-column">
        <div>
          <h2>피해내용</h2>
          <dl class="info-grid compact-grid">
            <div><dt>상해부위</dt><dd>{{ nz(detail.injured_part) }}</dd></div>
            <div><dt>상병명</dt><dd>{{ nz(detail.diagnosis_name) }}</dd></div>
          </dl>
        </div>
        <div>
          <h2>관리</h2>
          <dl class="info-grid compact-grid">
            <div class="full-row text-block"><dt>조치사항</dt><dd>{{ nz(detail.action_taken) }}</dd></div>
            <div><dt>관리구분</dt><dd>{{ detail.management_category }}</dd></div>
          </dl>
        </div>
      </section>

      <section class="report-section">
        <h2>비고</h2>
        <dl class="info-grid">
          <div class="full-row text-block"><dt>비고</dt><dd>{{ nz(detail.notes) }}</dd></div>
        </dl>
      </section>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { fetchAccidentDetail, type AccidentDetail } from "@/services/accidents";
import { formatAccidentMoment } from "@/utils/accidentDateDisplay";

const route = useRoute();
const detail = ref<AccidentDetail | null>(null);
const loading = ref(true);
const errorMessage = ref("");

const accidentId = computed(() => Number(route.params.id));
const shouldAutoPrint = computed(() => route.query.autoPrint === "1");

function nz(value: string | null | undefined) {
  const text = String(value ?? "").trim();
  return text || "—";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ko-KR");
  } catch {
    return value;
  }
}

function previewPrint() {
  window.print();
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  const id = accidentId.value;
  if (!Number.isFinite(id) || id <= 0) {
    errorMessage.value = "잘못된 사고 ID입니다.";
    loading.value = false;
    return;
  }
  try {
    detail.value = await fetchAccidentDetail(id);
    if (shouldAutoPrint.value) {
      await nextTick();
      window.print();
    }
  } catch {
    errorMessage.value = "보고서 데이터를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});

watch(
  () => route.params.id,
  () => {
    void load();
  },
);
</script>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.report-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.report-paper {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  padding: 14mm;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  color: #111827;
  box-sizing: border-box;
}
.report-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 2px solid #1f2937;
  padding-bottom: 12px;
}
.report-header h1 {
  margin: 0;
  font-size: 28px;
  letter-spacing: 0.02em;
}
.subtitle {
  margin: 6px 0 0;
  color: #4b5563;
  font-size: 13px;
}
.header-meta {
  margin: 0;
  min-width: 220px;
  display: grid;
  gap: 6px;
}
.header-meta div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
}
.header-meta dt,
.info-grid dt {
  color: #374151;
  font-weight: 700;
}
.header-meta dd,
.info-grid dd {
  margin: 0;
}
.report-section {
  margin-top: 18px;
}
.report-section h2 {
  margin: 0 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #d1d5db;
  font-size: 18px;
}
.two-column {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 18px;
}
.compact-grid {
  grid-template-columns: 1fr;
}
.info-grid div {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px;
  align-items: start;
}
.full-row {
  grid-column: 1 / -1;
}
.text-block dd {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.secondary-link {
  color: #334155;
  text-decoration: none;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
}
.muted {
  color: #64748b;
}
.error {
  color: #b91c1c;
  font-weight: 600;
}
@media (max-width: 1024px) {
  .report-paper {
    width: 100%;
    min-height: auto;
    padding: 16px;
  }
  .report-header,
  .two-column,
  .info-grid {
    grid-template-columns: 1fr;
  }
  .report-header {
    display: grid;
  }
}
@media print {
  .no-print {
    display: none !important;
  }
  .report-page {
    background: #fff;
  }
  .report-paper {
    width: auto;
    min-height: auto;
    margin: 0;
    border: none;
    border-radius: 0;
    padding: 0;
  }
  @page {
    size: A4;
    margin: 12mm;
  }
}
</style>

<style>
/* 레이아웃(사이드바 등)은 숨기고 보고서 본문만 인쇄한다. scoped 밖 전역 규칙. */
@media print {
  body * {
    visibility: hidden;
  }
  .report-print-root,
  .report-print-root * {
    visibility: visible;
  }
  .report-print-root {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0;
    background: #fff;
    box-shadow: none;
    border: none;
  }
}
</style>
