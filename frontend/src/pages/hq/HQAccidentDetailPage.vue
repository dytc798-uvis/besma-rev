<template>
  <div class="card">
    <div class="head-row">
      <div>
        <div class="card-title">사고 상세</div>
        <p class="muted">사고정보 수정, 관리구분 변경, 증빙 업로드, NAS 폴더 연결을 한 화면에서 처리합니다.</p>
      </div>
      <div class="toolbar">
        <button type="button" class="secondary" @click="openReportPreview">보고서 미리보기</button>
        <button type="button" class="secondary" @click="printReport">보고서 출력</button>
        <button type="button" class="secondary" :disabled="nasOpening" @click="openNasFolderInExplorer">
          {{ nasOpening ? "준비 중…" : "탐색기 열기" }}
        </button>
        <button type="button" class="danger" :disabled="deleting" @click="deleteCurrentAccident">
          {{ deleting ? "삭제 중…" : "삭제" }}
        </button>
        <RouterLink class="secondary-link" to="/hq-safe/accidents">목록</RouterLink>
      </div>
    </div>
    <p v-if="loading" class="muted">불러오는 중…</p>
    <template v-else-if="detail">
      <section v-if="parseWarningMessage" class="warn-box">
        <strong>파싱 검토 필요</strong>
        <p>{{ parseWarningMessage }}</p>
      </section>

      <section class="sec">
        <h3 class="sec-title">관리 정보</h3>
        <dl class="meta-dl">
          <div><dt>사고ID</dt><dd>{{ detail.accident_id }}</dd></div>
          <div><dt>관리번호</dt><dd>{{ detail.display_code }}</dd></div>
          <div><dt>사고일시</dt><dd>{{ formatAccidentMoment(detail.accident_datetime, detail.accident_datetime_text) }}</dd></div>
          <div><dt>파싱 상태</dt><dd>{{ detail.parse_status }}</dd></div>
          <div><dt>등록일시</dt><dd>{{ formatDt(detail.created_at) }}</dd></div>
        </dl>
      </section>

      <section class="sec">
        <h3 class="sec-title">사고정보 수정</h3>
        <form class="form-grid" @submit.prevent="saveDetail">
          <div class="field">
            <label>현장명</label>
            <select v-model="form.site_standard_name" class="input">
              <option v-for="site in lookups.site_names" :key="site" :value="site">{{ site }}</option>
            </select>
          </div>
          <div class="field">
            <label>보고자</label>
            <input v-model="form.reporter_name" class="input" />
          </div>
          <div class="field">
            <label>도급사</label>
            <input v-model="form.contractor_name" class="input" />
          </div>
          <div class="field">
            <label>공사팀</label>
            <input v-model="form.construction_team" class="input" />
          </div>
          <div class="field">
            <label>현장소장</label>
            <input v-model="form.site_manager_name" class="input" />
          </div>
          <div class="field">
            <label>재해자 생년월일</label>
            <input v-model="form.injured_person_birth_date" class="input" type="date" />
          </div>
          <div class="field">
            <label>상태</label>
            <select v-model="form.status" class="input">
              <option v-for="item in lookups.statuses" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div class="field">
            <label>관리구분</label>
            <select v-model="form.management_category" class="input">
              <option v-for="item in lookups.management_categories" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div class="field">
            <label>산업재해조사표 제출상황</label>
            <select v-model="form.industrial_accident_report_status" class="input">
              <option v-for="item in lookups.industrial_accident_report_statuses" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div class="field">
            <label>산업재해조사표 제출일시</label>
            <input v-model="form.industrial_accident_report_submitted_at" class="input" type="datetime-local" />
          </div>
          <div class="field">
            <label>의사소견서 상태</label>
            <select v-model="form.medical_opinion_status" class="input">
              <option v-for="item in lookups.medical_opinion_statuses" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div class="field">
            <label>의사소견서 수령일시</label>
            <input v-model="form.medical_opinion_received_at" class="input" type="datetime-local" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>의사소견 요약</label>
            <textarea v-model="form.medical_opinion_summary" class="input" rows="2" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>PC·NAS 동기화 상태</label>
            <input class="input" :value="detail.nas_sync_status" readonly />
          </div>
          <div class="field">
            <label>사고일시(원문)</label>
            <input v-model="form.accident_datetime_text" class="input" />
          </div>
          <div class="field">
            <label>성명</label>
            <input v-model="form.injured_person_name" class="input" />
          </div>
          <div class="field">
            <label>장소</label>
            <input v-model="form.accident_place" class="input" />
          </div>
          <div class="field">
            <label>작업명</label>
            <input v-model="form.work_content" class="input" />
          </div>
          <div class="field">
            <label>작업팀</label>
            <input v-model="form.work_team" class="input" />
          </div>
          <div class="field">
            <label>직종</label>
            <input v-model="form.job_name" class="input" />
          </div>
          <div class="field">
            <label>사고유형</label>
            <input v-model="form.accident_type" class="input" />
          </div>
          <div class="field">
            <label>부상정도</label>
            <input v-model="form.injury_severity" class="input" />
          </div>
          <div class="field">
            <label>휴업기간</label>
            <input v-model="form.leave_period" class="input" />
          </div>
          <div class="field">
            <label>산재 진행상태</label>
            <input v-model="form.industrial_accident_status" class="input" />
          </div>
          <div class="field">
            <label>재해부위</label>
            <input v-model="form.injured_part" class="input" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>사고경위</label>
            <textarea v-model="form.accident_circumstance" class="input" rows="3" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>사고원인</label>
            <textarea v-model="form.accident_reason" class="input" rows="3" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>상병명/진단</label>
            <input v-model="form.diagnosis_name" class="input" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>조치사항</label>
            <textarea v-model="form.action_taken" class="input" rows="3" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>비고</label>
            <textarea v-model="form.notes" class="input" rows="3" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>자동 생성 보고문(참고)</label>
            <textarea v-model="form.initial_report_template" class="input" rows="4" readonly />
          </div>
          <div class="field" style="grid-column: span 2">
            <label>NAS 폴더 경로</label>
            <div class="nas-path-row">
              <input class="input" :value="displayNasPath" readonly />
              <button type="button" class="secondary" :disabled="nasOpening" @click="openNasFolderInExplorer">
                {{ nasOpening ? "준비 중…" : "탐색기 열기" }}
              </button>
            </div>
          </div>
          <div class="actions full-row">
            <button type="submit" class="primary" :disabled="saving">{{ saving ? "저장 중…" : "저장" }}</button>
          </div>
        </form>
      </section>

      <section class="sec">
        <h3 class="sec-title">증빙 파일 업로드</h3>
        <div class="upload-row">
          <input type="file" @change="onFileChange" />
          <button type="button" class="secondary" :disabled="uploading || !uploadFile" @click="uploadAttachment">
            {{ uploading ? "업로드 중…" : "증빙 업로드" }}
          </button>
        </div>
        <ul class="attachment-list">
          <li v-for="item in detail.attachments" :key="item.id">
            <a :href="attachmentHref(item.id)" target="_blank" rel="noopener">{{ item.file_name }}</a>
          </li>
          <li v-if="detail.attachments.length === 0" class="muted">업로드된 증빙 파일이 없습니다.</li>
        </ul>
      </section>

      <section class="sec">
        <h3 class="sec-title">원문 및 자동 생성 보고문</h3>
        <div class="compare-block">
          <div>
            <label class="compare-label">원문 메시지</label>
            <pre class="pre">{{ detail.message_raw }}</pre>
          </div>
          <div v-if="output">
            <label class="compare-label">자동 생성 보고문</label>
            <p class="out-line">{{ output.composed_line }}</p>
          </div>
        </div>
      </section>
    </template>
    <p v-else-if="errorMessage" class="error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import { formatAccidentMoment } from "@/utils/accidentDateDisplay";
