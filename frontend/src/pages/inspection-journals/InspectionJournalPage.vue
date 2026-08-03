<template>
  <main class="journal-page">
    <header class="hero">
      <div>
        <p>현장 안전업무</p>
        <h1>점검·교육일지</h1>
        <span>교육 구분별 법정 내용을 자동 반영하고 사진과 결재란이 포함된 PDF를 만듭니다.</span>
      </div>
      <div class="approval-preview" aria-label="출력 결재란">
        <b>결재</b><b>담당</b><b>소장</b><b>전무</b><b>대표</b>
        <i></i><i></i><i></i><i></i><i></i>
      </div>
    </header>

    <p v-if="notice" class="notice">{{ notice }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <form class="journal-form" @submit.prevent="submitJournal">
      <section class="card">
        <h2>1. 기본정보</h2>
        <div class="grid">
          <label>현장명<input v-model="form.site_name" required maxlength="200" /></label>
          <label>점검·교육 제목<input v-model="form.subject" required maxlength="300" /></label>
          <label>점검일<input v-model="form.inspected_on" type="date" required /></label>
          <label>교육 시간<input v-model="form.time_text" placeholder="예: 07:00~09:00 (2시간)" /></label>
          <label>교육 장소<input v-model="form.location" /></label>
          <label>교육강사 성명<input v-model="form.instructor_name" /></label>
          <label>강사 소속<input v-model="form.instructor_affiliation" /></label>
          <label class="wide">참석자<textarea v-model="form.attendees" rows="3" placeholder="소속과 성명을 줄바꿈하여 입력"></textarea></label>
        </div>
      </section>

      <section class="card training-card">
        <h2>2. 교육 구분과 필수 법정 내용</h2>
        <label class="training-select">
          교육 구분
          <select v-model="form.training_code" required>
            <option value="" disabled>교육을 선택하세요</option>
            <option v-for="item in catalog" :key="item.code" :value="item.code">{{ item.label }}</option>
          </select>
        </label>
        <div v-if="selectedTraining" class="legal-content">
          <div><strong>{{ selectedTraining.label }}</strong><span>출력 필수 · 삭제할 수 없음</span></div>
          <pre>{{ selectedTraining.legal_content }}</pre>
        </div>
        <label class="additional">
          추가 교육내용
          <textarea v-model="form.additional_content" rows="6" placeholder="현장 위험요인, 작업방법, 물질명 등 추가 내용을 입력하세요."></textarea>
        </label>
        <label class="additional">
          특기사항 및 교육 효과성
          <textarea v-model="form.special_notes" rows="4" placeholder="이해도 확인, 개선사항 등을 입력하세요."></textarea>
        </label>
      </section>

      <section class="card">
        <h2>3. 점검·교육 사진</h2>
        <label class="photo-picker">
          <input type="file" accept="image/jpeg,image/png,image/webp" multiple capture="environment" @change="addPhotos" />
          <strong>사진 촬영·선택</strong>
          <span>여러 장을 선택할 수 있으며 각 사진을 크롭·회전할 수 있습니다.</span>
        </label>
        <article v-for="(photo, index) in photos" :key="photo.key" class="photo-editor-row">
          <div class="photo-row-head"><b>{{ index + 1 }}. {{ photo.file.name }}</b><button type="button" @click="removePhoto(index)">삭제</button></div>
          <ImageCropEditor
            v-model="photo.transform"
            :file="photo.file"
            :target-aspect="82 / 65"
            auto-crop
            show-caption
          />
        </article>
      </section>

      <button class="submit" :disabled="submitting || !selectedTraining">
        {{ submitting ? "저장 중…" : "점검일지 저장 및 PDF 준비" }}
      </button>
    </form>

    <section class="card records">
      <div class="records-head"><h2>저장된 점검일지</h2><button type="button" @click="load">새로고침</button></div>
      <p v-if="!journals.length" class="empty">저장된 점검일지가 없습니다.</p>
      <article v-for="journal in journals" :key="journal.id" class="record">
        <div><strong>{{ journal.inspected_on }} · {{ journal.site_name }}</strong><span>{{ journal.subject }} / {{ journal.training_label }}</span></div>
        <button type="button" @click="downloadPdf(journal)">PDF 출력</button>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "@/services/api";
import ImageCropEditor, { type ImageTransform } from "@/components/ImageCropEditor.vue";

interface TrainingItem { code: string; label: string; legal_content: string }
interface PhotoDraft { key: string; file: File; transform: ImageTransform }
interface JournalRow { id: number; site_name: string; subject: string; inspected_on: string; training_label: string }

function todayInput() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}
function emptyTransform(): ImageTransform {
  return { rotation_degrees: 0, crop_left: 0, crop_top: 0, crop_right: 0, crop_bottom: 0, caption: "" };
}

const catalog = ref<TrainingItem[]>([]);
const journals = ref<JournalRow[]>([]);
const photos = ref<PhotoDraft[]>([]);
const submitting = ref(false);
const notice = ref("");
const error = ref("");
const form = reactive({
  site_name: "",
  subject: "",
  inspected_on: todayInput(),
  time_text: "",
  location: "",
  attendees: "",
  instructor_name: "",
  instructor_affiliation: "",
  training_code: "",
  additional_content: "",
  special_notes: "",
});
const selectedTraining = computed(() => catalog.value.find((item) => item.code === form.training_code));

onMounted(load);

async function load() {
  error.value = "";
  try {
    const [catalogResponse, journalResponse] = await Promise.all([
      api.get("/inspection-journals/training-catalog"),
      api.get("/inspection-journals"),
    ]);
    catalog.value = catalogResponse.data || [];
    journals.value = journalResponse.data || [];
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "점검일지 정보를 불러오지 못했습니다.";
  }
}

