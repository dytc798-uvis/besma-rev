<template>

  <div class="work-plan-page card">

    <h1 class="title">지게차 작업계획서</h1>

    <p class="hint">

      회색 글씨는 <strong>입력 예시</strong>입니다. 고정값(현장명·업체·오늘 날짜)은 미리 채워져 있으며 수정할 수 있습니다.

      모델명 입력 시 제원(정격하중 등)을 자동 조회합니다.

    </p>



    <form class="form-grid" @submit.prevent="onSubmit">

      <section class="block block-fixed">

        <h2>고정값 (수정 가능)</h2>

        <label>

          현장명

          <input v-model="form.site_name" class="prefilled" />

        </label>

        <label>

          협력사 / 업체명

          <input v-model="form.company_name" class="prefilled" />

        </label>

        <div class="row-3">

          <label>작성일 (연) <input v-model="form.document_date_year" class="prefilled" /></label>

          <label>월 <input v-model="form.document_date_month" class="prefilled" /></label>

          <label>일 <input v-model="form.document_date_day" class="prefilled" /></label>

        </div>

      </section>



      <section class="block">

        <h2>1. 작업개요</h2>

        <label>

          작업명 <span class="req">*</span>

          <input v-model="form.work_name" required class="prefilled" />

        </label>

        <label>

          작업장소

          <input v-model="form.work_location" class="prefilled" placeholder="지상1층" />

        </label>

        <div class="row-3">

          <label>시작 연 <input v-model="form.period_start_year" class="prefilled" /></label>

          <label>월 <input v-model="form.period_start_month" class="prefilled" /></label>

          <label>일 <input v-model="form.period_start_day" class="prefilled" /></label>

        </div>

        <div class="row-3">

          <label>종료 연 <input v-model="form.period_end_year" class="prefilled" /></label>

          <label>월 <input v-model="form.period_end_month" class="prefilled" /></label>

          <label>일 <input v-model="form.period_end_day" class="prefilled" /></label>

        </div>

        <label>

          참석 인원

          <input v-model="form.participants" class="prefilled" placeholder="2" />

        </label>

      </section>



      <section class="block">

        <h2>2. 책임자 · 신호수 · 작업지휘자</h2>

        <div class="row-2">

          <label>운전원(책임자) 성명 <input v-model="form.supervisor_name" placeholder="홍길동" /></label>

          <label>연락처 <input v-model="form.supervisor_phone" placeholder="010-0000-0000" /></label>

        </div>

        <div class="row-2">

          <label>면허 종류 <input v-model="form.supervisor_license_type" placeholder="건설기계조종사(지게차)" /></label>

          <label>면허 번호 <input v-model="form.supervisor_license_no" placeholder="면허번호" /></label>

        </div>

        <div class="row-2">

          <label>신호자 성명 <input v-model="form.signal_name" placeholder="김신호" /></label>

          <label>연락처 <input v-model="form.signal_phone" placeholder="010-0000-0000" /></label>

        </div>

        <div class="row-2">

          <label>신호자 교육 <input v-model="form.signal_license_type" placeholder="특별교육" /></label>

          <label>기초교육 <input v-model="form.signal_license_no" placeholder="기초안전보건교육" /></label>

        </div>

        <div class="row-2">

          <label>작업지휘자 <input v-model="form.commander_name" placeholder="차광식" /></label>

          <label>직책 <input v-model="form.commander_role" placeholder="부장" /></label>

        </div>

      </section>



      <section class="block">

        <h2>3. 장비 · 제원</h2>

        <label>

          장비 종류

          <input v-model="form.equipment_type" class="prefilled" placeholder="카운터밸런스형" />

        </label>

        <div class="row-2">

          <label>

            모델명

            <input

              v-model="form.equipment_model"

              class="example-field"

              :placeholder="ph.equipment_model"

              @blur="onModelBlur"

            />

          </label>

          <label>

            등록번호

            <input v-model="form.registration_no" class="example-field" :placeholder="ph.registration_no" />

          </label>

        </div>

        <p v-if="specLookupMessage" class="spec-hint" :class="{ ok: specLookupOk }">{{ specLookupMessage }}</p>

        <div class="row-2">

          <label>

            제작년도

            <input v-model="form.manufacture_year" class="example-field" :placeholder="ph.manufacture_year" />

          </label>

          <label>

            정격하중

            <input v-model="form.rated_capacity" class="example-field" :placeholder="ph.rated_capacity" />

          </label>

        </div>

        <label>

          등록업체명

          <input v-model="form.registered_company" class="example-field" :placeholder="ph.registered_company" />

        </label>

        <div class="row-4">

          <label>

            전장(mm)

            <input v-model="form.length_mm" type="number" class="example-field" :placeholder="ph.length_mm" />

          </label>

          <label>

            전폭(mm)

            <input v-model="form.width_mm" type="number" class="example-field" :placeholder="ph.width_mm" />

          </label>

          <label>

            전고(mm)

            <input v-model="form.height_mm" type="number" class="example-field" :placeholder="ph.height_mm" />

          </label>

          <label>

            허용하중(kg)

            <input v-model="form.max_lifting_kg" type="number" class="example-field" :placeholder="ph.max_lifting_kg" />

          </label>

        </div>

        <label>

          작업장소 (일일계획)

          <input v-model="form.work_location_plan" placeholder="예: B동 1층 자재 야적장" />

        </label>

        <label>

          작업내용 (일일계획)

          <input v-model="form.work_content_plan" placeholder="예: 철골 자재 하역 및 적재" />

        </label>

      </section>



      <div class="actions">

        <button type="submit" class="primary" :disabled="loading">{{ loading ? "생성 중…" : "엑셀 생성·저장" }}</button>

        <button v-if="lastFilename" type="button" class="secondary" @click="openDownload">다운로드</button>

      </div>

    </form>



    <p v-if="message" class="message" :class="{ error: isError }">{{ message }}</p>

    <p v-if="lastSavedPath" class="saved-path">저장: {{ lastSavedPath }}</p>

  </div>