import { formatDateTimeKst } from "@/utils/datetime";
import { toDisplayedAccidentNasPath } from "@/utils/accidentNasPath";
import {
  downloadAccidentNasFolderLauncher,
  fetchAccidentDetail,
  fetchAccidentLookups,
  type AccidentDetail,
  type AccidentInitialReportOutput,
  type AccidentLookups,
  type AccidentUpdatePayload,
} from "@/services/accidents";
import { readLookupsCache, writeLookupsCache } from "@/utils/accidentsCache";

const route = useRoute();
const router = useRouter();
const detail = ref<AccidentDetail | null>(null);
const output = ref<AccidentInitialReportOutput | null>(null);
const lookups = reactive<AccidentLookups>({
  statuses: [],
  management_categories: [],
  site_names: [],
  industrial_accident_report_statuses: [],
  medical_opinion_statuses: [],
});
const loading = ref(true);
const saving = ref(false);
const deleting = ref(false);
const uploading = ref(false);
const nasOpening = ref(false);
const errorMessage = ref("");
const uploadFile = ref<File | null>(null);
const syncingForm = ref(false);
const form = reactive<AccidentUpdatePayload>({
  site_standard_name: "",
  reporter_name: null,
  status: "신규",
  management_category: "일반",
  accident_datetime_text: null,
  accident_datetime: null,
  accident_place: null,
  work_content: null,
  injured_person_name: null,
  injured_person_birth_date: null,
  contractor_name: null,
  construction_team: null,
  site_manager_name: null,
  work_team: null,
  job_name: null,
  accident_type: null,
  injury_severity: null,
  leave_period: null,
  industrial_accident_status: null,
  accident_circumstance: null,
  accident_reason: null,
  injured_part: null,
  diagnosis_name: null,
  action_taken: null,
  notes: null,
  initial_report_template: null,
  industrial_accident_report_status: "미정",
  industrial_accident_report_submitted_at: null,
  medical_opinion_status: "미정",
  medical_opinion_received_at: null,
  medical_opinion_summary: null,
});

