<template>
  <FeSignatureModal
    ref="modalRef"
    :open="open"
    :title="consentTitle"
    :description="consentDescription"
    :consent-text="consentBody"
    require-consent-check
    require-consent-scroll
    submit-label="동의 및 서명"
    @update:open="(v) => emit('update:open', v)"
    @submit="onSubmit"
  >
    <template v-if="requirePasswordChange" #before-signature>
      <section class="fe-consent-password">
        <h3>비밀번호 변경</h3>
        <p>동의서 서명과 함께 초기 비밀번호를 새 비밀번호로 변경해야 합니다.</p>
        <label>
          <span>현재 비밀번호</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>
        <label>
          <span>새 비밀번호</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>
        <label>
          <span>새 비밀번호 확인</span>
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
import { applyFeConsentPrefill, FE_CONSENT_FALLBACK_BODY } from "@/utils/feConsentPrefill";

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
const consentTitle = ref("기능인인정제 평가 수행 및 전자서명 동의서");
const teamLabel = ref("");
const siteFullName = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const newPasswordConfirm = ref("");

const consentDescription = computed(() => {
  const lines: string[] = [];
  if (siteFullName.value) lines.push(siteFullName.value);
  if (teamLabel.value) lines.push(teamLabel.value);
  lines.push("기능인인제 화면 이용 전 최초 1회 동의·서명이 필요합니다.");
  return lines.join("\n");
});

function applyPrefill(data: FeConsentPrefill | null | undefined) {
  applyFeConsentPrefill(data, { consentBody, consentTitle, teamLabel, siteFullName });
  if (!consentBody.value) {
    consentBody.value = FE_CONSENT_FALLBACK_BODY;
  }
}

watch(
  () => props.prefill,
  (data) => {
    if (data) applyPrefill(data);
  },
  { immediate: true },
);

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen || props.prefill?.consent_body) return;
    if (consentBody.value && consentBody.value !== FE_CONSENT_FALLBACK_BODY) return;
    try {
      const res = await api.get("/functional-eval/consent/status");
      applyPrefill(res.data as FeConsentPrefill);
    } catch {
      consentBody.value = FE_CONSENT_FALLBACK_BODY;
    }
  },
  { immediate: true },
);

async function onSubmit(payload: {
  signature_data: string;
  consent_acknowledged: boolean;
  read_to_bottom_confirmed?: boolean;
  read_completed_at?: string;
}) {
  if (props.requirePasswordChange) {
    if (!currentPassword.value || !newPassword.value || !newPasswordConfirm.value) {
      modalRef.value?.setError("비밀번호 변경 정보를 모두 입력해 주세요.");
      return;
    }
    if (newPassword.value !== newPasswordConfirm.value) {
      modalRef.value?.setError("새 비밀번호 확인이 일치하지 않습니다.");
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
    modalRef.value?.setError(typeof detail === "string" ? detail : "동의서 저장에 실패했습니다.");
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
