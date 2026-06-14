<template>
  <div class="hq-worker-actions">
    <button class="link-btn" type="button" @click="openHistory">이력</button>
    <button
      v-if="canSanction"
      class="link-btn"
      type="button"
      @click="openSanction"
    >
      제재
    </button>
    <button
      v-if="!periodClosed"
      class="link-btn"
      type="button"
      @click="openOverride('FUNCTIONAL')"
    >
      2-1 수정
    </button>
    <button
      v-if="!periodClosed"
      class="link-btn"
      type="button"
      @click="openOverride('SAFETY')"
    >
      2-2 수정
    </button>

    <Teleport to="body">
      <div v-if="dialogOpen" class="hq-fe-overlay" @click.self="closeAll">
        <section
          v-if="dialogMode === 'sanction'"
          class="hq-fe-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="hq-dialog-title"
          @click.stop
        >
          <div class="dialog-head">
            <h2 id="hq-dialog-title">{{ workerName }} — 제재 등록</h2>
            <button class="dialog-close" type="button" aria-label="닫기" @click="closeAll">✕</button>
          </div>
          <FeSanctionRegisterForm
            :worker-id="workerId"
            :worker-name="workerName"
            :grouped-violations="groupedViolations"
            :default-violation-code="sanctionForm.violation_code"
            :disabled="!canSanction"
            @saved="onSanctionSaved"
            @cancel="closeAll"
          />
          <p v-if="error" class="error">{{ error }}</p>
        </section>

        <section
          v-else-if="dialogMode === 'override'"
          class="hq-fe-dialog hq-fe-dialog--wide"
          role="dialog"
          aria-modal="true"
          @click.stop
        >
          <div class="dialog-head">
            <h2>{{ workerName }} — {{ overrideEvalType === "SAFETY" ? "2-2 안전·제재" : "2-1 기능" }} 점수 수정</h2>
            <button class="dialog-close" type="button" aria-label="닫기" @click="closeAll">✕</button>
          </div>
          <p v-if="loadingOverride" class="muted">불러오는 중…</p>
          <template v-else>
            <div v-for="c in overrideCriteria" :key="c.id" class="criteria-row">
              <div class="criteria-title">{{ c.title }}</div>
              <div class="grade-chips">
                <button
                  v-for="g in c.grades"
                  :key="g.key"
                  type="button"
                  class="grade-chip"
                  :class="{ selected: overrideScores[c.id] === g.key }"
                  @click="overrideScores[c.id] = g.key"
                >
                  {{ g.label }} ({{ g.points }})
                </button>
              </div>
            </div>
            <label class="field">
              <span class="field-label">수정 사유 <span class="req">*</span></span>
              <textarea v-model="overrideReason" class="field-control" rows="3" placeholder="점수 수정 사유" />
            </label>
            <div class="actions">
              <button class="stitch-btn-secondary" type="button" @click="closeAll">취소</button>
              <button
                class="stitch-btn-primary"
                type="button"
                :disabled="saving || !overrideReason.trim() || !overrideComplete"
                @click="submitOverride"
              >
                {{ saving ? "저장 중…" : "저장" }}
              </button>
            </div>
          </template>
          <p v-if="error" class="error">{{ error }}</p>
        </section>

        <section
          v-else-if="dialogMode === 'history'"
          class="hq-fe-dialog hq-fe-dialog--history"
          role="dialog"
          aria-modal="true"
          @click.stop
        >
          <div class="dialog-head">
            <h2>{{ workerName }} — 평가·제재 이력</h2>
            <button class="dialog-close" type="button" aria-label="닫기" @click="closeAll">✕</button>
          </div>
          <div class="hq-fe-dialog-body">
            <p v-if="loadingHistory" class="muted">불러오는 중…</p>
            <div v-else-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</div>
            <div v-else class="history-sections">
              <section class="history-block">
                <h3>제재 이력</h3>
                <ul class="history-list">
                  <li v-for="s in allSanctions" :key="`s-${s.id}`">
                    <div class="history-item-main">
                      {{ s.violation_label }} →
                      <span :class="sanctionOutcomeClass(s)">{{ sanctionHistoryLabel(s) }}</span>
                      <span v-if="s.penalty_points" class="meta"> · -{{ s.penalty_points }}점</span>
                    </div>
                    <div class="history-item-meta">
                      <span class="meta">{{ formatDateTimeKst(s.created_at, "—") }}</span>
                      <span v-if="s.reported_by_name" class="meta"> · {{ s.reported_by_name }}</span>
                      <span v-if="s.evidence_type_label" class="meta"> · {{ s.evidence_type_label }}</span>
                      <button v-if="s.evidence_photo_url" class="link-btn" type="button" @click="previewSanctionEvidence(s.id)">
                        근거 사진
                      </button>
                    </div>
                    <p v-if="s.note" class="meta note">{{ s.note }}</p>
                  </li>
                  <li v-if="!allSanctions.length" class="muted">제재 이력 없음</li>
                </ul>
              </section>
              <section v-if="historyData?.assessment_revisions?.length" class="history-block">
                <h3>점수 수정 이력</h3>
                <ul class="history-list">
                  <li v-for="r in historyData.assessment_revisions" :key="`r-${r.id}`">
                    <div class="history-item-main">
                      {{ r.eval_type === "SAFETY" ? "2-2 안전" : "2-1 기능" }}
                      {{ r.before_grade_code || "—" }} → {{ r.after_grade_code }}
                    </div>
                    <div class="history-item-meta">
                      <span class="meta">{{ formatDateTimeKst(r.created_at, "—") }}</span>
                      <span v-if="r.edited_by_name" class="meta"> · {{ r.edited_by_name }}</span>
                    </div>
                    <p v-if="r.reason" class="meta note">{{ r.reason }}</p>
                  </li>
                </ul>
              </section>
            </div>
            <p v-if="historyError" class="error">{{ historyError }}</p>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { api } from "@/services/api";
