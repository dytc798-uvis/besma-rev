<template>
  <div v-if="open">
    <Teleport to="body">
      <div class="fe-sign-overlay" @click.self="onCancel">
        <div class="fe-sign-modal" role="dialog" aria-modal="true">
          <header class="fe-sign-header">
            <h2>{{ title }}</h2>
            <p v-if="description" class="fe-sign-desc">{{ description }}</p>
          </header>
          <div v-if="requiresConsentText" class="fe-sign-consent">
            <pre
              v-if="hasConsentText"
              ref="consentBodyRef"
              class="fe-sign-consent-body"
              :class="{ 'fe-sign-consent-body--locked': requireConsentScroll && !scrollCompleted }"
              @scroll="onConsentScroll"
            >{{ consentText }}</pre>
            <p v-else class="fe-sign-consent-loading" role="status">
              {{ consentLoadingText }}
            </p>
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
          <slot name="before-signature" />
          <SignaturePad ref="padRef" :width="560" :height="200" :disabled="signaturePadDisabled" />
          <p v-if="error" class="fe-sign-error">{{ error }}</p>
          <footer class="fe-sign-footer">
            <button type="button" class="stitch-btn-secondary" :disabled="submitting" @click="onCancel">{{ cancelLabel }}</button>
            <button type="button" class="stitch-btn-primary" :disabled="submitting || !canSubmit" @click="onSubmit">
              {{ submitting ? submittingLabel : submitLabel }}
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
    title: "\uc804\uc790 \uc11c\uba85",
    submitLabel: "\uc11c\uba85 \uc644\ub8cc",
    consentCheckLabel: "\uc704 \ub0b4\uc6a9\uc744 \ud655\uc778\ud558\uc600\uc73c\uba70 \ub3d9\uc758\ud569\ub2c8\ub2e4.",
    requireConsentCheck: false,
    requireConsentScroll: false,
    showReviewFields: false,
    reviewMode: "none",
    officerCommentLabel: "\uc548\uc804\ubcf4\uac74 \ub2f4\ub2f9\uc790 \uac80\ud1a0 \ucf54\uba58\ud2b8",
    directorCommentLabel: "\uc548\uc804\ubcf4\uac74\uc2e4\uc7a5 \ucd5c\uc885 \ucf54\uba58\ud2b8",
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
const normalizedConsentText = computed(() => (props.consentText || "").trim());
const requiresConsentText = computed(() => props.requireConsentScroll || props.requireConsentCheck || !!normalizedConsentText.value);
const hasConsentText = computed(() => normalizedConsentText.value.length >= 80 && !/\?{3,}/.test(normalizedConsentText.value));

const consentLoadingText = "\ub3d9\uc758\uc11c \ub0b4\uc6a9\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \ud655\uc778\ud574 \uc8fc\uc138\uc694.";
const cancelLabel = "\ucde8\uc18c";
const submittingLabel = "\uc800\uc7a5 \uc911";
const scrollDoneText = "\ub3d9\uc758\uc11c \ub0b4\uc6a9\uc744 \ubaa8\ub450 \ud655\uc778\ud588\uc2b5\ub2c8\ub2e4. \ub3d9\uc758 \ud6c4 \uc11c\uba85\ud574 \uc8fc\uc138\uc694.";
const scrollRequiredText = "\ub3d9\uc758\uc11c \ub0b4\uc6a9\uc744 \ub05d\uae4c\uc9c0 \ud655\uc778\ud55c \ud6c4 \uc11c\uba85\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.";
const scrollRequiredError = "\ub3d9\uc758\uc11c \ub0b4\uc6a9\uc744 \ub05d\uae4c\uc9c0 \ud655\uc778\ud574 \uc8fc\uc138\uc694.";
const checkRequiredError = "\ub3d9\uc758\uc11c \ud655\uc778 \uccb4\ud06c\uac00 \ud544\uc694\ud569\ub2c8\ub2e4.";
const sOverLimitReasonError = "\uae30\ub2a5/\uc548\uc804 S\ub4f1\uae09 \uad8c\uc7a5 \uae30\uc900 \ucd08\uacfc \uc0ac\uc720\ub97c 10\uc790 \uc774\uc0c1 \uc785\ub825\ud574 \uc8fc\uc138\uc694.";
const signatureRequiredError = "\uc11c\uba85\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.";

const showOfficerComment = computed(() => {
  if (props.reviewMode === "officer" || props.reviewMode === "both") return true;
  return props.showReviewFields;
});
const showDirectorComment = computed(() => {
  if (props.reviewMode === "director" || props.reviewMode === "both") return true;
  return false;
});

const consentControlsLocked = computed(
  () => requiresConsentText.value && (!hasConsentText.value || (props.requireConsentScroll && !scrollCompleted.value)),
);

const signaturePadDisabled = computed(() => consentControlsLocked.value);

const scrollHintText = computed(() =>
  scrollCompleted.value ? scrollDoneText : scrollRequiredText,
);

const canSubmit = computed(() => {
  if (requiresConsentText.value && !hasConsentText.value) return false;
  if (props.requireConsentScroll && !scrollCompleted.value) return false;
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
  if (!hasConsentText.value) {
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
        Boolean(val && hasConsentText.value),
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
    error.value = scrollRequiredError;
    return;
  }
  if (props.requireConsentCheck && !ackChecked.value) {
    error.value = checkRequiredError;
    return;
  }
  if (props.gradeReview?.s_over_limit && sOverLimitReason.value.trim().length < 10) {
    error.value = sOverLimitReasonError;
    return;
  }
  const dataUrl = padRef.value?.toDataUrl() || "";
  if (!dataUrl || dataUrl.length < 100) {
    error.value = signatureRequiredError;
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

.fe-sign-consent-loading {
  margin: 0 0 8px;
  padding: 14px;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 15px;
  line-height: 1.55;
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
  align-items: flex-start;
  justify-content: center;
  padding: 16px;
  overflow-y: auto;
}

.fe-sign-modal {
  width: min(760px, 100%);
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
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
    max-height: none;
    min-height: 100dvh;
    border-radius: 0;
    padding: 12px 14px calc(12px + env(safe-area-inset-bottom, 0px));
    box-shadow: none;
    display: block;
    overflow-y: auto;
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
    display: block;
    margin-bottom: 8px;
  }

  .fe-sign-consent-body {
    min-height: 220px;
    max-height: 42dvh;
    overflow-y: auto;
  }

  .fe-sign-footer {
    flex-shrink: 0;
    margin-top: 8px;
  }
}
</style>
