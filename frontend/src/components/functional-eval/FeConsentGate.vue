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
  />
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
  modalRef.value?.setSubmitting(true);
  try {
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
