<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from "vue";

const LOCAL_TEST_NOTICE_KEY = "besma_local_test_notice_v1";

const localDevNotice = {
  title: "\ub85c\uceec \ud14c\uc2a4\ud2b8 \ud658\uacbd\uc785\ub2c8\ub2e4.",
  frontendLabel: "\ud504\ub860\ud2b8",
  warning: "\uae30\ub2a5\uc778\uc778\uc815\uc81c \ub610\ub294 \ubcf8\uc0ac \uc811\uc218 \uc218\uc815 \uc804\uc5d0 \uba3c\uc800 \ud655\uc778\ud55c \ud6c4 \ubc30\ud3ec\ud558\uc138\uc694.",
  backend: "\ubc31\uc5d4\ub4dc\ub294 backend\uc5d0\uc11c uvicorn --port 8001",
  fallback: "\ub610\ub294 run_local_mvp.bat",
};

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
    localDevNotice.title,
    "",
    `${localDevNotice.frontendLabel}: ${window.location.origin}`,
    `API: ${apiBase}`,
    "",
    localDevNotice.warning,
    "",
    localDevNotice.backend,
    localDevNotice.fallback,
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