import FeSanctionRegisterForm from "@/components/functional-eval/FeSanctionRegisterForm.vue";
import { formatDateTimeKst } from "@/utils/datetime";

interface ViolationItem {
  code: string;
  category: string;
  category_label: string;
  label: string;
}

interface CriterionGrade {
  key: string;
  label: string;
  points: number;
}

interface Criterion {
  id: string;
  title: string;
  grades: CriterionGrade[];
}

interface SanctionRow {
  id: number;
  violation_label: string;
  sanction_result_label: string;
  institutional_sanction_label?: string;
  outcome_label?: string;
  sanction_display_label?: string;
  is_hiring_ban?: boolean;
  strike_number: number;
  note?: string | null;
  reported_by_name?: string | null;
  penalty_points?: number;
  evidence_type_label?: string;
  evidence_photo_url?: string | null;
  created_at: string;
  from_prior_period?: boolean;
}

interface RevisionRow {
  id: number;
  eval_type: string;
  before_grade_code?: string | null;
  after_grade_code: string;
  reason: string;
  edited_by_name?: string | null;
  created_at: string;
}

const props = defineProps<{
  workerId: number;
  workerName: string;
  periodClosed?: boolean;
  isPermanentlyExpelled?: boolean;
}>();

const emit = defineEmits<{ saved: [] }>();

type DialogMode = "sanction" | "override" | "history" | null;
type EvalType = "FUNCTIONAL" | "SAFETY";

const dialogOpen = ref(false);
const dialogMode = ref<DialogMode>(null);
const saving = ref(false);
const error = ref("");
const violations = ref<ViolationItem[]>([]);
const evalCatalog = ref<{ FUNCTIONAL: { criteria: Criterion[] }; SAFETY: { criteria: Criterion[] } } | null>(null);

