<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh">
    <div class="card" style="width: 420px">
      <div class="card-title">비밀번호 변경</div>

      <form @submit.prevent="handleChangePassword" style="display: flex; flex-direction: column; gap: 10px">
        <label>
          <div style="font-size: 12px; margin-bottom: 2px">현재 비밀번호</div>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>

        <label>
          <div style="font-size: 12px; margin-bottom: 2px">새 비밀번호</div>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>

        <button class="primary" type="submit" :disabled="loading">
          {{ loading ? "변경 중..." : "비밀번호 변경" }}
        </button>

        <p v-if="errorMessage" style="color: #dc2626; font-size: 12px; margin: 0">{{ errorMessage }}</p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

const currentPassword = ref("");
const newPassword = ref("");
const loading = ref(false);
const errorMessage = ref("");

async function handleChangePassword() {
  loading.value = true;
  errorMessage.value = "";

  try {
    await api.post("/auth/change-password", {
      current_password: currentPassword.value,
      new_password: newPassword.value,
    });

    await auth.loadMe();

    if (auth.user?.role === "WORKER") {
      router.replace({ name: "worker-mobile-list" });
      return;
    }

    if (auth.user?.ui_type === "HQ_SAFE") {
      router.replace({ name: "hq-safe-document-explorer" });
      return;
    }

    if (auth.user?.ui_type === "SITE") {
      router.replace({ name: "site-mobile-ops" });
      return;
    }

    if (auth.user?.ui_type === "HQ_OTHER") {
      router.replace({ name: "hq-other-dashboard" });
      return;
    }

    router.replace({ name: "login" });
  } catch (e) {
    errorMessage.value = "요청을 처리할 수 없습니다.";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped></style>

