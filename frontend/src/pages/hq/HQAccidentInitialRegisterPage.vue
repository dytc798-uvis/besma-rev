<template>
  <div class="card">
    <div class="card-title">사고 등록</div>
    <p class="muted">자동 파싱은 보조 기능입니다. 양식 미준수 보고도 HQ가 직접 보정해 저장할 수 있습니다.</p>

    <div class="mode-toggle">
      <button type="button" class="toggle-btn" :class="{ active: inputMode === 'auto' }" @click="setMode('auto')">자동입력</button>
      <button type="button" class="toggle-btn" :class="{ active: inputMode === 'manual' }" @click="setMode('manual')">수동입력</button>
    </div>

    <form class="form-stack" @submit.prevent="submit">
      <template v-if="inputMode === 'auto'">
        <div class="form-grid">
          <div class="field">
            <label class="lbl">템플릿</label>
            <select v-model="selectedTemplate" class="input">
              <option v-for="item in templates" :key="item.name" :value="item.name">{{ item.name }}</option>
            </select>
          </div>
          <div class="field">
            <label class="lbl">템플릿 예시</label>
            <input class="input" :value="currentTemplate.sample" readonly />
          </div>
        </div>
        <div class="template-actions">
          <button type="button" class="secondary" @click="applyTemplate">템플릿 넣기</button>
          <button type="button" class="secondary" @click="clearMessage">입력창 비우기</button>
          <button type="button" class="secondary" @click="switchAutoToManual">직접 입력하기</button>
        </div>
        <label class="lbl" for="msg">최초보고 메시지</label>
        <textarea
          id="msg"
          v-model="messageRaw"
          class="ta"
          rows="12"
          :placeholder="messagePlaceholder"
          required
        />
        <p class="template-notice">※ 사고최초보고 템플릿 형식이 아닌 경우 자동 등록되지 않으며, 수동 보완이 필요합니다.</p>
        <section v-if="autoPreview" class="preview-box" :class="previewClass">
          <strong>{{ previewTitle }}</strong>
          <p>{{ previewDescription }}</p>
          <p v-if="missingFieldLabels.length > 0" class="missing-line">누락 필드: {{ missingFieldLabels.join(", ") }}</p>
          <p v-if="autoPreview.composed_line" class="preview-line">{{ autoPreview.composed_line }}</p>
          <div v-if="autoPreview.parse_status === 'failed'" class="preview-actions">
            <button type="button" class="secondary" @click="switchFailedPreviewToManual">수동입력으로 전환</button>
          </div>
        </section>
      </template>

      <section v-if="showEditableForm" class="editor-section">
        <div class="section-title">{{ inputMode === "manual" ? "수동 입력" : "파싱 결과 보완" }}</div>
        <p v-if="inputMode === 'auto' && autoPreview?.parse_status === 'partial'" class="section-help">
          partial 상태는 유지되며, 보완 후 저장하면 `parse_note`에 수동보완 흔적이 남습니다.
        </p>
        <p v-else-if="inputMode === 'manual' && autoPreview?.parse_status === 'failed'" class="section-help">
          자동 파싱 실패 원문을 유지한 채 수동 입력으로 저장할 수 있습니다.
        </p>

        <div class="form-grid">
          <div class="field">
            <label class="lbl">현장명</label>
            <select v-model="manualForm.site_standard_name" class="input" :class="fieldClass('site_standard_name')" required>
              <option value="">선택하세요</option>
              <option v-for="site in lookups.site_names" :key="site" :value="site">{{ site }}</option>
            </select>
            <small v-if="fieldMissing('site_standard_name')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field">
            <label class="lbl">보고자</label>
            <input v-model="manualForm.reporter_name" class="input" :class="fieldClass('reporter_name')" required />
            <small v-if="fieldMissing('reporter_name')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field">
            <label class="lbl">사고일시</label>
            <input v-model="manualForm.accident_datetime" class="input" :class="fieldClass('accident_datetime')" type="datetime-local" required />
            <small v-if="fieldMissing('accident_datetime')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field">
            <label class="lbl">사고시각(원문)</label>
            <input v-model="manualForm.accident_datetime_text" class="input" :class="fieldClass('accident_datetime')" placeholder="예: 금일 오후 2시 10분" />
          </div>
          <div class="field">
            <label class="lbl">사고장소</label>
            <input v-model="manualForm.accident_place" class="input" :class="fieldClass('accident_place')" required />
            <small v-if="fieldMissing('accident_place')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field">
            <label class="lbl">작업내용</label>
            <input v-model="manualForm.work_content" class="input" :class="fieldClass('work_content')" required />
            <small v-if="fieldMissing('work_content')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field">
            <label class="lbl">재해자</label>
            <input v-model="manualForm.injured_person_name" class="input" :class="fieldClass('injured_person_name')" />
            <small v-if="fieldMissing('injured_person_name')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field">
            <label class="lbl">사고경위</label>
            <input v-model="manualForm.accident_circumstance" class="input" :class="fieldClass('accident_circumstance')" />
            <small v-if="fieldMissing('accident_circumstance')" class="missing-help">누락 필드입니다.</small>
          </div>
          <div class="field" style="grid-column: span 2">
            <label class="lbl">사고원인</label>
            <textarea v-model="manualForm.accident_reason" class="ta compact" :class="fieldClass('accident_reason')" rows="2" />
            <small v-if="fieldMissing('accident_reason')" class="missing-help">사고원인 또는 상해부위 중 하나는 입력되어야 합니다.</small>
          </div>
          <div class="field">
            <label class="lbl">상해부위</label>
            <input v-model="manualForm.injured_part" class="input" :class="fieldClass('injured_part')" />
            <small v-if="fieldMissing('injured_part')" class="missing-help">사고원인 또는 상해부위 중 하나는 입력되어야 합니다.</small>
          </div>
          <div class="field">
            <label class="lbl">상병명/진단</label>
            <input v-model="manualForm.diagnosis_name" class="input" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label class="lbl">조치사항</label>
            <textarea v-model="manualForm.action_taken" class="ta compact" rows="2" />
          </div>
          <div class="field">
            <label class="lbl">상태</label>
            <select v-model="manualForm.status" class="input">
              <option v-for="item in lookups.statuses" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div class="field">
            <label class="lbl">관리구분</label>
            <select v-model="manualForm.management_category" class="input">
              <option v-for="item in lookups.management_categories" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div class="field" style="grid-column: span 2">
            <label class="lbl">비고</label>
            <textarea v-model="manualForm.notes" class="ta compact" rows="3" />
          </div>
          <div class="field" style="grid-column: span 2">
            <label class="lbl">원문 메모</label>
            <textarea
              v-model="manualForm.message_raw"
              class="ta"
              rows="4"
              placeholder="원문이 없으면 자동 문안으로 생성됩니다."
            />
          </div>
        </div>
      </section>

      <div class="actions">
        <RouterLink class="secondary-link" to="/hq-safe/accidents">목록</RouterLink>
        <button
          v-if="inputMode === 'auto' && !autoPreview"
          type="submit"
          class="primary"
          :disabled="submitting"
        >
          {{ submitting ? "처리 중…" : "파싱 미리보기" }}
        </button>
        <button
          v-else
          type="submit"
          class="primary"
          :disabled="submitting"
        >
          {{ submitting ? "처리 중…" : saveButtonLabel }}
        </button>
      </div>
    </form>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api } from "@/services/api";