const sanctionForm = reactive({ violation_code: "", note: "" });
const overrideEvalType = ref<EvalType>("FUNCTIONAL");
const overrideScores = ref<Record<string, string>>({});
const overrideReason = ref("");
const loadingOverride = ref(false);

const loadingHistory = ref(false);
const historyError = ref("");
const historyData = ref<{
  history_visible: boolean;
  message?: string;
  sanctions: SanctionRow[];
  prior_sanctions: SanctionRow[];
  assessment_revisions?: RevisionRow[];
} | null>(null);

const canSanction = computed(() => !props.periodClosed && !props.isPermanentlyExpelled);

const groupedViolations = computed(() => {
  const map = new Map<string, { category: string; label: string; items: ViolationItem[] }>();
  for (const item of violations.value) {
    if (!map.has(item.category)) {
      map.set(item.category, { category: item.category, label: item.category_label, items: [] });
    }
    map.get(item.category)!.items.push(item);
  }
  return Array.from(map.values());
});

const overrideCriteria = computed(() => {
  if (!evalCatalog.value) return [];
  return overrideEvalType.value === "SAFETY"
    ? evalCatalog.value.SAFETY.criteria
    : evalCatalog.value.FUNCTIONAL.criteria;
});

const overrideComplete = computed(() => {
  const criteria = overrideCriteria.value;
  if (!criteria.length) return false;
  return criteria.every((c) => Boolean(overrideScores.value[c.id]));
});

const allSanctions = computed(() => {
  if (!historyData.value?.history_visible) return [];
  return [...(historyData.value.prior_sanctions || []), ...(historyData.value.sanctions || [])];
});


function sanctionHistoryLabel(s: SanctionRow): string {
  return s.sanction_display_label || s.outcome_label || s.institutional_sanction_label || s.sanction_result_label;
}

function sanctionOutcomeClass(s: SanctionRow): string {
  if (s.is_hiring_ban) return "sanction-outcome sanction-outcome--ban";
  const label = s.outcome_label || s.institutional_sanction_label || "";
  if (label === "현장퇴출") return "sanction-outcome sanction-outcome--expulsion";
  return "sanction-outcome";
}

function closeAll() {
  dialogOpen.value = false;
  dialogMode.value = null;
  error.value = "";
  historyError.value = "";
  syncBodyScrollLock();
}

function syncBodyScrollLock() {
  if (dialogOpen.value) {
    document.body.classList.add("fe-sheet-open-body");
  } else {
    document.body.classList.remove("fe-sheet-open-body");
  }
}

async function ensureCatalog() {
  if (!violations.value.length) {
    const res = await api.get("/functional-eval/violation-catalog");
    violations.value = res.data.items || [];
    if (!sanctionForm.violation_code) {
      sanctionForm.violation_code = res.data.default_violation_code || violations.value[0]?.code || "";
    }
  }
  if (!evalCatalog.value) {
    const res = await api.get("/functional-eval/eval-catalog");
    evalCatalog.value = res.data;
  }
}

function openSanction() {
  error.value = "";
  dialogMode.value = "sanction";
  dialogOpen.value = true;
  syncBodyScrollLock();
  void ensureCatalog();
}

function onSanctionSaved() {
  closeAll();
  emit("saved");
}

