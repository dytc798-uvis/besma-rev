<template>
  <FeSignatureModal
    ref="modalRef"
    :open="open"
    title="기능인인정제 평가 동의서"
    description="기능인인정제 화면 이용 전 최초 1회 동의·서명이 필요합니다."
    :consent-text="consentBody"
    require-consent-check
    submit-label="동의 및 서명"
    @update:open="(v) => emit('update:open', v)"
    @submit="onSubmit"
  />
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";
import FeSignatureModal from "@/components/functional-eval/FeSignatureModal.vue";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "completed"): void;
}>();

const modalRef = ref<InstanceType<typeof FeSignatureModal> | null>(null);
const consentBody = ref("");

onMounted(async () => {
  try {
    const res = await api.get("/functional-eval/consent/status");
    consentBody.value = res.data.consent_body || "";
  } catch {
    consentBody.value = "기능인인정제 평가 업무 수행에 동의합니다.";
  }
});

async function onSubmit(payload: { signature_data: string; consent_acknowledged: boolean }) {
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
