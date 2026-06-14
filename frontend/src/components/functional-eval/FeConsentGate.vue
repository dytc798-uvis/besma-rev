<template>
  <FeSignatureModal
    ref="modalRef"
    :open="open"
    title="기능인인정제 평가 동의서"
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
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import FeSignatureModal from "@/components/functional-eval/FeSignatureModal.vue";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "completed"): void;
}>();

const modalRef = ref<InstanceType<typeof FeSignatureModal> | null>(null);
const consentBody = ref("");
const teamLabel = ref("");
const siteFullName = ref("");

const consentDescription = computed(() => {
  const lines: string[] = [];
  if (siteFullName.value) lines.push(siteFullName.value);
  if (teamLabel.value) lines.push(teamLabel.value);
  lines.push("기능인인제 화면 이용 전 최초 1회 동의·서명이 필요합니다.");
  return lines.join("\n");
});

onMounted(async () => {
  try {
    const res = await api.get("/functional-eval/consent/status");
    consentBody.value = res.data.consent_body || "";
    teamLabel.value = res.data.role_line || res.data.team_label || "";
    siteFullName.value = res.data.site_full_name || "";
  } catch {
    consentBody.value = "기능인인정제 평가 업무 수행에 동의합니다.";
  }
});

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
