<template>
  <div v-if="open">
    <Teleport to="body">
      <div class="fe-sign-overlay" @click.self="onCancel">
        <div class="fe-sign-modal" role="dialog" aria-modal="true">
          <header class="fe-sign-header">
            <h2>{{ title }}</h2>
            <p v-if="description" class="fe-sign-desc">{{ description }}</p>
          </header>
          <div v-if="consentText" class="fe-sign-consent">
            <pre
              ref="consentBodyRef"
              class="fe-sign-consent-body"
              :class="{ 'fe-sign-consent-body--locked': requireConsentScroll && !scrollCompleted }"
              @scroll="onConsentScroll"
            >{{ consentText }}</pre>
            <p
              v-if="requireConsentScroll"
              class="fe-sign-scroll-hint"
              :class="{ 'fe-sign-scroll-hint--done': scrollCompleted }"
            >
              {{ scrollHintText }}
            </p>
            <label class="fe-sign-check" :class="{ 'fe-sign-check--disabled': consentControlsLocked }">
              <input
                v-model="ackChecked"
                type="checkbox"
                :disabled="consentControlsLocked"
              />
              <span>{{ consentCheckLabel }}</span>
            </label>
          </div>
          <div v-if="showOfficerComment" class="fe-sign-review">
            <label class="fe-sign-review-label">
              <span>{{ officerCommentLabel }}</span>
              <textarea v-model="officerComment" rows="3" class="fe-sign-textarea" />
            </label>
          </div>
          <div v-if="showDirectorComment" class="fe-sign-review">
            <label class="fe-sign-review-label">
              <span>{{ directorCommentLabel }}</span>
              <textarea v-model="directorComment" rows="3" class="fe-sign-textarea" />
            </label>
          </div>
          <SignaturePad ref="padRef" :width="560" :height="200" :disabled="signaturePadDisabled" />
          <p v-if="error" class="fe-sign-error">{{ error }}</p>
          <footer class="fe-sign-footer">
            <button type="button" class="stitch-btn-secondary" :disabled="submitting" @click="onCancel">취소</button>
            <button type="button" class="stitch-btn-primary" :disabled="submitting || !canSubmit" @click="onSubmit">
              {{ submitting ? "저장 중…" : submitLabel }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import SignaturePad from "@/components/SignaturePad.vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    description?: string;
    consentText?: string;
    consentCheckLabel?: string;
    requireConsentCheck?: boolean;
    requireConsentScroll?: boolean;
    submitLabel?: string;
    showReviewFields?: boolean;
    reviewMode?: "officer" | "director" | "both" | "none";
    officerCommentLabel?: string;
    directorCommentLabel?: string;
  }>(),
  {
    title: "전자 서명",
    submitLabel: "서명 완료",
    consentCheckLabel: "위 내용을 확인하였으며 동의합니다.",
    requireConsentCheck: false,
    requireConsentScroll: false,
    showReviewFields: false,
    reviewMode: "none",
    officerCommentLabel: "안전보건 담당자 검토 코멘트",
    directorCommentLabel: "안전보건실장 최종 코멘트",
  },
);

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "submit", payload: {
    signature_data: string;
    consent_acknowledged: boolean;
    read_to_bottom_confirmed?: boolean;
    read_completed_at?: string;
    officer_comment?: string;
    director_comment?: string;
  }): void;
  (e: "cancel"): void;
}>();

const padRef = ref<InstanceType<typeof SignaturePad> | null>(null);
const consentBodyRef = ref<HTMLElement | null>(null);
const ackChecked = ref(false);
const officerComment = ref("");
const directorComment = ref("");
const submitting = ref(false);
const error = ref("");
const scrollCompleted = ref(false);
const readCompletedAt = ref<string | null>(null);

const showOfficerComment = computed(() => {
  if (props.reviewMode === "officer" || props.reviewMode === "both") return true;
  return props.showReviewFields;
});
const showDirectorComment = computed(() => {
  if (props.reviewMode === "director" || props.reviewMode === "both") return true;
  return false;
});

const consentControlsLocked = computed(
  () => props.requireConsentScroll && props.consentText && !scrollCompleted.value,
);

const signaturePadDisabled = computed(() => consentControlsLocked.value);

const scrollHintText = computed(() =>
  scrollCompleted.value
    ? "동의서 내용을 모두 확인했습니다. 동의 후 서명해 주세요."
    : "동의서 내용을 끝까지 확인한 후 서명할 수 있습니다.",
);

const canSubmit = computed(() => {
  if (props.requireConsentScroll && props.consentText && !scrollCompleted.value) return false;
  if (props.requireConsentCheck && !ackChecked.value) return false;
  return true;
});

function isScrolledToBottom(el: HTMLElement): boolean {
  const threshold = 8;
  return el.scrollTop + el.clientHeight >= el.scrollHeight - threshold;
}

function markScrollCompleted() {
  if (scrollCompleted.value) return;
  scrollCompleted.value = true;
  readCompletedAt.value = new Date().toISOString();
}

function onConsentScroll() {
  const el = consentBodyRef.value;
  if (!el || !props.requireConsentScroll) return;
  if (isScrolledToBottom(el)) markScrollCompleted();
}

async function refreshConsentScrollState() {
  scrollCompleted.value = false;
  readCompletedAt.value = null;
  if (!props.requireConsentScroll || !props.consentText) {
    scrollCompleted.value = true;
    return;
  }
  await nextTick();
  const el = consentBodyRef.value;
  if (!el) return;
  el.scrollTop = 0;
  if (el.scrollHeight <= el.clientHeight + 8) {
    markScrollCompleted();
  }
}

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
      void refreshConsentScrollState();
    }
  },
);

watch(
  () => props.consentText,
  () => {
    if (props.open) void refreshConsentScrollState();
  },
);

function onCancel() {
  emit("update:open", false);
  emit("cancel");
}

function onSubmit() {
  error.value = "";
  if (props.requireConsentScroll && props.consentText && !scrollCompleted.value) {
    error.value = "동의서 내용을 끝까지 확인해 주세요.";
    return;
  }
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
    read_to_bottom_confirmed: props.requireConsentScroll ? scrollCompleted.value : undefined,
    read_completed_at: props.requireConsentScroll ? readCompletedAt.value ?? undefined : undefined,
    officer_comment: showOfficerComment.value ? officerComment.value.trim() : undefined,
    director_comment: showDirectorComment.value ? directorComment.value.trim() : undefined,
  });
}

function setSubmitting(val: boolean) {
  submitting.value = val;
}

function setError(msg: string) {
  error.value = msg;
}

defineExpose({ setSubmitting, setError, scrollCompleted, consentBodyRef });
</script>

<style scoped>
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
  max-height: 240px;
  overflow-y: auto;
}

.fe-sign-consent-body--locked {
  border-color: #fcd34d;
}

.fe-sign-scroll-hint {
  margin: 0 0 8px;
  font-size: 13px;
  color: #b45309;
  font-weight: 600;
}

.fe-sign-scroll-hint--done {
  color: #047857;
}

.fe-sign-check {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 14px;
}

.fe-sign-check--disabled {
  opacity: 0.55;
  cursor: not-allowed;
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

<style>
.fe-sign-overlay {
  position: fixed;
  inset: 0;
  z-index: 600;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  overflow-y: auto;
}

.fe-sign-modal {
  width: min(640px, 100%);
  max-height: 90vh;
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  color: #0f172a;
}
</style>
