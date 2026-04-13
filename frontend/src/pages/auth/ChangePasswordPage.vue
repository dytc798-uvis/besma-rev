<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px">
    <div class="card" style="width: 420px">
      <div class="card-title">비밀번호 변경</div>

      <p v-if="auth.mustChangePassword" style="font-size: 13px; color: #334155; margin: 0 0 12px">
        초기 비밀번호를 변경해야 서비스를 이용할 수 있습니다.
      </p>

      <p style="font-size: 12px; color: #64748b; margin: 0 0 12px">
        비밀번호는 4자리 이상이면 설정할 수 있습니다.
      </p>

      <form @submit.prevent="handleChangePassword" style="display: flex; flex-direction: column; gap: 10px">
        <label>
          <div style="font-size: 12px; margin-bottom: 2px">현재 비밀번호</div>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>

        <label>
          <div style="font-size: 12px; margin-bottom: 2px">새 비밀번호</div>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>

        <label>
          <div style="font-size: 12px; margin-bottom: 2px">새 비밀번호 확인</div>
          <input v-model="newPasswordConfirm" type="password" autocomplete="new-password" />
        </label>

        <button class="primary" type="submit" :disabled="loading">
          {{ loading ? "변경 중..." : "비밀번호 변경" }}
        </button>

        <p v-if="successMessage" style="color: #15803d; font-size: 12px; margin: 0">{{ successMessage }}</p>
        <p v-if="errorMessage" style="color: #dc2626; font-size: 12px; margin: 0">{{ errorMessage }}</p>

        <p style="margin: 8px 0 0; font-size: 12px">
          <button type="button" class="secondary" style="width: 100%" @click="handleLogout">다른 계정으로 로그인</button>
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

const currentPassword = ref("");
const newPassword = ref("");
const newPasswordConfirm = ref("");
const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data?.detail;
    if (typeof d === "string") {
      if (d === "CURRENT_PASSWORD_INCORRECT") return "현재 비밀번호가 올바르지 않습니다.";
      if (d === "NEW_PASSWORD_REQUIRED") return "새 비밀번호를 입력해 주세요.";
      if (d === "NEW_PASSWORD_CONFIRM_MISMATCH") return "새 비밀번호 확인이 일치하지 않습니다.";
      return d;
    }
  }
  return "요청을 처리할 수 없습니다.";
}

async function handleChangePassword() {
  loading.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    const res = await api.post("/auth/change-password", {
      current_password: currentPassword.value,
      new_password: newPassword.value,
      new_password_confirm: newPasswordConfirm.value,
    });

    successMessage.value = (res.data?.message as string) || "비밀번호가 변경되었습니다.";
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
    errorMessage.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function handleLogout() {
  try {
    await api.post("/auth/logout");
  } catch {
    /* ignore */
  }
  auth.logout();
  router.replace({ name: "login" });
}
</script>

<style scoped></style>