import {
  fetchAccidentLookups,
  fetchAccidentParsePreview,
  type AccidentCreatePayload,
  type AccidentLookups,
  type AccidentParsePreviewResponse,
} from "@/services/accidents";

const router = useRouter();
const inputMode = ref<"auto" | "manual">("auto");
const messageRaw = ref("");
const submitting = ref(false);
const errorMessage = ref("");
const autoPreview = ref<AccidentParsePreviewResponse | null>(null);
const lookups = reactive<AccidentLookups>({
  statuses: [],
  management_categories: [],
  site_names: [],
});
const templates = [
  {
    name: "사고최초보고 템플릿",
    sample: "[사고최초보고] 형식 강제 템플릿",
    body: `[사고최초보고]
현  장  명:
보  고  자:
사고시각:
사고장소:
작업내용:
재  해  자:
사고경위:
사고원인:
상해부위:
조치사항:
위와 같이 보고드립니다.`,
  },
];
const selectedTemplate = ref(templates[0].name);
const currentTemplate = computed(() => templates.find((item) => item.name === selectedTemplate.value) ?? templates[0]);
const messagePlaceholder = computed(
  () => `현장 보고 원문을 그대로 붙여넣으세요.\n\n템플릿이 필요하면 '템플릿 넣기'를 누르세요.\n\n${currentTemplate.value.body}`,
);

