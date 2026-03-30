<template>
  <li class="decision-item">
    <div class="decision-item-head">
      <span class="decision-item-title">{{ title }}</span>
      <div class="decision-item-head-right">
        <button type="button" class="btn-copy-cursor" @click="copyCursorDraft">
          검토안 복사
        </button>
        <span v-if="copyFeedback" class="copy-feedback">{{ copyFeedback }}</span>
        <span class="decision-item-pill">OPEN</span>
      </div>
    </div>
    <p v-if="summary" class="decision-item-summary">{{ summary }}</p>
    <p v-if="refDoc" class="decision-item-ref">
      <span class="ref-label">참고:</span>
      {{ refDoc }}
    </p>

    <div class="decision-controls">
      <p class="decision-section-title">선택지</p>
      <div class="option-cards" role="radiogroup" :aria-label="`${title} 선택지`">
        <label
          v-for="opt in effectiveOptions"
          :key="opt.id"
          class="option-card"
          :class="{
            'option-card--selected': selectedId === opt.id,
            'option-card--recommended': opt.recommended,
          }"
        >
          <input
            v-model="selectedId"
            type="radio"
            class="option-card-input"
            :value="opt.id"
            :name="radioGroupName"
          />
          <span class="option-card-body">
            <span class="option-card-top">
              <span class="option-card-label">{{ opt.label }}</span>
              <span v-if="opt.recommended" class="option-badge-rec">추천</span>
            </span>
            <span class="option-card-desc">{{ opt.description }}</span>
          </span>
        </label>
      </div>

      <div v-if="selectedOption" class="selection-preview">
        <div class="selection-preview-title">선택안 미리보기</div>
        <p class="selection-preview-text">{{ selectedOption.description }}</p>
        <p v-if="selectedOption.expectedOutcome" class="selection-preview-outcome">
          <strong>예상 반영 결과:</strong>
          {{ selectedOption.expectedOutcome }}
        </p>
      </div>

      <div class="selection-summary" aria-live="polite">
        <span class="selection-summary-label">최종 선택</span>
        <span class="selection-summary-value">{{ selectedOption?.label ?? "선택지를 고르세요" }}</span>
      </div>

      <label class="decision-note-wrap">
        <span class="decision-note-label">구현 지시 (Cursor 실행용)</span>
        <textarea
          v-model="localNote"
          class="decision-note decision-note--textarea"
          rows="4"
          :placeholder="instructionPlaceholder"
        />
        <p class="decision-instruction-hint">
          승인 시 위 내용이 <strong>Cursor 실행 지시</strong> 블록에 그대로 들어갑니다. 모호한 표현(예: 추후 구현
          예정)은 사용할 수 없습니다.
        </p>
      </label>

      <div class="decision-actions">
        <button
          type="button"
          class="btn-approve"
          :disabled="!canApprove"
          :title="!canApprove ? '구현 지시를 구체적으로 입력해야 승인할 수 있습니다.' : ''"
          @click="emitAction('APPROVED')"
        >
          승인
        </button>
        <button type="button" class="btn-defer" @click="emitAction('DEFERRED')">보류</button>
        <button type="button" class="btn-reject" @click="emitAction('REJECTED')">기각</button>
      </div>
      <p class="decision-actions-hint">
        처리 시 선택안 「{{ selectedOption?.label ?? "—" }}」이(가) 로그에 남고, 클립보드에는
        <strong>구현 지시</strong> 기반 「Cursor 실행 지시」가 복사됩니다. (승인만 즉시 실행 대상)
      </p>
    </div>
  </li>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { DecisionAction, DecisionOption } from "@/services/decisionService";
import {
  copyTextToClipboard,
  formatReviewDraftMarkdown,
  isVagueImplementationInstruction,
} from "@/services/decisionCursorExport";

const FALLBACK_OPTIONS: DecisionOption[] = [
  {
    id: "fallback_conservative",
    label: "안 1 · 보수적 적용",
    description: "기존 동작을 최대한 유지하고, 필요한 부분만 최소 변경합니다.",
    recommended: true,
    expectedOutcome: "교육·전파 비용이 적고, 회귀 위험이 낮습니다.",
    implementationDirective:
      "- 해당 `scope` 화면에서 기존 기본값·정렬·필터를 유지하고, 변경이 필요한 컴포넌트만 최소 diff로 수정.\n- 회귀 방지를 위해 E2E/스모크 경로(진입·저장·목록 갱신)만 확인.",
  },
  {
    id: "fallback_balanced",
    label: "안 2 · 균형",
    description: "운영 편의와 변경 범위를 중간 수준으로 맞춥니다.",
    expectedOutcome: "일부 화면만 조정되며, 사용자 적응 기간이 짧습니다.",
    implementationDirective:
      "- 해당 `scope`의 주요 리스트/대시보드에서 기본 필터·KPI 카드 순서·CTA 중 1~2곳만 조정.\n- 변경 구역에 짧은 인앱 안내(툴팁 또는 한 줄 카피) 추가.",
  },
  {
    id: "fallback_bold",
    label: "안 3 · 적극 개선",
    description: "운영 효율을 우선해 흐름·문구를 적극 바꿉니다.",
    expectedOutcome: "체감 개선은 크지만, 안내·교육이 더 필요할 수 있습니다.",
    implementationDirective:
      "- 해당 `scope` 플로우 전반(네비·빈 상태·모달 단계)을 재배치하고, 정렬/필터 기본값을 운영 우선으로 재설정.\n- `docs/OPEN_DECISIONS.md` 또는 운영 가이드에 UX 변경 요약 반영.",
  },
];

