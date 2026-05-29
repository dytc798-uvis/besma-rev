<template>
  <section
    class="eval-panel"
    :class="{
      'eval-panel--mobile': variant === 'mobile',
      'eval-panel--desktop': variant === 'desktop',
      'fe-sheet': variant === 'mobile',
      'fe-sheet-open': variant === 'mobile',
    }"
    :role="variant === 'mobile' ? 'dialog' : undefined"
    :aria-modal="variant === 'mobile' ? true : undefined"
    :aria-label="variant === 'mobile' ? `${worker.name} ${title}` : undefined"
  >
    <div v-if="variant === 'mobile'" class="fe-sheet-handle" aria-hidden="true" />
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
            :class="{ selected: scores[c.id] === g.key }"
            :disabled="disabled"
            @click="pickGrade(c.id, g.key)"
          >
            <span class="grade-chip-label">{{ g.label }}</span>
            <span class="grade-chip-pts">{{ g.points }}</span>
          </button>
        </div>
      </div>

      <!-- 모바일: 항목별 세로 라디오 -->
      <div v-else class="criteria-mobile">
        <div v-for="c in criteria" :key="c.id" class="criterion-block">
          <div class="criterion-title">{{ c.title }}</div>
          <div class="grade-options">
            <label v-for="g in c.grades" :key="g.key" class="grade-option">
              <input
                type="radio"
                :name="`grade-${worker.id}-${c.id}`"
                :value="g.key"
                :checked="scores[c.id] === g.key"
                :disabled="disabled"
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
        <p v-if="error" class="error">{{ error }}</p>
        <div class="actions">
          <button
            v-if="variant === 'mobile'"
            class="stitch-btn-secondary touch-btn"
            type="button"
            @click="emit('close')"
          >
            취소
          </button>
          <button
            class="stitch-btn-primary touch-btn save-btn"
            type="button"
            :disabled="disabled || saving || !canSave"
            @click="emit('save')"
          >
            {{ saving ? "저장 중…" : saveLabel }}
          </button>
        </div>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

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
    loading: boolean;
    saving: boolean;
    disabled: boolean;
    error: string;
    variant: "mobile" | "desktop";
    preview: { total_score: number; max_score: number; grade_label: string } | null;
    saveLabel?: string;
  }>(),
  { saveLabel: "평가 저장" },
);

const emit = defineEmits<{
  close: [];
  save: [];
  "update:scores": [value: Record<string, string>];
}>();

const gradeHeaderLabels = computed(() => {
  const first = props.criteria[0];
  return first ? first.grades.map((g) => g.label) : [];
});

const canSave = computed(() => {
  if (!props.criteria.length) return false;
  return props.criteria.every((c) => Boolean(props.scores[c.id]));
});

function pickGrade(criterionId: string, gradeKey: string) {
  emit("update:scores", { ...props.scores, [criterionId]: gradeKey });
}
</script>

<style scoped>
.eval-panel--desktop {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 16px 20px 20px;
  overflow: hidden;
}

.eval-panel--mobile.panel,
.eval-panel--mobile {
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

.criteria-desktop {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
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