function addPhotos(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files || []);
  photos.value.push(...files.map((file) => ({ key: `${file.name}-${file.lastModified}-${Math.random()}`, file, transform: emptyTransform() })));
  (event.target as HTMLInputElement).value = "";
}

function removePhoto(index: number) {
  photos.value.splice(index, 1);
}

async function submitJournal() {
  if (!selectedTraining.value) return;
  submitting.value = true;
  notice.value = "";
  error.value = "";
  try {
    const body = new FormData();
    for (const [key, value] of Object.entries(form)) body.append(key, value);
    body.append("photo_metadata", JSON.stringify(photos.value.map((photo) => photo.transform)));
    for (const photo of photos.value) body.append("photos", photo.file);
    const { data } = await api.post("/inspection-journals", body, { timeout: 120_000 });
    notice.value = "점검일지를 저장했습니다. 목록에서 결재란 포함 PDF를 출력할 수 있습니다.";
    photos.value = [];
    journals.value.unshift(data);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "점검일지를 저장하지 못했습니다.";
  } finally {
    submitting.value = false;
  }
}

async function downloadPdf(journal: JournalRow) {
  error.value = "";
  try {
    const { data } = await api.get(`/inspection-journals/${journal.id}/pdf`, { responseType: "blob", timeout: 120_000 });
    const href = URL.createObjectURL(data);
    const link = document.createElement("a");
    link.href = href;
    link.download = `${journal.inspected_on.replaceAll("-", "")}_${journal.site_name}_${journal.subject}_점검일지.pdf`;
    link.click();
    URL.revokeObjectURL(href);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || "PDF를 만들지 못했습니다.";
  }
}
</script>

<style scoped>
.journal-page { max-width: 1120px; margin: 0 auto; padding-bottom: 30px; color: #142033; }
.hero { display: flex; justify-content: space-between; gap: 24px; padding: 25px; border-radius: 20px; background: linear-gradient(135deg,#0b3b56,#0f6b6d); color: white; }
.hero p,.hero h1,.hero span { margin: 0; }
.hero p { color: #a7f3d0; font-weight: 800; }
.hero h1 { margin: 4px 0 7px; font-size: clamp(27px,4vw,38px); }
.approval-preview { display: grid; grid-template-columns: repeat(5,42px); grid-template-rows: 27px 48px; align-self: center; background: white; color: #172033; }
.approval-preview>* { display: grid; place-items: center; border: 1px solid #64748b; font-size: 11px; font-style: normal; }
.journal-form { display: grid; gap: 16px; margin-top: 18px; }
.card { padding: 20px; border: 1px solid #dce5ea; border-radius: 18px; background: white; box-shadow: 0 8px 24px rgba(31,53,71,.06); }
.card h2 { margin: 0 0 15px; font-size: 19px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }
label { display: grid; gap: 6px; color: #334155; font-size: 13px; font-weight: 800; }
.wide { grid-column: 1/-1; }
input,select,textarea { box-sizing: border-box; width: 100%; padding: 10px 11px; border: 1px solid #cbd5e1; border-radius: 10px; color: #172033; background: white; font: inherit; }
input,select { min-height: 46px; }
textarea { resize: vertical; line-height: 1.5; }
.training-select { max-width: 520px; }
.legal-content { margin-top: 14px; border: 1px solid #9cc9c4; border-radius: 12px; overflow: hidden; }
.legal-content>div { display: flex; justify-content: space-between; gap: 12px; padding: 10px 13px; background: #e9f7f4; color: #145e5e; }
.legal-content span { font-size: 12px; font-weight: 800; }
.legal-content pre { margin: 0; padding: 15px; overflow-x: auto; white-space: pre-wrap; color: #263746; font: 13px/1.6 "Malgun Gothic",sans-serif; }
.additional { margin-top: 14px; }
.photo-picker { display: grid; place-items: center; min-height: 130px; padding: 18px; border: 2px dashed #4f8790; border-radius: 14px; background: #f2fbf9; text-align: center; cursor: pointer; }
.photo-picker input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.photo-picker strong { color: #0f5c5e; font-size: 18px; }
.photo-picker span { color: #64748b; font-weight: 500; }
.photo-editor-row { margin-top: 14px; }
.photo-row-head { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.photo-row-head button,.records button { padding: 8px 11px; border: 1px solid #b8c6cf; border-radius: 9px; background: white; font-weight: 800; cursor: pointer; }
.submit { min-height: 56px; border: 0; border-radius: 13px; background: #e36b2c; color: white; font-size: 17px; font-weight: 900; cursor: pointer; }
.submit:disabled { opacity: .55; }
.notice,.error { margin: 14px 0 0; padding: 12px 15px; border-radius: 10px; font-weight: 800; }
.notice { color: #176b4b; background: #e8f7f0; }.error { color: #a43d2d; background: #fff0ed; }
.records { margin-top: 18px; }.records-head,.record { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.record { padding: 14px 0; border-top: 1px solid #e4eaee; }.record div { display: grid; gap: 4px; }.record span,.empty { color: #64748b; }
@media(max-width:760px){
  .journal-page { padding: 0 4px 24px; }.hero { flex-direction: column; padding: 20px; }.approval-preview { grid-template-columns: repeat(5,1fr); width: 100%; }
  .grid { grid-template-columns: 1fr; }.wide { grid-column: auto; }.card { padding: 16px; }.legal-content>div,.record { align-items: stretch; flex-direction: column; }
  input,select,textarea { font-size: 16px; }.submit { position: sticky; bottom: 8px; z-index: 3; }
}
</style>