const accidentId = computed(() => Number(route.params.id));
const displayNasPath = computed(() => {
  if (!detail.value) return "";
  return toDisplayedAccidentNasPath(detail.value.nas_folder_path, detail.value.accident_id);
});
const parseWarningMessage = computed(() => {
  if (!detail.value) return "";
  if (!detail.value.parse_note && detail.value.parse_status === "success") return "";
  try {
    const note = detail.value.parse_note ? JSON.parse(detail.value.parse_note) : {};
    if (note.manual_supplemented) {
      return `자동 파싱은 ${detail.value.parse_status} 상태였고 HQ가 수동보완했습니다. 상세 값을 다시 확인하세요.`;
    }
    const missing = Array.isArray(note.missing_required_fields) ? note.missing_required_fields : [];
    if (missing.length > 0) {
      return `자동 파싱 핵심 필드가 누락되었습니다: ${missing.join(", ")}`;
    }
  } catch {
    // ignore malformed parse_note and fall back to parse_status messaging
  }
  if (detail.value.parse_status !== "success") {
    return "자동 파싱 결과가 불완전합니다. 상세 값을 확인 후 저장하세요.";
  }
  return "";
});

function formatDt(value: string) {
  return formatDateTimeKst(value, value);
}

function syncForm() {
  if (!detail.value) return;
  syncingForm.value = true;
  form.site_standard_name = detail.value.site_standard_name || detail.value.site_name || "";
  form.reporter_name = detail.value.reporter_name;
  form.status = detail.value.status;
  form.management_category = detail.value.management_category;
  form.accident_datetime_text = detail.value.accident_datetime_text;
  form.accident_datetime = detail.value.accident_datetime;
  form.accident_place = detail.value.accident_place;
  form.work_content = detail.value.work_content;
  form.injured_person_name = detail.value.injured_person_name;
  form.injured_person_birth_date = detail.value.injured_person_birth_date;
  form.contractor_name = detail.value.contractor_name;
  form.construction_team = detail.value.construction_team;
  form.site_manager_name = detail.value.site_manager_name;
  form.work_team = detail.value.work_team;
  form.job_name = detail.value.job_name;
  form.accident_type = detail.value.accident_type;
  form.injury_severity = detail.value.injury_severity;
  form.leave_period = detail.value.leave_period;
  form.industrial_accident_status = detail.value.industrial_accident_status;
  form.accident_circumstance = detail.value.accident_circumstance;
  form.accident_reason = detail.value.accident_reason;
  form.injured_part = detail.value.injured_part;
  form.diagnosis_name = detail.value.diagnosis_name;
  form.action_taken = detail.value.action_taken;
  form.notes = detail.value.notes;
  form.initial_report_template =
    detail.value.initial_report_template || detail.value.composed_line || output.value?.composed_line || null;
  form.industrial_accident_report_status = detail.value.industrial_accident_report_status;
  form.industrial_accident_report_submitted_at = detail.value.industrial_accident_report_submitted_at;
  form.medical_opinion_status = detail.value.medical_opinion_status;
  form.medical_opinion_received_at = detail.value.medical_opinion_received_at;
  form.medical_opinion_summary = detail.value.medical_opinion_summary;
  syncingForm.value = false;
}