async function previewSanctionEvidence(sanctionId: number) {
  try {
    const res = await api.get(`/functional-eval/sanctions/${sanctionId}/evidence-photo`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    historyError.value = "근거 사진을 불러오지 못했습니다.";
  }
}

async function openOverride(evalType: EvalType) {
  overrideEvalType.value = evalType;
  overrideReason.value = "";
  error.value = "";
  loadingOverride.value = true;
  dialogMode.value = "override";
  dialogOpen.value = true;
  syncBodyScrollLock();
  try {
    await ensureCatalog();
    const res = await api.get(`/functional-eval/workers/${props.workerId}/assessment/${evalType}`);
    const existing = res.data.assessment?.scores || {};
    const criteria =
      evalType === "SAFETY"
        ? evalCatalog.value!.SAFETY.criteria
        : evalCatalog.value!.FUNCTIONAL.criteria;
    const scores: Record<string, string> = {};
    for (const c of criteria) {
      scores[c.id] = existing[c.id] || c.grades[Math.floor((c.grades.length - 1) / 2)]?.key || c.grades[0]?.key;
    }
    overrideScores.value = scores;
  } catch {
    error.value = "평가 데이터를 불러오지 못했습니다.";
  } finally {
    loadingOverride.value = false;
  }
}

async function openHistory() {
  historyError.value = "";
  loadingHistory.value = true;
  dialogMode.value = "history";
  dialogOpen.value = true;
  syncBodyScrollLock();
  try {
    const res = await api.get(`/functional-eval/workers/${props.workerId}/history`);
    historyData.value = res.data;
  } catch {
    historyError.value = "이력을 불러오지 못했습니다.";
    historyData.value = null;
  } finally {
    loadingHistory.value = false;
  }
}

async function submitOverride() {
  if (!overrideReason.value.trim() || !overrideComplete.value) return;
  saving.value = true;
  error.value = "";
  try {
    await api.put(`/functional-eval/hq/workers/${props.workerId}/assessment/${overrideEvalType.value}`, {
      scores: overrideScores.value,
      reason: overrideReason.value.trim(),
    });
    closeAll();
    emit("saved");
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "점수 수정에 실패했습니다.";
  } finally {
    saving.value = false;
  }
}

watch(
  () => props.workerId,
  () => closeAll(),
);

onMounted(() => {
  void ensureCatalog();
});

onBeforeUnmount(() => {
  document.body.classList.remove("fe-sheet-open-body");
});
</script>

<style scoped>
.hq-worker-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  justify-content: flex-end;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.field {
  display: block;
  margin-top: 12px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.req {
  color: #dc2626;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 14px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.criteria-row {
  margin-top: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f1f5f9;
}

.criteria-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.grade-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.grade-chip {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.grade-chip.selected {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.history-block h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.history-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.history-list {
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
  line-height: 1.5;
}

.history-list li {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}

.history-list li:last-child {
  border-bottom: none;
}

.history-item-main {
  font-weight: 500;
  color: #0f172a;
}

.history-item-meta {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
}

.meta {
  color: #64748b;
  font-size: 12px;
}

.meta.note {
  display: block;
  margin-top: 2px;
}

.error {
  color: #b91c1c;
  margin-top: 10px;
  font-size: 13px;
}

.warn {
  color: #9a3412;
  background: #fff7ed;
  padding: 10px 12px;
  border-radius: 8px;
}

.muted {
  color: #64748b;
}

.sanction-outcome {
  font-weight: 600;
}

.sanction-outcome--ban {
  color: #dc2626;
}

.sanction-outcome--expulsion {
  color: #ea580c;
}
</style>

<style>
.hq-fe-overlay {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
  overflow-y: auto;
  background: rgba(15, 23, 42, 0.52);
}

.hq-fe-dialog {
  position: relative;
  flex-shrink: 0;
  width: min(560px, 100%);
  max-height: min(88vh, 760px);
  display: flex;
  flex-direction: column;
  margin: auto;
  padding: 20px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.22);
  color: #0f172a;
}

.hq-fe-dialog--wide {
  width: min(640px, 100%);
}

.hq-fe-dialog--history {
  width: min(720px, 100%);
  max-height: min(90vh, 820px);
}

.hq-fe-dialog-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-top: 4px;
  padding-right: 4px;
}

.hq-fe-dialog .dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.hq-fe-dialog .dialog-head h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
  flex: 1;
  min-width: 0;
}

.hq-fe-dialog .dialog-close {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.hq-fe-dialog .dialog-close:hover {
  background: #e2e8f0;
}
</style>
