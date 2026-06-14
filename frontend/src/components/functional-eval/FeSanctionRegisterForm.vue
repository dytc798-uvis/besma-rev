<template>
  <div class="fe-sanction-register">
    <label class="field">
      <span class="field-label">위반 항목</span>
      <select v-model="violationCode" class="field-control" :disabled="disabled">
        <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
          <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
        </optgroup>
      </select>
    </label>

    <fieldset class="evidence-type-field">
      <legend class="field-label">제재 근거 <span class="req">*</span></legend>
      <label class="radio-line">
        <input v-model="evidenceType" type="radio" value="COMMENT" :disabled="disabled" />
        <span>코멘트</span>
      </label>
      <label class="radio-line">
        <input v-model="evidenceType" type="radio" value="PHOTO" :disabled="disabled" />
        <span>사진</span>
      </label>
    </fieldset>

    <label v-if="evidenceType === 'COMMENT'" class="field">
      <span class="field-label">근거 코멘트 <span class="req">*</span></span>
      <textarea
        ref="noteInputRef"
        v-model="note"
        class="field-control"
        rows="3"
        placeholder="위반 상황·제재 근거"
        :disabled="disabled"
      />
    </label>

    <template v-else>
      <label class="field">
        <span class="field-label">근거 사진 <span class="req">*</span></span>
        <input
          ref="photoInputRef"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          class="field-control"
          :disabled="disabled"
          @change="onPhotoChange"
        />
      </label>
      <label class="field">
        <span class="field-label">보충 설명 (선택)</span>
        <textarea v-model="note" class="field-control" rows="2" placeholder="사진 설명" :disabled="disabled" />
      </label>
      <div v-if="photoPreviewUrl" class="photo-preview">
        <img :src="photoPreviewUrl" alt="제재 근거 사진 미리보기" />
      </div>
    </template>

    <p class="sign-hint">제재 등록 시 전자 서명이 필요합니다. (첫 제재는 별도 감점 없음 · 추가 제재 -5점)</p>

    <div class="actions">
      <button
        v-if="showCancel"
        class="stitch-btn-secondary touch-btn"
        type="button"
        :disabled="saving"
        @click="emit('cancel')"
      >
        취소
      </button>
      <button
        class="stitch-btn-primary touch-btn"
        type="button"
        :disabled="disabled || saving || !canProceed"
        @click="openSignature"
      >
        {{ saving ? "등록 중…" : "서명 후 제재 등록" }}
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <FeSignatureModal
      :open="signatureOpen"
      title="제재 등록 서명"
      :description="signatureDescription"
      submit-label="제재 등록"
      @update:open="signatureOpen = $event"
      @submit="submitWithSignature"
      @cancel="signatureOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { api } from "@/services/api";
import FeSignatureModal from "@/components/functional-eval/FeSignatureModal.vue";

interface ViolationItem {
  code: string;
  category: string;
  category_label: string;
  label: string;
}

const props = withDefaults(
  defineProps<{
    workerId: number;
    workerName: string;
    groupedViolations: { category: string; label: string; items: ViolationItem[] }[];
    disabled?: boolean;
    defaultViolationCode?: string;
    defaultNote?: string;
    focusComment?: boolean;
    showCancel?: boolean;
  }>(),
  {
    disabled: false,
    showCancel: true,
    focusComment: false,
  },
);

const emit = defineEmits<{ saved: []; cancel: [] }>();

const violationCode = ref(props.defaultViolationCode || "");
const evidenceType = ref<"COMMENT" | "PHOTO">("COMMENT");
const note = ref("");
const photoFile = ref<File | null>(null);
const photoPreviewUrl = ref<string | null>(null);
const photoInputRef = ref<HTMLInputElement | null>(null);
const noteInputRef = ref<HTMLTextAreaElement | null>(null);
const saving = ref(false);
const error = ref("");
const signatureOpen = ref(false);

const canProceed = computed(() => {
  if (!violationCode.value) return false;
  if (evidenceType.value === "COMMENT") return Boolean(note.value.trim());
  return Boolean(photoFile.value);
});

const signatureDescription = computed(
  () => `${props.workerName} 근로자 제재 등록 — 근거(${evidenceType.value === "PHOTO" ? "사진" : "코멘트"}) 확인 후 서명해 주세요.`,
);

function applyDefaults() {
  if (props.defaultViolationCode) violationCode.value = props.defaultViolationCode;
  if (props.defaultNote) note.value = props.defaultNote;
}

watch(
  () => [props.defaultViolationCode, props.defaultNote] as const,
  ([code, defaultNote]) => {
    if (code) violationCode.value = code;
    if (defaultNote) note.value = defaultNote;
    if (props.focusComment && defaultNote) {
      void nextTick(() => noteInputRef.value?.focus());
    }
  },
  { immediate: true },
);

watch(
  () => props.workerId,
  () => {
    resetForm();
    applyDefaults();
  },
);

watch(evidenceType, () => {
  error.value = "";
  if (evidenceType.value === "COMMENT") {
    clearPhotoPreview();
    photoFile.value = null;
    if (photoInputRef.value) photoInputRef.value.value = "";
  }
});

function clearPhotoPreview() {
  if (photoPreviewUrl.value) {
    URL.revokeObjectURL(photoPreviewUrl.value);
    photoPreviewUrl.value = null;
  }
}

function resetForm() {
  violationCode.value = props.defaultViolationCode || "";
  note.value = props.defaultNote || "";
  evidenceType.value = "COMMENT";
  photoFile.value = null;
  error.value = "";
  clearPhotoPreview();
  if (photoInputRef.value) photoInputRef.value.value = "";
}

function onPhotoChange(e: Event) {
  const input = e.target as HTMLInputElement;
  photoFile.value = input.files?.[0] ?? null;
  clearPhotoPreview();
  if (photoFile.value) {
    photoPreviewUrl.value = URL.createObjectURL(photoFile.value);
  }
}

function openSignature() {
  if (!canProceed.value) return;
  error.value = "";
  signatureOpen.value = true;
}

async function submitWithSignature(payload: { signature_data: string }) {
  saving.value = true;
  error.value = "";
  try {
    const fd = new FormData();
    fd.append("worker_id", String(props.workerId));
    fd.append("violation_code", violationCode.value);
    fd.append("evidence_type", evidenceType.value);
    fd.append("signature_data", payload.signature_data);
    if (note.value.trim()) fd.append("note", note.value.trim());
    if (evidenceType.value === "PHOTO" && photoFile.value) {
      fd.append("photo", photoFile.value);
    }
    await api.post("/functional-eval/sanctions", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    signatureOpen.value = false;
    resetForm();
    emit("saved");
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "제재 등록에 실패했습니다.";
    signatureOpen.value = false;
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
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

.evidence-type-field {
  margin: 12px 0 0;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.evidence-type-field legend {
  padding: 0 4px;
}

.radio-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 14px;
}

.photo-preview {
  margin-top: 10px;
}

.photo-preview img {
  max-width: 100%;
  max-height: 220px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  object-fit: contain;
  background: #f8fafc;
}

.sign-hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: #64748b;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.error {
  color: #b91c1c;
  margin-top: 10px;
  font-size: 13px;
}
</style>
