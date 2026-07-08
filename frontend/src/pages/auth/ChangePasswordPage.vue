<template>
  <div class="change-password-page">
    <div class="card change-password-card">
      <div class="card-title">비밀번호 변경</div>
      <div class="ascii-title">Change Password</div>

      <p v-if="auth.mustChangePassword" class="help-text">
        초기 비밀번호를 변경해야 서비스를 이용할 수 있습니다.
      </p>

      <p class="hint-text">
        현재 비밀번호에는 발급받은 초기 비밀번호를 입력하고, 새 비밀번호는 4자리 이상으로 설정해 주세요.
      </p>

      <p class="ascii-help">
        Current password = issued initial password. New password = at least 4 characters.
      </p>

      <form class="form-stack" @submit.prevent="handleChangePassword">
        <label>
          <div class="field-label">현재 비밀번호</div>
          <div class="field-label-ascii">Current password</div>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>

        <label>
          <div class="field-label">새 비밀번호</div>
          <div class="field-label-ascii">New password</div>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>

        <label>
          <div class="field-label">새 비밀번호 확인</div>
          <div class="field-label-ascii">Confirm new password</div>
          <input v-model="newPasswordConfirm" type="password" autocomplete="new-password" />
        </label>

        <button class="primary" type="submit" :disabled="loading">
          {{ loading ? "변경 중..." : "비밀번호 변경" }}
        </button>

        <p v-if="successMessage" class="success-message">{{ successMessage }}</p>
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

        <p class="logout-row">
          <button type="button" class="secondary logout-button" @click="handleLogout">
            다른 계정으로 로그인
          </button>
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
import { siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";
import { hqSafeHomeRouteName } from "@/utils/hqHomeRoute";

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

    if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") {
      router.replace({ name: "site-functional-eval-field-form-uploads" });
      return;
    }

    if (auth.user?.ui_type === "HQ_SAFE") {
      router.replace({ name: hqSafeHomeRouteName() });
      return;
    }

    if (auth.user?.ui_type === "SITE") {
      router.replace({ name: siteMobileOrDesktopHomeName() });
      return;
    }

    if (auth.user?.ui_type === "HQ_OTHER") {
      router.replace({ name: "hq-other-field-form-uploads" });
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

<style scoped>
.change-password-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 16px;
}

.change-password-card {
  width: min(420px, 100%);
}

.ascii-title {
  margin-top: 2px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.help-text {
  margin: 12px 0;
  color: #334155;
  font-size: 13px;
}

.hint-text,
.ascii-help {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.form-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-label {
  margin-bottom: 2px;
  font-size: 12px;
  font-weight: 700;
}

.field-label-ascii {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 11px;
}

.success-message {
  margin: 0;
  color: #15803d;
  font-size: 12px;
}

.error-message {
  margin: 0;
  color: #dc2626;
  font-size: 12px;
}

.logout-row {
  margin: 8px 0 0;
  font-size: 12px;
}

.logout-button {
  width: 100%;
}
</style>
