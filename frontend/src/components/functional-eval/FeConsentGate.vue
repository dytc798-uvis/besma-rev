<template>
  <FeSignatureModal
    ref="modalRef"
    :open="open"
    :title="consentTitle"
    :description="consentDescription"
    :consent-text="consentBody"
    require-consent-check
    require-consent-scroll
    submit-label="?? ? ??"
    @update:open="(v) => emit('update:open', v)"
    @submit="onSubmit"
  >
    <template v-if="requirePasswordChange" #before-signature>
      <section class="fe-consent-password">
        <h3>???? ??</h3>
        <p>??? ??? ?? ?? ????? ? ????? ???? ???.</p>
        <label>
          <span>?? ????</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>
        <label>
          <span>? ????</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>
        <label>
          <span>? ???? ??</span>
          <input v-model="newPasswordConfirm" type="password" autocomplete="new-password" />
        </label>
      </section>
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
const consentTitle = ref("?????? ?? ?? ? ???? ???");
const teamLabel = ref("");
const siteFullName = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const newPasswordConfirm = ref("");

const consentDescription = computed(() => {
  const lines: string[] = [];
  if (siteFullName.value) lines.push(siteFullName.value);
  if (teamLabel.value) lines.push(teamLabel.value);
  lines.push("?????? ?? ?? ? ?? 1? ?????? ?????.");
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
    modalRef.value?.setError("??? ??? ??? ? ?? ??? ???.");
    await loadConsentStatus();
    return;
  }
  if (props.requirePasswordChange) {
    if (!currentPassword.value || !newPassword.value || !newPasswordConfirm.value) {
      modalRef.value?.setError("???? ?? ??? ?? ??? ???.");
      return;
    }
    if (newPassword.value !== newPasswordConfirm.value) {
      modalRef.value?.setError("? ???? ??? ???? ????.");
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
    modalRef.value?.setError(typeof detail === "string" ? detail : "??? ??? ??????.");
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