function createManualForm(): AccidentCreatePayload {
  return {
    input_mode: "manual",
    message_raw: null,
    site_standard_name: "",
    reporter_name: "",
    status: "신규",
    management_category: "일반",
    accident_datetime_text: null,
    accident_datetime: null,
    accident_place: null,
    work_content: null,
    injured_person_name: null,
    accident_circumstance: null,
    accident_reason: null,
    injured_part: null,
    diagnosis_name: null,
    action_taken: null,
    notes: null,
    initial_report_template: null,
    parse_status_override: null,
    parse_note_override: null,
  };
}

const manualForm = reactive<AccidentCreatePayload>(createManualForm());

const previewNote = computed<Record<string, unknown>>(() => {
  if (!autoPreview.value?.parse_note) return {};
  try {
    return JSON.parse(autoPreview.value.parse_note) as Record<string, unknown>;
  } catch {
    return {};
  }
});

const missingFieldLabels = computed(() => {
  const values = previewNote.value.missing_required_fields;
  return Array.isArray(values) ? values.map((item) => String(item)) : [];
});

const previewTitle = computed(() => {
  if (autoPreview.value?.parse_status === "failed") return "자동 파싱 실패";
  if (autoPreview.value?.parse_status === "partial") return "자동 파싱 partial";
  return "자동 파싱 success";
});

const previewDescription = computed(() => {
  if (autoPreview.value?.parse_status === "failed") {
    return "양식 미준수 보고로 판단되어 자동 파싱이 실패했습니다. 수동입력으로 전환해 계속 저장할 수 있습니다.";
  }
  if (autoPreview.value?.parse_status === "partial") {
    return "파싱된 값은 채워 두었습니다. 누락 필드를 보완한 뒤 저장하세요.";
  }
  return "자동 파싱 결과를 검토하고 필요하면 수정한 뒤 저장하세요.";
});

const previewClass = computed(() => {
  if (autoPreview.value?.parse_status === "failed") return "is-failed";
  if (autoPreview.value?.parse_status === "partial") return "is-partial";
  return "is-success";
});

const showEditableForm = computed(
  () => inputMode.value === "manual" || (autoPreview.value != null && autoPreview.value.parse_status !== "failed"),
);
const saveButtonLabel = computed(() => {
  if (inputMode.value === "auto") {
    return autoPreview.value?.parse_status === "partial" ? "보완 후 저장" : "검토 후 저장";
  }
  return "수동 입력 저장";
});

function setMode(next: "auto" | "manual") {
  inputMode.value = next;
  errorMessage.value = "";
  if (next === "manual") {
    manualForm.message_raw = manualForm.message_raw || messageRaw.value || null;
  }
}

function applyTemplate() {
  messageRaw.value = currentTemplate.value.body;
}

function clearMessage() {
  messageRaw.value = "";
}

function resetManualForm() {
  Object.assign(manualForm, createManualForm());
}

