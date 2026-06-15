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
          <FeGradeInflationReview
            v-if="gradeReview"
            :review="gradeReview"
            :s-reason="sOverLimitReason"
            @update:s-reason="sOverLimitReason = $event"
          />
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
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import SignaturePad from "@/components/SignaturePad.vue";
import FeGradeInflationReview, { type GradeInflationReview } from "@/components/functional-eval/FeGradeInflationReview.vue";

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
    gradeReview?: GradeInflationReview | null;
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
    gradeReview: null,
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
    s_over_limit_reason?: string;
  }): void;
  (e: "cancel"): void;
}>();

const padRef = ref<InstanceType<typeof SignaturePad> | null>(null);
const consentBodyRef = ref<HTMLElement | null>(null);
const ackChecked = ref(false);
const officerComment = ref("");
const directorComment = ref("");
const sOverLimitReason = ref("");
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
  if (props.gradeReview?.s_over_limit && sOverLimitReason.value.trim().length < 10) return false;
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
  if (!props.requireConsentScroll) {
    scrollCompleted.value = true;
    return;
  }
  if (!props.consentText) {
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
    if (typeof document !== "undefined") {
      document.body.classList.toggle(
        "fe-consent-modal-open",
        Boolean(val && props.consentText),
      );
    }
    if (val) {
      ackChecked.value = false;
      officerComment.value = "";
      directorComment.value = "";
      sOverLimitReason.value = "";
      error.value = "";
      submitting.value = false;
      padRef.value?.clear();
      void refreshConsentScrollState();
    }
  },
);

onUnmounted(() => {
  if (typeof document !== "undefined") {
    document.body.classList.remove("fe-consent-modal-open");
  }
});

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
  if (props.gradeReview?.s_over_limit && sOverLimitReason.value.trim().length < 10) {
    error.value = "기능/품질 S등급 권장 기준 초과 사유를 10자 이상 입력해 주세요.";
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
    s_over_limit_reason: props.gradeReview?.s_over_limit ? sOverLimitReason.value.trim() : undefined,
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
  font-size: 22px;
}

.fe-sign-desc {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 17px;
}

.fe-sign-consent {
  margin-bottom: 12px;
}

.fe-sign-consent-body {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 17px;
  line-height: 1.65;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  margin: 0 0 8px;
  max-height: 220px;
  overflow-y: auto;
}

.fe-sign-consent-body--locked {
  border-color: #fcd34d;
}

.fe-sign-scroll-hint {
  margin: 0 0 8px;
  font-size: 16px;
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
  font-size: 17px;
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

@media (max-width: 768px) {
  .fe-sign-overlay {
    padding: 0;
    align-items: stretch;
    background: #fff;
    z-index: 700;
  }

  .fe-sign-modal {
    width: 100%;
    max-width: 100%;
    max-height: 100dvh;
    height: 100dvh;
    border-radius: 0;
    padding: 12px 14px calc(12px + env(safe-area-inset-bottom, 0px));
    box-shadow: none;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .fe-sign-header {
    flex-shrink: 0;
  }

  .fe-sign-header h2 {
    font-size: 21px;
  }

  .fe-sign-desc {
    font-size: 17px;
    margin-bottom: 8px;
  }

  .fe-sign-consent {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    margin-bottom: 8px;
  }

  .fe-sign-consent-body {
    flex: 1;
    min-height: 140px;
    max-height: none;
  }

  .fe-sign-footer {
    flex-shrink: 0;
    margin-top: 8px;
  }
}
</style>
