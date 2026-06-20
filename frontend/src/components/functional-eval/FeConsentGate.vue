<template>
  <FeSignatureModal
    ref="modalRef"
    :open="open"
    :title="consentTitle"
    :description="consentDescription"
    :consent-text="consentBody"
    require-consent-check
    require-consent-scroll
    :submit-label="submitLabel"
    @update:open="(v) => emit('update:open', v)"
    @submit="onSubmit"
  >
    <template v-if="requirePasswordChange" #before-signature>
      <form class="fe-consent-password" @submit.prevent>
        <h3>{{ passwordTitle }}</h3>
        <p>{{ passwordHelp }}</p>
        <label>
          <span>{{ currentPasswordLabel }}</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>
        <label>
          <span>{{ newPasswordLabel }}</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>
        <label>
          <span>{{ newPasswordConfirmLabel }}</span>
          <input v-model="newPasswordConfirm" type="password" autocomplete="new-password" />
        </label>
      </form>
    </template>
  </FeSignatureModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "@/services/api";
import type { FeConsentPrefill } from "@/composables/useFeConsentCheck";
import FeSignatureModal from "@/components/functional-eval/FeSignatureModal.vue";
import { applyFeConsentPrefill } from "@/utils/feConsentPrefill";

const props = defineProps<{
  open: boolean;
  prefill?: FeConsentPrefill | null;
  requirePasswordChange?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "completed"): void;
}>();

const modalRef = ref<InstanceType<typeof FeSignatureModal> | null>(null);
const consentBody = ref("");
const consentTitle = ref("\uae30\ub2a5\uc778\uc778\uc815\uc81c \ud3c9\uac00 \uc218\ud589 \ubc0f \uc804\uc790\uc11c\uba85 \ub3d9\uc758\uc11c");
const teamLabel = ref("");
const siteFullName = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const newPasswordConfirm = ref("");

const submitLabel = "\ub3d9\uc758 \ubc0f \uc11c\uba85";
const passwordTitle = "\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd";
const passwordHelp = "\ub3d9\uc758\uc11c \uc11c\uba85\uacfc \ud568\uaed8 \ucd08\uae30 \ube44\ubc00\ubc88\ud638\ub97c \uc0c8 \ube44\ubc00\ubc88\ud638\ub85c \ubcc0\uacbd\ud574\uc57c \ud569\ub2c8\ub2e4.";
const currentPasswordLabel = "\ud604\uc7ac \ube44\ubc00\ubc88\ud638";
const newPasswordLabel = "\uc0c8 \ube44\ubc00\ubc88\ud638";
const newPasswordConfirmLabel = "\uc0c8 \ube44\ubc00\ubc88\ud638 \ud655\uc778";
const firstUseNotice = "\uae30\ub2a5\uc778\uc778\uc815\uc81c \ud654\uba74 \uc774\uc6a9 \uc804 \ucd5c\ucd08 1\ud68c \ub3d9\uc758\u00b7\uc11c\uba85\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.";
const loadBeforeRetryMessage = "\ub3d9\uc758\uc11c \uc804\ubb38\uc744 \ubd88\ub7ec\uc628 \ub4a4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.";
const passwordRequiredMessage = "\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd \uc815\ubcf4\ub97c \ubaa8\ub450 \uc785\ub825\ud574 \uc8fc\uc138\uc694.";
const passwordMismatchMessage = "\uc0c8 \ube44\ubc00\ubc88\ud638 \ud655\uc778\uc774 \uc77c\uce58\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.";
const consentSaveFailedMessage = "\ub3d9\uc758\uc11c \uc800\uc7a5\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.";

const consentDescription = computed(() => {
  const lines: string[] = [];
  if (siteFullName.value) lines.push(siteFullName.value);
  if (teamLabel.value) lines.push(teamLabel.value);
  lines.push(firstUseNotice);
  return lines.join("\n");
});

function isUsableConsentText(value: string | null | undefined): boolean {
  const text = (value || "").trim();
  if (text.length < 80) return false;
  if (/\?{3,}/.test(text)) return false;
  return true;
}

function applyPrefill(data: FeConsentPrefill | null | undefined) {
  applyFeConsentPrefill(data, { consentBody, consentTitle, teamLabel, siteFullName });
  if (!isUsableConsentText(consentBody.value)) {
    consentBody.value = "";
  }
}

async function loadConsentStatus() {
  try {
    const res = await api.get("/functional-eval/consent/status");
    applyPrefill(res.data as FeConsentPrefill);
  } catch {
    consentBody.value = "";
  }
}

watch(
  () => props.prefill,
  (data) => {
    applyPrefill(data);
  },
  { immediate: true },
);

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    if (isUsableConsentText(consentBody.value)) return;
    await loadConsentStatus();
  },
  { immediate: true },
);

async function onSubmit(payload: {
  signature_data: string;
  consent_acknowledged: boolean;
  read_to_bottom_confirmed?: boolean;
  read_completed_at?: string;
}) {
  if (!isUsableConsentText(consentBody.value)) {
    modalRef.value?.setError(loadBeforeRetryMessage);
    await loadConsentStatus();
    return;
  }
  if (props.requirePasswordChange) {
    if (!currentPassword.value || !newPassword.value || !newPasswordConfirm.value) {
      modalRef.value?.setError(passwordRequiredMessage);
      return;
    }
    if (newPassword.value !== newPasswordConfirm.value) {
      modalRef.value?.setError(passwordMismatchMessage);
      return;
    }
  }
  modalRef.value?.setSubmitting(true);
  try {
    if (props.requirePasswordChange) {
      await api.post("/auth/change-password", {
        current_password: currentPassword.value,
        new_password: newPassword.value,
        new_password_confirm: newPasswordConfirm.value,
      });
    }
    await api.post("/functional-eval/consent/submit", payload);
    emit("update:open", false);
    emit("completed");
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    modalRef.value?.setError(typeof detail === "string" ? detail : consentSaveFailedMessage);
  } finally {
    modalRef.value?.setSubmitting(false);
  }
}
</script>

<style scoped>
.fe-consent-password {
  display: grid;
  gap: 10px;
  margin: 14px 0;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.58);
}

.fe-consent-password h3 {
  margin: 0;
  font-size: 17px;
  color: #0f172a;
}

.fe-consent-password p {
  margin: 0;
  font-size: 13px;
  color: #475569;
}

.fe-consent-password label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: #334155;
}

.fe-consent-password input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 16px;
  background: rgba(255, 255, 255, 0.94);
}
</style>
