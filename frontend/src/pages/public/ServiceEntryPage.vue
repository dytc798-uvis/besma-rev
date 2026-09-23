<template>
  <main class="service-entry"><h1>안전보건 업무</h1><p role="status">{{ message }}</p><RouterLink to="/law-register">법규등록부로 돌아가기</RouterLink></main>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const message = ref("사용 가능한 업무 화면으로 이동합니다.");
onMounted(() => {
  const ui = auth.effectiveUiType || auth.user?.ui_type;
  const role = auth.user?.role;
  const service = route.params.service;
  if (role === "WORKER" || role === "FUNCTIONAL_EVAL_VIEWER" || (service === "worker-voice" && ui === "HQ_OTHER")) {
    message.value = "이 업무는 현장 담당자 또는 안전보건실 계정으로 이용할 수 있습니다.";
    return;
  }
  const prefix = ui === "SITE" ? "/site" : ui === "HQ_OTHER" ? "/hq-other" : ui === "HQ_SAFE" ? "/hq-safe" : "";
  if (!prefix) { message.value = "계정의 업무 권한을 확인해 주세요."; return; }
  void router.replace(`${prefix}/${service}`);
});
</script>
<style scoped>.service-entry { max-width: 680px; margin: 80px auto; padding: 24px; } .service-entry p { line-height: 1.8; }</style>