const props = defineProps<{
  title: string;
  scope: string;
  summary?: string;
  refDoc?: string;
  /** 비어 있으면 운영용 기본 3안 사용 */
  options?: DecisionOption[];
  /** 라디오 name 충돌 방지 */
  decisionId: string;
}>();

const emit = defineEmits<{
  action: [
    payload: {
      action: DecisionAction;
      selectedOption: string;
      note: string;
      implementationDirective: string;
    },
  ];
}>();

const effectiveOptions = computed(() =>
  props.options && props.options.length > 0 ? props.options : FALLBACK_OPTIONS,
);

const radioGroupName = computed(() => `decision-${props.decisionId}`);

function pickInitialId(opts: DecisionOption[]): string {
  const rec = opts.find((o) => o.recommended);
  return rec?.id ?? opts[0]?.id ?? "";
}

const selectedId = ref(pickInitialId(effectiveOptions.value));

watch(
  effectiveOptions,
  (opts) => {
    const next = pickInitialId(opts);
    if (!opts.some((o) => o.id === selectedId.value)) {
      selectedId.value = next;
    }
  },
  { deep: true },
);

const selectedOption = computed(() => effectiveOptions.value.find((o) => o.id === selectedId.value));

const instructionPlaceholder =
  "이 기능을 어떻게 수정/추가할지 구체적으로 작성 (Cursor가 그대로 실행함)";

const localNote = ref("");
const copyFeedback = ref("");

const instructionTrimmed = computed(() => localNote.value.trim());
/** 승인: 비어 있거나 모호한 지시면 불가 */
const canApprove = computed(
  () => instructionTrimmed.value.length > 0 && !isVagueImplementationInstruction(instructionTrimmed.value),
);

async function copyCursorDraft() {
  const label = selectedOption.value?.label?.trim() || "";
  const dir = selectedOption.value?.implementationDirective?.trim() ?? "";
  const text = formatReviewDraftMarkdown({
    decision_id: props.decisionId,
    scope: props.scope,
    title: props.title,
    selected_option: label || "(선택지 미지정)",
    note: localNote.value,
    implementation_directive: dir,
  });
  const ok = await copyTextToClipboard(text);
  copyFeedback.value = ok ? "복사됨" : "실패";
  window.setTimeout(() => {
    copyFeedback.value = "";
  }, 2200);
}

function emitAction(action: DecisionAction) {
  if (action === "APPROVED") {
    if (!instructionTrimmed.value) return;
    if (isVagueImplementationInstruction(instructionTrimmed.value)) return;
  }
  const label = selectedOption.value?.label?.trim() || selectedId.value;
  const dir = selectedOption.value?.implementationDirective?.trim() ?? "";
  emit("action", {
    action,
    selectedOption: label,
    note: localNote.value,
    implementationDirective: dir,
  });
}
</script>

<style scoped>
.decision-item {
  list-style: none;
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}

.decision-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.decision-item-head-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.btn-copy-cursor {
  border: 1px solid #64748b;
  background: #fff;
  color: #334155;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.btn-copy-cursor:hover {
  background: #f1f5f9;
  border-color: #475569;
}

.copy-feedback {
  font-size: 10px;
  font-weight: 700;
  color: #15803d;
}

.decision-item-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.4;
}

.decision-item-pill {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 3px 8px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
}

.decision-item-summary {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.decision-item-ref {
  margin: 8px 0 0;
  font-size: 12px;
  color: #94a3b8;
  word-break: break-all;
}

.ref-label {
  font-weight: 600;
  color: #64748b;
}

.decision-controls {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.decision-section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
  text-transform: none;
}

.option-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  padding: 10px 12px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
  background: #f8fafc;
}

.option-card:hover {
  border-color: #cbd5e1;
  background: #fff;
}

.option-card--recommended:not(.option-card--selected) {
  border-color: #fde68a;
  background: #fffbeb;
}

.option-card--selected {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2);
}

.option-card-input {
  margin-top: 3px;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  accent-color: #2563eb;
}

.option-card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.option-card-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.option-card-label {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.option-badge-rec {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.03em;
  padding: 2px 8px;
  border-radius: 999px;
  background: #22c55e;
  color: #fff;
}

.option-card-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

.selection-preview {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: #f0f9ff;
}

.selection-preview-title {
  font-size: 11px;
  font-weight: 800;
  color: #1d4ed8;
  letter-spacing: 0.02em;
  margin-bottom: 6px;
}

.selection-preview-text {
  margin: 0;
  font-size: 12px;
  color: #1e3a8a;
  line-height: 1.45;
}

.selection-preview-outcome {
  margin: 8px 0 0;
  font-size: 12px;
  color: #1e40af;
  line-height: 1.45;
}

.selection-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

.selection-summary-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.selection-summary-value {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.decision-note-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.decision-note-label {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.decision-note {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
}

.decision-note--textarea {
  min-height: 88px;
  resize: vertical;
  font-family: inherit;
  line-height: 1.45;
}

.decision-instruction-hint {
  margin: 0;
  font-size: 10px;
  color: #64748b;
  line-height: 1.4;
}

.decision-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.decision-actions button {
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.btn-approve {
  background: #dcfce7;
  color: #166534;
}

.btn-approve:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-defer {
  background: #fef3c7;
  color: #92400e;
}

.btn-reject {
  background: #fee2e2;
  color: #991b1b;
}

.decision-actions-hint {
  margin: 0;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}
</style>