function applyDetailOutput(detailRes: AccidentDetail) {
  if (!detailRes.composed_line) {
    output.value = null;
    return;
  }
  output.value = {
    accident_id: detailRes.id,
    accident_code: detailRes.accident_id,
    display_code: detailRes.display_code,
    parse_status: detailRes.parse_status,
    composed_line: detailRes.composed_line,
    fields: detailRes.output_fields ?? {},
    message_raw: detailRes.message_raw,
  };
}

function applyLookups(lookupsRes: AccidentLookups, detailRes?: AccidentDetail | null) {
  lookups.statuses = lookupsRes.statuses;
  lookups.management_categories = lookupsRes.management_categories;
  lookups.site_names = [...lookupsRes.site_names];
  lookups.industrial_accident_report_statuses = lookupsRes.industrial_accident_report_statuses ?? [];
  lookups.medical_opinion_statuses = lookupsRes.medical_opinion_statuses ?? [];
  if (detailRes?.site_standard_name && !lookups.site_names.includes(detailRes.site_standard_name)) {
    lookups.site_names.unshift(detailRes.site_standard_name);
  }
  writeLookupsCache(lookupsRes);
}

async function loadAll() {
  errorMessage.value = "";
  const id = accidentId.value;
  if (!Number.isFinite(id) || id <= 0) {
    errorMessage.value = "잘못된 사고 ID입니다.";
    loading.value = false;
    return;
  }

  const cachedLookups = readLookupsCache<AccidentLookups>();
  if (cachedLookups) {
    applyLookups(cachedLookups);
  }

  loading.value = true;
  try {
    const detailPromise = fetchAccidentDetail(id);
    const lookupsPromise = cachedLookups ? Promise.resolve(cachedLookups) : fetchAccidentLookups();
    const [lookupsRes, detailRes] = await Promise.all([lookupsPromise, detailPromise]);
    detail.value = detailRes;
    applyLookups(lookupsRes, detailRes);
    applyDetailOutput(detailRes);
    syncForm();
  } catch {
    errorMessage.value = "사고 정보를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

async function saveDetail() {
  if (!detail.value) return;
  saving.value = true;
  try {
    await api.put(`/accidents/${detail.value.id}`, form);
    await loadAll();
  } catch {
    window.alert("상세 저장에 실패했습니다.");
  } finally {
    saving.value = false;
  }
}

async function deleteCurrentAccident() {
  if (!detail.value) return;
  const ok = window.confirm("이 사고 데이터를 삭제하시겠습니까?\n첨부와 사고 폴더도 함께 정리됩니다.");
  if (!ok) return;

  deleting.value = true;
  try {
    await api.delete(`/accidents/${detail.value.id}`);
    window.alert("삭제되었습니다.");
    await router.push({ name: "hq-safe-accidents", query: { bypassWorklist: "1" } });
  } catch {
    window.alert("삭제에 실패했습니다.");
  } finally {
    deleting.value = false;
  }
}

function onFileChange(event: Event) {
  uploadFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

async function uploadAttachment() {
  if (!detail.value || !uploadFile.value) return;
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", uploadFile.value);
    await api.post(`/accidents/${detail.value.id}/attachments`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    uploadFile.value = null;
    await loadAll();
  } catch {
    window.alert("증빙 업로드에 실패했습니다.");
  } finally {
    uploading.value = false;
  }
}

function attachmentHref(id: number) {
  return `${api.defaults.baseURL}/accidents/attachments/${id}`;
}

async function openNasFolderInExplorer() {
  if (!detail.value) {
    window.alert("연결된 NAS 경로가 없습니다.");
    return;
  }
  if (!displayNasPath.value?.trim()) {
    window.alert("연결된 NAS 경로가 없습니다.");
    return;
  }
  nasOpening.value = true;
  try {
    await downloadAccidentNasFolderLauncher(detail.value.id);
    await loadAll();
    window.alert(
      "탐색기를 여는 실행 파일을 내려받았습니다.\n\n다운로드한 .bat 파일을 더블클릭하세요.\n폴더가 없으면 먼저 만들고 탐색기가 열립니다.\n(서버에도 동일 폴더가 준비됩니다.)",
    );
  } catch {
    window.alert("탐색기 열기 파일을 받지 못했습니다. NAS 연결과 권한을 확인해 주세요.");
  } finally {
    nasOpening.value = false;
  }
}

function openReportPreview() {
  if (!detail.value) return;
  void router.push({ name: "hq-safe-accident-report", params: { id: String(detail.value.id) } });
}

function printReport() {
  if (!detail.value) return;
  const href = router.resolve({
    name: "hq-safe-accident-report",
    params: { id: String(detail.value.id) },
    query: { autoPrint: "1" },
  }).href;
  window.open(href, "_blank", "noopener");
}

onMounted(() => {
  void loadAll();
});

watch(
  () => route.params.id,
  () => {
    void loadAll();
  },
);
</script>

<style scoped>
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}
.toolbar {
  display: flex;
  gap: 8px;
}
.danger {
  padding: 6px 10px;
  border: 1px solid #dc2626;
  color: #dc2626;
  background: #fff;
  border-radius: 6px;
  font-size: 14px;
  white-space: nowrap;
}
.secondary-link {
  color: #334155;
  text-decoration: none;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
  white-space: nowrap;
}
.muted {
  color: #64748b;
}
.warn-box {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #f59e0b;
  background: #fffbeb;
  border-radius: 8px;
  color: #92400e;
}
.warn-box p {
  margin: 6px 0 0;
}
.sec {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}
.sec-title {
  font-size: 15px;
  margin: 0 0 8px;
}
.meta-dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}
.meta-dl div {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 8px;
}
.meta-dl dt {
  color: #64748b;
  font-weight: 600;
}
.meta-dl dd {
  margin: 0;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 13px;
  font-weight: 600;
}
.input {
  width: 100%;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
}
.nas-path-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.actions {
  display: flex;
  justify-content: flex-end;
}
.full-row {
  grid-column: span 2;
}
.upload-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.attachment-list {
  margin: 12px 0 0;
  padding-left: 18px;
}
.compare-block {
  display: grid;
  gap: 12px;
}
.manual-checklist {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
  margin-bottom: 12px;
}
.manual-check-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.manual-check-item input {
  width: 16px;
  height: 16px;
}
.compare-label {
  display: inline-block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.pre {
  white-space: pre-wrap;
  word-break: break-word;
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid #e2e8f0;
}
.out-line {
  font-size: 15px;
  line-height: 1.6;
  padding: 12px;
  background: #eff6ff;
  border-radius: 6px;
  border: 1px solid #bfdbfe;
  margin-top: 12px;
}
.error {
  color: #b91c1c;
  font-weight: 600;
}
</style>
