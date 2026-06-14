<template>
  <section class="sanction-inline panel">
    <div class="sanction-inline-head">
      <h3>위반·제재</h3>
      <button class="link-btn" type="button" @click="emit('open-history')">이력</button>
    </div>
    <p v-if="promptMessage" class="sanction-hint">{{ promptMessage }}</p>
    <p v-else-if="showSanctionForm" class="sanction-hint">
      안전·기능 등급에 따라 제재 등록이 필요할 수 있습니다.
    </p>
    <p class="sanction-status">
      현재 상태:
      <span :class="['status-pill', statusClass(worker.sanction_status)]">{{ worker.sanction_status_label }}</span>
    </p>
    <template v-if="showSanctionForm">
      <label class="field">
        <span class="field-label">위반 항목</span>
        <select v-model="violationCode" class="field-control" :disabled="disabled">
          <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
            <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
          </optgroup>
        </select>
      </label>
      <label class="field">
        <span class="field-label">등록 사유 <span class="req">*</span></span>
        <textarea v-model="note" class="field-control" rows="2" placeholder="위반 상황·등록 사유" :disabled="disabled" />
      </label>
      <button
        class="stitch-btn-primary touch-btn sanction-submit"
        type="button"
        :disabled="disabled || saving || !violationCode || !note.trim()"
        @click="submit"
      >
        {{ saving ? "등록 중…" : "제재 등록" }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "@/services/api";
import { needsSanctionPrompt, type EvalWorkerCompletion } from "@/utils/functionalEvalCompletion";

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
  functional_assessment?: { grade_code?: string; grade_label?: string; is_complete?: boolean } | null;
  safety_assessment?: { grade_code?: string; grade_label?: string; is_complete?: boolean } | null;
}

const props = defineProps<{
  worker: Worker;
  groupedViolations: { category: string; label: string; items: ViolationItem[] }[];
  periodClosed: boolean;
  promptMessage?: string;
  defaultViolationCode?: string;
}>();

const emit = defineEmits<{
  saved: [];
  "open-history": [];
}>();

const violationCode = ref(props.defaultViolationCode || "");
const note = ref("");
const saving = ref(false);
const error = ref("");

const disabled = computed(() => props.periodClosed || props.worker.is_permanently_expelled);

const showSanctionForm = computed(
  () => needsSanctionPrompt(props.worker) || props.promptMessage,
);

watch(
  () => props.defaultViolationCode,
  (code) => {
    if (code && !violationCode.value) violationCode.value = code;
  },
  { immediate: true },
);

watch(
  () => props.worker.id,
  () => {
    note.value = "";
    error.value = "";
  },
);

function statusClass(status: string) {
  if (status.includes("EXPULSION") || status.includes("BAN")) return "danger";
  if (status.includes("WARNING") || status.includes("TRAINING")) return "warn";
  return "normal";
}

async function submit() {
  if (!violationCode.value) return;
  const item = props.groupedViolations.flatMap((g) => g.items).find((v) => v.code === violationCode.value);
  const ok = window.confirm(
    `${props.worker.name} 근로자\n위반: ${item?.label || violationCode.value}\n\n제재를 등록하시겠습니까?`,
  );
  if (!ok) return;
  saving.value = true;
  error.value = "";
  try {
    await api.post("/functional-eval/sanctions", {
      worker_id: props.worker.id,
      violation_code: violationCode.value,
      note: note.value.trim(),
    });
    note.value = "";
    emit("saved");
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "제재 등록에 실패했습니다.";
  } finally {
    saving.value = false;
  }
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

.field {
  display: block;
  margin-top: 10px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 15px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
}

.sanction-submit {
  width: 100%;
  margin-top: 12px;
  min-height: 44px;
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

.req {
  color: #dc2626;
}

.error {
  color: #b91c1c;
  margin-top: 8px;
  font-size: 13px;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
}
</style>