function normalizeText(value: unknown) {
  const text = String(value ?? "").trim();
  return text || null;
}

function toDatetimeLocal(value: unknown) {
  if (!value) return null;
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return null;
  const yyyy = date.getFullYear();
  const mm = `${date.getMonth() + 1}`.padStart(2, "0");
  const dd = `${date.getDate()}`.padStart(2, "0");
  const hh = `${date.getHours()}`.padStart(2, "0");
  const mi = `${date.getMinutes()}`.padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
}

function fillManualForm(fields: Record<string, unknown>, sourceMessage: string) {
  manualForm.site_standard_name = normalizeText(fields.site_name) ?? "";
  manualForm.reporter_name = normalizeText(fields.reporter_name);
  manualForm.accident_datetime_text = normalizeText(fields.accident_datetime_text);
  manualForm.accident_datetime = toDatetimeLocal(fields.accident_datetime);
  manualForm.accident_place = normalizeText(fields.accident_place);
  manualForm.work_content = normalizeText(fields.work_content);
  manualForm.injured_person_name = normalizeText(fields.injured_person_name);
  manualForm.accident_circumstance = normalizeText(fields.accident_circumstance);
  manualForm.accident_reason = normalizeText(fields.accident_reason);
  manualForm.injured_part = normalizeText(fields.injured_part);
  manualForm.diagnosis_name = normalizeText(fields.diagnosis_name);
  manualForm.action_taken = normalizeText(fields.action_taken);
  manualForm.message_raw = sourceMessage || manualForm.message_raw;
}

function validateManualInput() {
  const required = [
    ["현장명", manualForm.site_standard_name],
    ["보고자", manualForm.reporter_name],
    ["사고일시", manualForm.accident_datetime || manualForm.accident_datetime_text],
    ["사고장소", manualForm.accident_place],
    ["작업내용", manualForm.work_content],
  ];
  const missing = required.filter(([, value]) => !value).map(([label]) => label);
  if (missing.length > 0) {
    errorMessage.value = `수동입력 필수값 누락: ${missing.join(", ")}`;
    return false;
  }
  return true;
}

function fieldMissing(key: string) {
  if (autoPreview.value?.parse_status !== "partial") return false;
  const groups: Record<string, boolean> = {
    site_standard_name: !manualForm.site_standard_name,
    reporter_name: !manualForm.reporter_name,
    accident_datetime: !manualForm.accident_datetime && !manualForm.accident_datetime_text,
    accident_place: !manualForm.accident_place,
    work_content: !manualForm.work_content,
    injured_person_name: !manualForm.injured_person_name,
    accident_circumstance: !manualForm.accident_circumstance,
    accident_reason: !manualForm.accident_reason && !manualForm.injured_part,
    injured_part: !manualForm.accident_reason && !manualForm.injured_part,
  };
  const labelMap: Record<string, string> = {
    site_standard_name: "현장명",
    reporter_name: "보고자",
    accident_datetime: "사고시각",
    accident_place: "사고장소",
    work_content: "작업내용",
    injured_person_name: "재해자",
    accident_circumstance: "사고경위",
    accident_reason: "사고원인 또는 상해부위",
    injured_part: "사고원인 또는 상해부위",
  };
  return missingFieldLabels.value.includes(labelMap[key]) && groups[key];
}

function fieldClass(key: string) {
  return fieldMissing(key) ? "input-missing" : "";
}

function switchFailedPreviewToManual() {
  setMode("manual");
  manualForm.message_raw = messageRaw.value || manualForm.message_raw;
}

function switchAutoToManual() {
  setMode("manual");
  manualForm.message_raw = messageRaw.value || manualForm.message_raw;
}

async function loadLookups() {
  try {
    const data = await fetchAccidentLookups();
    lookups.statuses = data.statuses;
    lookups.management_categories = data.management_categories;
    lookups.site_names = data.site_names;
  } catch {
    errorMessage.value = "등록 화면 초기값을 불러오지 못했습니다.";
  }
}