</template>



<script setup lang="ts">

import { onUnmounted, reactive, ref, watch } from "vue";

import {

  createForkliftWorkPlanDefaults,

  FORKLIFT_EQUIPMENT_PLACEHOLDERS,

} from "@/config/forkliftWorkPlanDefaults";

import {

  downloadForkliftWorkPlanFile,

  generateForkliftWorkPlan,

  lookupForkliftSpecs,

  type ForkliftWorkPlanInput,

} from "@/services/workPlanForklift";



const ph = FORKLIFT_EQUIPMENT_PLACEHOLDERS;

const loading = ref(false);

const message = ref("");

const isError = ref(false);

const lastFilename = ref("");

const lastSavedPath = ref("");

const specLookupMessage = ref("");

const specLookupOk = ref(false);



const form = reactive(createForkliftWorkPlanDefaults());



function isEmpty(v: unknown) {
  return v === "" || v == null;
}



watch(

  () => form.equipment_model,

  (model) => {

    specLookupMessage.value = "";

    scheduleSpecLookup(model);

  },

);



let lookupTimer: ReturnType<typeof setTimeout> | null = null;



function scheduleSpecLookup(model: string) {

  if (lookupTimer) clearTimeout(lookupTimer);

  const trimmed = model.trim();

  if (trimmed.length < 3) return;

  lookupTimer = setTimeout(() => void runSpecLookup(trimmed), 600);

}



async function runSpecLookup(model: string) {

  specLookupMessage.value = "제원 조회 중…";

  specLookupOk.value = false;

  try {

    const spec = await lookupForkliftSpecs(model);

    if (spec.source === "none") {

      specLookupMessage.value = "카탈로그·웹에서 제원을 찾지 못했습니다. 직접 입력하세요.";

      return;

    }

    applySpec(spec, spec.source === "catalog" ? "내장 카탈로그" : "웹 검색");

    specLookupOk.value = true;

  } catch {

    specLookupMessage.value = "제원 조회에 실패했습니다.";

  }

}



function applySpec(

  spec: Awaited<ReturnType<typeof lookupForkliftSpecs>>,

  sourceLabel: string,

) {

  const map: [keyof ForkliftWorkPlanInput, string | number | null | undefined][] = [

    ["equipment_type", spec.equipment_type],

    ["rated_capacity", spec.rated_capacity],

    ["manufacture_year", spec.manufacture_year],

    ["length_mm", spec.length_mm],

    ["width_mm", spec.width_mm],

    ["height_mm", spec.height_mm],

    ["max_lifting_kg", spec.max_lifting_kg],

  ];

  let filled = 0;

  for (const [key, val] of map) {

    if (val == null || val === "") continue;

    if (!isEmpty((form as Record<string, unknown>)[key as string])) continue;

    (form as Record<string, unknown>)[key as string] = val;

    filled += 1;

  }

  specLookupMessage.value =

    filled > 0

      ? `${sourceLabel}에서 ${filled}개 항목을 채웠습니다 (${spec.confidence}).`

      : `${sourceLabel} 결과가 있으나 이미 입력된 값을 유지했습니다.`;

}



