<template>
  <section
    class="eval-panel"
    :class="{
      'eval-panel--mobile': variant === 'mobile',
      'eval-panel--desktop': variant === 'desktop',
    }"
    :role="variant === 'mobile' ? 'dialog' : undefined"
    :aria-modal="variant === 'mobile' ? true : undefined"
    :aria-label="variant === 'mobile' ? `${worker.name} ${title}` : undefined"
  >
    <header class="eval-head">
      <div>
        <h2 class="eval-head-title">{{ worker.name }}</h2>
        <p class="eval-head-sub">{{ title }}</p>
      </div>
      <button
        v-if="variant === 'mobile'"
        class="link-btn touch-btn-inline"
        type="button"
        @click="emit('close')"
      >
        닫기
      </button>
    </header>

    <p v-if="guidePreviewMode" class="guide-preview-banner">설명서용 샘플 화면 (저장되지 않음)</p>
    <p v-else-if="showEvalPolicyHint" class="default-grade-hint" :class="evalPolicyHintClass">
      {{ evalPolicyHint }}
    </p>
    <p v-if="loading" class="hint">불러오는 중…</p>
    <template v-else>
      <!-- PC: 항목별 가로 4버튼 — 한 화면에 최대한 노출 -->
      <div v-if="variant === 'desktop'" class="criteria-desktop">
        <div class="criteria-desktop-header" aria-hidden="true">
          <span class="col-title">평가 항목</span>
          <span v-for="label in gradeHeaderLabels" :key="label" class="col-grade">{{ label }}</span>
        </div>
        <div v-for="c in criteria" :key="c.id" class="criteria-row">
          <div class="criteria-row-title">{{ c.title }}</div>
          <button
            v-for="g in c.grades"
            :key="g.key"
            type="button"
            class="grade-chip"
            :class="{ selected: displayScores[c.id] === g.key }"
            :disabled="disabled || guidePreviewMode"
            @click="pickGrade(c.id, g.key)"
          >
            <span class="grade-chip-label">{{ g.label }}</span>
            <span class="grade-chip-pts">{{ g.points }}</span>
          </button>
        </div>
      </div>

      <!-- 모바일: 항목별 세로 라디오 -->
      <div v-else ref="criteriaMobileRef" class="criteria-mobile">
        <div
          v-for="c in criteria"
          :key="c.id"
          :ref="(el) => setCriterionBlockRef(c.id, el as Element | null)"
          class="criterion-block"
        >
          <div class="criterion-title">{{ c.title }}</div>
          <div class="grade-options">
            <label v-for="g in c.grades" :key="g.key" class="grade-option">
              <input
                type="radio"
                :name="`grade-${worker.id}-${c.id}`"
                :value="g.key"
                :checked="displayScores[c.id] === g.key"
                :disabled="disabled || guidePreviewMode"
                @change="pickGrade(c.id, g.key)"
              />
              <span class="grade-label">{{ g.label }}</span>
              <span class="grade-pts">{{ g.points }}점</span>
            </label>
          </div>
        </div>
      </div>

      <footer class="eval-footer" :class="{ 'eval-footer--sticky': variant === 'mobile' }">
        <p v-if="preview" class="eval-preview">
          합계 <strong>{{ preview.total_score }}</strong> / {{ preview.max_score }}점
          · <strong>{{ preview.grade_label }}</strong>
        </p>
        <p v-else-if="guidePreviewMode" class="eval-preview eval-preview--sample">
          합계 <strong>24</strong> / 32점 · <strong>B등급</strong> (설명서 샘플)
        </p>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="actions">
          <button
            class="stitch-btn-secondary touch-btn"
            type="button"
            :disabled="disabled || saving || !criteria.length"
            @click="setAllNormalGrades"
          >
            일괄 보통 등록
          </button>
          <button
            v-if="variant === 'mobile'"
            class="stitch-btn-secondary touch-btn"
            type="button"
            @click="emit('close')"
          >
            취소
          </button>
          <button
            v-if="isDirty && canSave"
            class="stitch-btn-primary touch-btn save-btn"
            type="button"
            :disabled="disabled || saving"
            @click="emit('save', scores)"
          >
            {{ saving ? "저장 중…" : "수정 저장" }}
          </button>
          <p v-else-if="saving" class="saving-hint" aria-live="polite">저장 중…</p>
          <p v-else-if="canSave && !isDirty" class="saved-hint">저장됨</p>
        </div>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, withDefaults } from "vue";