async function runPreview() {
  if (!messageRaw.value.trim()) {
    errorMessage.value = "최초보고 메시지를 입력하세요.";
    return;
  }
  const preview = await fetchAccidentParsePreview({ message_raw: messageRaw.value });
  autoPreview.value = preview;
  fillManualForm(preview.fields, preview.message_raw);
  manualForm.initial_report_template = preview.composed_line || null;
  if (preview.parse_status === "failed") {
    manualForm.message_raw = preview.message_raw;
  }
}

function buildCreatePayload(): AccidentCreatePayload {
  const useAutoAssist = !!autoPreview.value && !!messageRaw.value.trim();
  return {
    ...manualForm,
    input_mode: "manual",
    template_name: inputMode.value === "auto" ? selectedTemplate.value : null,
    message_raw: manualForm.message_raw || messageRaw.value || null,
    parse_status_override: useAutoAssist ? autoPreview.value?.parse_status ?? null : null,
    parse_note_override: useAutoAssist ? autoPreview.value?.parse_note ?? null : null,
  };
}

async function submit() {
  errorMessage.value = "";
  if (inputMode.value === "auto" && !autoPreview.value) {
    submitting.value = true;
    try {
      await runPreview();
    } catch {
      errorMessage.value = "자동 파싱 미리보기에 실패했습니다.";
    } finally {
      submitting.value = false;
    }
    return;
  }

  if (!validateManualInput()) return;

  submitting.value = true;
  try {
    const res = await api.post<{ id: number }>("/accidents/initial-report/parse-and-create", buildCreatePayload());
    const id = res.data?.id;
    if (id == null) throw new Error("no id");
    await router.push({ name: "hq-safe-accident-detail", params: { id: String(id) } });
  } catch {
    errorMessage.value = "등록에 실패했습니다. 입력 원문과 필수값을 확인하세요.";
  } finally {
    submitting.value = false;
  }
}

watch(messageRaw, () => {
  if (inputMode.value !== "auto") return;
  autoPreview.value = null;
  resetManualForm();
});

onMounted(() => {
  void loadLookups();
});
</script>

<style scoped>
.muted {
  color: #64748b;
  font-size: 13px;
  margin: 8px 0 12px;
}
.mode-toggle {
  display: inline-flex;
  gap: 8px;
  margin-bottom: 14px;
}
.toggle-btn {
  padding: 6px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
}
.toggle-btn.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.form-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
.lbl {
  font-weight: 600;
  font-size: 14px;
}
.input,
.ta {
  width: 100%;
  font-family: inherit;
  font-size: 14px;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
}
.ta {
  resize: vertical;
}
.ta.compact {
  min-height: 72px;
}
.template-notice {
  margin: -4px 0 0;
  color: #92400e;
  font-size: 13px;
}
.template-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: -2px;
}
.preview-box {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
}
.preview-box p {
  margin: 6px 0 0;
}
.preview-box.is-success {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}
.preview-box.is-partial {
  background: #fffbeb;
  border-color: #f59e0b;
  color: #92400e;
}
.preview-box.is-failed {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}
.preview-line {
  white-space: pre-wrap;
  word-break: break-word;
}
.preview-actions {
  margin-top: 10px;
}
.editor-section {
  border-top: 1px solid #e2e8f0;
  padding-top: 12px;
}
.section-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.section-help {
  margin: 0 0 10px;
  color: #64748b;
  font-size: 13px;
}
.missing-line,
.missing-help {
  font-size: 12px;
  color: #b45309;
}
.input-missing {
  border-color: #f59e0b;
  background: #fffbeb;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  align-items: center;
  margin-top: 8px;
}
.secondary-link {
  color: #334155;
  text-decoration: none;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
}
.error {
  margin-top: 12px;
  color: #b91c1c;
  font-weight: 600;
}
</style>
