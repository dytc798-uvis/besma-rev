<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from "vue";

const LOCAL_TEST_NOTICE_KEY = "besma_local_test_notice_v1";

function isLocalDevHost(): boolean {
  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1" || host === "118.36.137.127";
}

function maybeShowLocalTestNotice() {
  if (!isLocalDevHost()) return;
  if (import.meta.env.PROD && import.meta.env.VITE_API_BASE_URL?.includes("api.besma.co.kr")) return;
  try {
    if (localStorage.getItem(LOCAL_TEST_NOTICE_KEY)) return;
  } catch {
    return;
  }

  const apiBase = `${window.location.protocol}//${window.location.hostname}:8001`;
  const lines = [
    "로컬 테스트 환경입니다.",
    "",
    `프론트: ${window.location.origin}`,
    `API: ${apiBase}`,
    "",
    "기능인제(제재·본사 점수 수정 등)는 여기서 먼저 확인한 뒤 배포하세요.",
    "",
    "백엔드: backend에서 uvicorn --port 8001",
    "또는 run_local_mvp.bat",
  ];
  window.alert(lines.join("\n"));

  try {
    localStorage.setItem(LOCAL_TEST_NOTICE_KEY, "1");
  } catch {
    // ignore
  }
}

onMounted(() => {
  maybeShowLocalTestNotice();
});
</script>

<style>
html,
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}
</style>