import { buildSampleScoresForCriteria, isFeGuidePreview } from "@/utils/feGuidePreview";
import { FE_FUNCTIONAL_EVAL_GUIDE, FE_SAFETY_EVAL_GUIDE } from "@/config/feEvalPolicyText";

export interface GradeOption {
  key: string;
  label: string;
  points: number;
}

export interface Criterion {
  id: string;
  title: string;
  grades: GradeOption[];
}

export interface WorkerBrief {
  id: number;
  name: string;
}

const props = withDefaults(
  defineProps<{
    worker: WorkerBrief;
    title: string;
    criteria: Criterion[];
    scores: Record<string, string>;
    baselineScores: Record<string, string>;
    loading: boolean;
    saving: boolean;
    disabled: boolean;
    error: string;
    variant: "mobile" | "desktop";
    preview: { total_score: number; max_score: number; grade_label: string } | null;
    evalKind?: "functional" | "safety";
  }>(),
  { evalKind: "functional" },
);

const emit = defineEmits<{
  close: [];
  save: [scores: Record<string, string>];
  "update:scores": [value: Record<string, string>];
}>();

const gradeHeaderLabels = computed(() => {
  const first = props.criteria[0];
  return first ? first.grades.map((g) => g.label) : [];
});

const guidePreviewMode = computed(() => isFeGuidePreview());

const displayScores = computed(() => {
  if (!guidePreviewMode.value) return props.scores;
  const hasAny = props.criteria.some((c) => Boolean(props.scores[c.id]));
  if (hasAny) return props.scores;
  return buildSampleScoresForCriteria(props.criteria);
});

function scoresEqual(a: Record<string, string>, b: Record<string, string>) {
  for (const c of props.criteria) {
    if ((a[c.id] || "") !== (b[c.id] || "")) return false;
  }
  return true;
}

const isDirty = computed(() => !scoresEqual(props.scores, props.baselineScores));

const canSave = computed(() => {
  if (!props.criteria.length) return false;
  return props.criteria.every((c) => Boolean(props.scores[c.id]));
});

const showEvalPolicyHint = computed(
  () => !guidePreviewMode.value && !props.loading && props.criteria.length > 0,
);

const evalPolicyHint = computed(() =>
  props.evalKind === "safety" ? FE_SAFETY_EVAL_GUIDE : FE_FUNCTIONAL_EVAL_GUIDE,
);

const evalPolicyHintClass = computed(() =>
  props.evalKind === "safety" ? "default-grade-hint--safety" : "default-grade-hint--functional",
);

function scoresComplete(scores: Record<string, string>) {
  return props.criteria.every((c) => Boolean(scores[c.id]));
}

function tryAutoSave(next: Record<string, string>, wasComplete: boolean) {
  if (!scoresComplete(next) || props.disabled || props.saving || props.loading) {
    return false;
  }
  const dirty = !scoresEqual(next, props.baselineScores);
  if (!wasComplete || dirty) {
    emit("save", next);
    return true;
  }
  return false;
}

function findNormalGrade(c: Criterion): string | null {
  const byLabel = c.grades.find((g) => g.label.includes("보통"));
  if (byLabel) return byLabel.key;
  if (!c.grades.length) return null;
  const normalIndex = Math.floor((c.grades.length - 1) / 2);
  return c.grades[normalIndex]?.key ?? null;
}

const criteriaMobileRef = ref<HTMLElement | null>(null);
const criterionBlockRefs = new Map<string, HTMLElement>();

function setCriterionBlockRef(criterionId: string, el: Element | null) {
  if (el instanceof HTMLElement) {
    criterionBlockRefs.set(criterionId, el);
  } else {
    criterionBlockRefs.delete(criterionId);
  }
}

function scrollToNextCriterion(currentCriterionId: string) {
  const container = criteriaMobileRef.value;
  if (!container) return;

  const currentIndex = props.criteria.findIndex((c) => c.id === currentCriterionId);
  if (currentIndex < 0 || currentIndex >= props.criteria.length - 1) return;

  const nextBlock = criterionBlockRefs.get(props.criteria[currentIndex + 1].id);
  if (!nextBlock) return;

  const containerRect = container.getBoundingClientRect();
  const blockRect = nextBlock.getBoundingClientRect();
  const padding = 8;
  const fullyVisible =
    blockRect.top >= containerRect.top + padding && blockRect.bottom <= containerRect.bottom - padding;
  if (fullyVisible) return;

  const scrollTop = container.scrollTop + (blockRect.top - containerRect.top) - padding;
  container.scrollTo({ top: Math.max(0, scrollTop), behavior: "smooth" });
}

