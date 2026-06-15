<template>
  <section class="sanction-inline panel">
    <div class="sanction-inline-head">
      <h3>위반·제재</h3>
      <button class="link-btn" type="button" @click="emit('open-history')">이력</button>
    </div>
    <p v-if="promptMessage" class="sanction-hint">{{ promptMessage }}</p>
    <p v-else-if="showSanctionForm && hasBottomPrefill" class="sanction-hint">
      「문제」로 평가한 항목이 선택되었습니다. 근거 코멘트를 확인·보완한 뒤 제재를 등록하세요. (첫 제재는 별도 감점 없음)
    </p>
    <p v-else-if="showSanctionForm" class="sanction-hint">
      평가 완료 후에도 제재를 등록할 수 있습니다. 첫 제재는 해당 안전 항목 「문제」 반영, 같은 위반 재발 시 -5점 감점(등급 반영)입니다.
    </p>
    <p class="sanction-status">
      현재 상태:
      <span :class="['status-pill', statusClass(worker.sanction_status)]">{{ worker.sanction_status_label }}</span>
    </p>
    <FeSanctionRegisterForm
      v-if="showSanctionForm"
      :key="`${worker.id}-${prefillToken}`"
      :worker-id="worker.id"
      :worker-name="worker.name"
      :grouped-violations="groupedViolations"
      :default-violation-code="defaultViolationCode"
      :default-note="defaultNote"
      :disabled="disabled"
      :show-cancel="false"
      :focus-comment="hasBottomPrefill"
      @saved="emit('saved')"
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import FeSanctionRegisterForm from "@/components/functional-eval/FeSanctionRegisterForm.vue";
import type { EvalWorkerCompletion } from "@/utils/functionalEvalCompletion";
import { hasSafetyBottomScores } from "@/utils/safetySanctionMapping";

interface ViolationItem {
  code: string;
  category: string;
  category_label: string;
  label: string;
}

interface Worker extends EvalWorkerCompletion {
  id: number;
  name: string;
  sanction_status: string;
  sanction_status_label: string;
  is_permanently_expelled: boolean;
  functional_assessment?: { grade_code?: string; grade_label?: string; is_complete?: boolean; scores?: Record<string, string> } | null;
  safety_assessment?: { grade_code?: string; grade_label?: string; is_complete?: boolean; scores?: Record<string, string> } | null;
}

const props = defineProps<{
  worker: Worker;
  groupedViolations: { category: string; label: string; items: ViolationItem[] }[];
  periodClosed: boolean;
  evidenceSubmitBlocked?: boolean;
  promptMessage?: string;
  defaultViolationCode?: string;
  defaultNote?: string;
  prefillToken?: number;
}>();

const emit = defineEmits<{
  saved: [];
  "open-history": [];
}>();

const disabled = computed(
  () => Boolean(props.evidenceSubmitBlocked) || props.worker.is_permanently_expelled,
);

const showSanctionForm = computed(
  () => !disabled.value || Boolean(props.promptMessage),
);

const hasBottomPrefill = computed(() => {
  if (props.defaultNote && props.defaultViolationCode) return true;
  return hasSafetyBottomScores(props.worker.safety_assessment?.scores);
});

const prefillToken = computed(() => props.prefillToken ?? 0);

function statusClass(status: string) {
  if (status.includes("EXPULSION") || status.includes("BAN")) return "danger";
  if (status.includes("WARNING") || status.includes("TRAINING")) return "warn";
  return "normal";
}
</script>

<style scoped>
.sanction-inline {
  margin-top: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.sanction-inline-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.sanction-inline-head h3 {
  margin: 0;
  font-size: 15px;
}

.sanction-hint {
  margin: 0 0 10px;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  color: #9a3412;
  font-size: 13px;
  line-height: 1.45;
}

.sanction-status {
  margin: 0 0 12px;
  font-size: 13px;
  color: #475569;
}

.status-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.status-pill.danger {
  background: #fee2e2;
  color: #991b1b;
}

.status-pill.warn {
  background: #fef3c7;
  color: #92400e;
}

.status-pill.normal {
  background: #f1f5f9;
  color: #475569;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
}
</style>
