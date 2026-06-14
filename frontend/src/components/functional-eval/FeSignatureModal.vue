<template>
  <div v-if="open" class="fe-sign-overlay" @click.self="onCancel">
    <div class="fe-sign-modal" role="dialog" aria-modal="true">
      <header class="fe-sign-header">
        <h2>{{ title }}</h2>
        <p v-if="description" class="fe-sign-desc">{{ description }}</p>
      </header>
      <div v-if="consentText" class="fe-sign-consent">
        <pre class="fe-sign-consent-body">{{ consentText }}</pre>
        <label class="fe-sign-check">
          <input v-model="ackChecked" type="checkbox" />
          <span>{{ consentCheckLabel }}</span>
        </label>
      </div>
      <div v-if="showReviewFields" class="fe-sign-review">
        <label class="fe-sign-review-label">
          <span>{{ officerCommentLabel }}</span>
          <textarea v-model="officerComment" rows="3" class="fe-sign-textarea" />
        </label>
        <label class="fe-sign-review-label">
          <span>{{ directorCommentLabel }}</span>
          <textarea v-model="directorComment" rows="3" class="fe-sign-textarea" />
        </label>
      </div>
      <SignaturePad ref="padRef" :width="560" :height="200" />
      <p v-if="error" class="fe-sign-error">{{ error }}</p>
      <footer class="fe-sign-footer">
        <button type="button" class="stitch-btn-secondary" :disabled="submitting" @click="onCancel">취소</button>
        <button type="button" class="stitch-btn-primary" :disabled="submitting || !canSubmit" @click="onSubmit">
          {{ submitting ? "저장 중…" : submitLabel }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import SignaturePad from "@/components/SignaturePad.vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    description?: string;
    consentText?: string;
    consentCheckLabel?: string;
    requireConsentCheck?: boolean;
    submitLabel?: string;
    showReviewFields?: boolean;
    officerCommentLabel?: string;
    directorCommentLabel?: string;
  }>(),
  {
    title: "전자 서명",
    submitLabel: "서명 완료",
    consentCheckLabel: "위 내용을 확인하였으며 동의합니다.",
    requireConsentCheck: false,
    showReviewFields: false,
    officerCommentLabel: "안전보건 담당자 검토 코멘트",
    directorCommentLabel: "안전보건실장 최종 코멘트",
  },
);

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "submit", payload: {
    signature_data: string;
    consent_acknowledged: boolean;
    officer_comment?: string;
    director_comment?: string;
  }): void;
  (e: "cancel"): void;
}>();

const padRef = ref<InstanceType<typeof SignaturePad> | null>(null);
const ackChecked = ref(false);
const officerComment = ref("");
const directorComment = ref("");
const submitting = ref(false);
const error = ref("");

const canSubmit = computed(() => {
  if (props.requireConsentCheck && !ackChecked.value) return false;
  return true;
});

watch(
  () => props.open,
  (val) => {
    if (val) {
      ackChecked.value = false;
      officerComment.value = "";
      directorComment.value = "";
      error.value = "";
      submitting.value = false;
      padRef.value?.clear();
    }
  },
);

function onCancel() {
  emit("update:open", false);
  emit("cancel");
}

function onSubmit() {
  error.value = "";
  if (props.requireConsentCheck && !ackChecked.value) {
    error.value = "동의서 확인 체크가 필요합니다.";
    return;
  }
  const dataUrl = padRef.value?.toDataUrl() || "";
  if (!dataUrl || dataUrl.length < 100) {
    error.value = "서명을 입력해 주세요.";
    return;
  }
  emit("submit", {
    signature_data: dataUrl,
    consent_acknowledged: ackChecked.value || !props.requireConsentCheck,
    officer_comment: props.showReviewFields ? officerComment.value.trim() : undefined,
    director_comment: props.showReviewFields ? directorComment.value.trim() : undefined,
  });
}

function setSubmitting(val: boolean) {
  submitting.value = val;
}

function setError(msg: string) {
  error.value = msg;
}

defineExpose({ setSubmitting, setError });
</script>

<style scoped>
.fe-sign-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.fe-sign-modal {
  width: min(640px, 100%);
  max-height: 90vh;
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
}

.fe-sign-header h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

.fe-sign-desc {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 14px;
}

.fe-sign-consent {
  margin-bottom: 12px;
}

.fe-sign-consent-body {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  margin: 0 0 8px;
}

.fe-sign-check {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 14px;
}

.fe-sign-error {
  color: #b91c1c;
  font-size: 13px;
  margin: 8px 0 0;
}

.fe-sign-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.fe-sign-review {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.fe-sign-review-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.fe-sign-textarea {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  font-family: inherit;
  font-size: 13px;
  resize: vertical;
}
</style>