function setAllNormalGrades() {
  if (guidePreviewMode.value) return;
  const next: Record<string, string> = {};
  for (const c of props.criteria) {
    const gradeKey = findNormalGrade(c);
    if (gradeKey) {
      next[c.id] = gradeKey;
    }
  }
  emit("update:scores", next);
  if (!props.disabled && !props.saving && scoresComplete(next) && !scoresEqual(next, props.baselineScores)) {
    emit("save", next);
  }
}

async function pickGrade(criterionId: string, gradeKey: string) {
  if (guidePreviewMode.value) return;
  const wasComplete = canSave.value;
  const next = { ...props.scores, [criterionId]: gradeKey };
  emit("update:scores", next);
  if (tryAutoSave(next, wasComplete)) return;
  if (props.variant !== "mobile") return;
  await nextTick();
  scrollToNextCriterion(criterionId);
}
</script>

<style scoped>
.eval-panel--desktop {
  display: flex;
  flex-direction: column;
  flex: 0 1 auto;
  width: 100%;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 16px 20px 20px;
  overflow: visible;
}

.eval-panel--mobile.panel,
.eval-panel--mobile {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #fff;
}

.eval-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.eval-head-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
}

.eval-head-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}

.default-grade-hint {
  margin: 0 0 12px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  font-size: 13px;
  line-height: 1.45;
}
.default-grade-hint--functional {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1e40af;
}
.default-grade-hint--safety {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}

.guide-preview-banner {
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  color: #92400e;
  font-size: 12px;
  font-weight: 600;
}

.eval-preview--sample {
  color: #64748b;
}

.criteria-desktop {
  flex: 0 0 auto;
  overflow: visible;
  padding-right: 4px;
}

.criteria-desktop-header,
.criteria-row {
  display: grid;
  grid-template-columns: minmax(120px, 1.4fr) repeat(4, minmax(64px, 1fr));
  gap: 8px;
  align-items: stretch;
}

.criteria-desktop-header {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
  padding: 8px 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 4px;
}

.criteria-row {
  padding: 6px 0;
  border-bottom: 1px solid #f1f5f9;
}

.criteria-row-title {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  padding-right: 8px;
}

.grade-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: 6px 4px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  background: #fafafa;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s;
}

.grade-chip:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #f8fafc;
}

.grade-chip.selected {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 1px #2563eb;
}

.grade-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.grade-chip-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.grade-chip-pts {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.criteria-mobile {
  flex: 1;
  overflow-y: auto;
}

.criterion-block {
  border-top: 1px solid #e2e8f0;
  padding: 12px 0;
  scroll-margin-top: 8px;
}

.criterion-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}

.grade-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.grade-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fafafa;
  cursor: pointer;
}

.grade-option:has(input:checked) {
  border-color: #2563eb;
  background: #eff6ff;
}

.grade-option input {
  width: 18px;
  height: 18px;
}

.grade-label {
  flex: 1;
  font-size: 14px;
}

.grade-pts {
  font-size: 13px;
  color: #64748b;
}

.eval-footer {
  flex-shrink: 0;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.eval-footer--sticky {
  position: sticky;
  bottom: 0;
  background: linear-gradient(transparent, #fff 16px);
  padding-bottom: env(safe-area-inset-bottom, 0);
}

.eval-preview {
  margin: 0 0 10px;
  padding: 10px 12px;
  background: #f0fdf4;
  border-radius: 8px;
  font-size: 14px;
}

.hint {
  color: #64748b;
}

.error {
  color: #b91c1c;
  margin: 8px 0 0;
}

.actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.saving-hint {
  margin: 0;
  flex: 1;
  min-width: 5rem;
  text-align: right;
  font-size: 14px;
  font-weight: 600;
  color: #2563eb;
}

.saved-hint {
  margin: 0;
  flex: 1;
  min-width: 5rem;
  text-align: right;
  font-size: 13px;
  color: #64748b;
}

.save-btn {
  flex: 1;
  min-height: 48px;
  font-size: 15px;
}

.touch-btn-inline {
  min-height: 44px;
  padding: 8px 12px;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
}

@media (max-width: 900px) {
  .criteria-desktop-header,
  .criteria-row {
    grid-template-columns: 1fr;
  }

  .criteria-desktop-header {
    display: none;
  }

  .criteria-row {
    gap: 6px;
  }

  .criteria-row-title {
    margin-bottom: 4px;
  }

  .grade-chip {
    min-height: 44px;
    flex-direction: row;
    justify-content: space-between;
    padding: 10px 12px;
  }
}
</style>
