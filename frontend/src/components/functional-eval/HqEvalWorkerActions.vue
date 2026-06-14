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
      <div v-if="dialogOpen" class="fe-overlay-backdrop" @click="closeAll" />
      <section
        v-if="dialogMode === 'sanction' && dialogOpen"
        class="panel hq-action-dialog fe-modal-panel"
        role="dialog"
        aria-modal="true"
        @click.stop
      >
        <div class="dialog-head">
          <h2>{{ workerName }} — 제재 등록</h2>
          <button class="link-btn dialog-close" type="button" @click="closeAll">✕</button>
        </div>
        <label class="field">
          <span class="field-label">위반 항목</span>
          <select v-model="sanctionForm.violation_code" class="field-control">
            <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
              <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
            </optgroup>
          </select>
        </label>
        <label class="field">
          <span class="field-label">등록 사유 <span class="req">*</span></span>
          <textarea
            v-model="sanctionForm.note"
            class="field-control"
            rows="3"
            placeholder="위반 상황·등록 사유"
          />
        </label>
        <div class="actions">
          <button class="stitch-btn-secondary" type="button" @click="closeAll">취소</button>
          <button
            class="stitch-btn-primary"
            type="button"
            :disabled="saving || !sanctionForm.violation_code || !sanctionForm.note.trim()"
            @click="submitSanction"
          >
            {{ saving ? "등록 중…" : "제재 등록" }}
          </button>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <section
        v-else-if="dialogMode === 'override' && dialogOpen"
        class="panel hq-action-dialog fe-modal-panel hq-override-dialog"
        role="dialog"
        aria-modal="true"
        @click.stop
      >
        <div class="dialog-head">
          <h2>{{ workerName }} — {{ overrideEvalType === "SAFETY" ? "2-2 안전·제재" : "2-1 기능" }} 점수 수정</h2>
          <button class="link-btn dialog-close" type="button" @click="closeAll">✕</button>
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
        v-else-if="dialogMode === 'history' && dialogOpen"
        class="panel hq-action-dialog fe-modal-panel hq-history-dialog"
        role="dialog"
        aria-modal="true"
        @click.stop
      >
        <div class="dialog-head">
          <h2>{{ workerName }} — 평가·제재 이력</h2>
          <button class="link-btn dialog-close" type="button" @click="closeAll">✕</button>
        </div>
        <p v-if="loadingHistory" class="muted">불러오는 중…</p>
        <div v-else-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</div>
        <div v-else class="history-sections">
          <section class="history-block">
            <h3>제재 이력</h3>
            <ul class="history-list">
              <li v-for="s in allSanctions" :key="`s-${s.id}`">
                {{ s.violation_label }} → {{ s.sanction_result_label }} ({{ s.strike_number }}차)
                <span class="meta">{{ formatDate(s.created_at) }}</span>
                <span v-if="s.reported_by_name" class="meta"> · {{ s.reported_by_name }}</span>
                <span v-if="s.note" class="meta note"> — {{ s.note }}</span>
              </li>
              <li v-if="!allSanctions.length">제재 이력 없음</li>
            </ul>
          </section>
          <section v-if="historyData?.assessment_revisions?.length" class="history-block">
            <h3>점수 수정 이력</h3>
            <ul class="history-list">
              <li v-for="r in historyData.assessment_revisions" :key="`r-${r.id}`">
                {{ r.eval_type === "SAFETY" ? "2-2 안전" : "2-1 기능" }}
                {{ r.before_grade_code || "—" }} → {{ r.after_grade_code }}
                <span class="meta">{{ formatDate(r.created_at) }}</span>
                <span v-if="r.edited_by_name" class="meta"> · {{ r.edited_by_name }}</span>
                <span class="meta note"> — {{ r.reason }}</span>
              </li>
            </ul>
          </section>
        </div>
        <p v-if="historyError" class="error">{{ historyError }}</p>
      </section>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "@/services/api";

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
  strike_number: number;
  note?: string | null;
  reported_by_name?: string | null;
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

function formatDate(v: string) {
  try {
    return new Date(v).toLocaleString("ko-KR");
  } catch {
    return v;
  }
}

function closeAll() {
  dialogOpen.value = false;
  dialogMode.value = null;
  error.value = "";
  historyError.value = "";
}

async function ensureCatalog() {
  if (!violations.value.length) {
    const res = await api.get("/functional-eval/violation-catalog");
    violations.value = res.data.items || [];
    if (violations.value.length && !sanctionForm.violation_code) {
      sanctionForm.violation_code = violations.value[0].code;
    }
  }
  if (!evalCatalog.value) {
    const res = await api.get("/functional-eval/eval-catalog");
    evalCatalog.value = res.data;
  }
}

function openSanction() {
  sanctionForm.note = "";
  error.value = "";
  dialogMode.value = "sanction";
  dialogOpen.value = true;
  void ensureCatalog();
}

async function openOverride(evalType: EvalType) {
  overrideEvalType.value = evalType;
  overrideReason.value = "";
  error.value = "";
  loadingOverride.value = true;
  dialogMode.value = "override";
  dialogOpen.value = true;
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

async function submitSanction() {
  if (!sanctionForm.violation_code || !sanctionForm.note.trim()) return;
  saving.value = true;
  error.value = "";
  try {
    await api.post("/functional-eval/sanctions", {
      worker_id: props.workerId,
      violation_code: sanctionForm.violation_code,
      note: sanctionForm.note.trim(),
    });
    closeAll();
    emit("saved");
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "제재 등록에 실패했습니다.";
  } finally {
    saving.value = false;
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

.hq-action-dialog {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1200;
  width: min(560px, calc(100vw - 24px));
  max-height: min(88vh, 720px);
  overflow: auto;
  padding: 20px;
}

.hq-override-dialog {
  width: min(640px, calc(100vw - 24px));
}

.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.dialog-head h2 {
  margin: 0;
  font-size: 18px;
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

.history-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.5;
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
</style>