function onModelBlur() {

  scheduleSpecLookup(form.equipment_model);

}



onUnmounted(() => {

  if (lookupTimer) clearTimeout(lookupTimer);

});



function numOrNull(v: string | number | null | undefined): number | null {

  if (v === "" || v == null) return null;

  const n = Number(v);

  return Number.isFinite(n) ? n : null;

}



function toPayload(): ForkliftWorkPlanInput {

  return {

    ...form,

    length_mm: numOrNull(form.length_mm),

    width_mm: numOrNull(form.width_mm),

    height_mm: numOrNull(form.height_mm),

    max_lifting_kg: numOrNull(form.max_lifting_kg),

  };

}



async function onSubmit() {

  loading.value = true;

  message.value = "";

  isError.value = false;

  try {

    const result = await generateForkliftWorkPlan(toPayload());

    lastFilename.value = result.filename;

    lastSavedPath.value = result.saved_path;

    message.value = `${result.filename} 파일이 생성되었습니다.`;

    await downloadForkliftWorkPlanFile(result.filename);

  } catch (err: unknown) {

    isError.value = true;

    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;

    message.value = detail ? String(detail) : "생성에 실패했습니다. 로컬 백엔드(8001)가 실행 중인지 확인하세요.";

  } finally {

    loading.value = false;

  }

}



async function openDownload() {

  if (lastFilename.value) await downloadForkliftWorkPlanFile(lastFilename.value);

}

</script>



<style scoped>

.work-plan-page {

  max-width: 920px;

  margin: 0 auto;

}

.title {

  margin: 0 0 8px;

  font-size: 1.35rem;

}

.hint {

  color: #555;

  font-size: 0.92rem;

  line-height: 1.5;

  margin-bottom: 20px;

}

.block {

  margin-bottom: 24px;

  padding-bottom: 16px;

  border-bottom: 1px solid #e8e8e8;

}

.block-fixed {

  background: #f8fafc;

  padding: 12px 14px;

  border-radius: 8px;

  border: 1px solid #e2e8f0;

}

.block h2 {

  font-size: 1rem;

  margin: 0 0 12px;

}

.form-grid label {

  display: flex;

  flex-direction: column;

  gap: 4px;

  margin-bottom: 10px;

  font-size: 0.9rem;

}

.form-grid input {

  padding: 8px 10px;

  border: 1px solid #ccc;

  border-radius: 6px;

}

.form-grid input.prefilled {

  background: #fff;

  border-color: #94a3b8;

}

.form-grid input.example-field::placeholder {

  color: #9ca3af;

  opacity: 1;

}

.form-grid input:not(.example-field)::placeholder {

  color: #b0b8c4;

  opacity: 1;

}

.row-2 {

  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 12px;

}

.row-3 {

  display: grid;

  grid-template-columns: 1fr 1fr 1fr;

  gap: 12px;

}

.row-4 {

  display: grid;

  grid-template-columns: repeat(4, 1fr);

  gap: 10px;

}

.req {

  color: #c00;

}

.spec-hint {

  font-size: 0.85rem;

  color: #64748b;

  margin: -4px 0 10px;

}

.spec-hint.ok {

  color: #0a6640;

}

.actions {

  display: flex;

  flex-wrap: wrap;

  gap: 10px;

}

.primary {

  background: #1a5fb4;

  color: #fff;

  border: none;

  padding: 10px 18px;

  border-radius: 8px;

  cursor: pointer;

}

.secondary {

  background: #f3f3f3;

  border: 1px solid #ccc;

  padding: 10px 18px;

  border-radius: 8px;

  cursor: pointer;

}

.message {

  margin-top: 16px;

  color: #0a6640;

}

.message.error {

  color: #b00020;

}

.saved-path {

  margin-top: 8px;

  font-size: 0.85rem;

  color: #666;

  word-break: break-all;

}

@media (max-width: 720px) {

  .row-2,

  .row-3,

  .row-4 {

    grid-template-columns: 1fr;

  }

}

</style>

