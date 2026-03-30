<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh">
    <div class="card" style="width: 420px">
      <div class="card-title">비밀번호 변경 필요</div>

      <div style="font-size: 12px; color: #6b7280; margin-bottom: 16px">
        최초 로그인(또는 초기화) 계정은 비밀번호 변경 완료 전까지 서비스 접근이 차단됩니다.
      </div>

      <form @submit.prevent="handleChangePassword" style="display: flex; flex-direction: column; gap: 10px">
        <label>
          <div style="font-size: 12px; margin-bottom: 2px">현재 비밀번호</div>
          <input v-model="currentPassword" type="password" autocomplete="current-password" />
        </label>

        <label>
          <div style="font-size: 12px; margin-bottom: 2px">새 비밀번호</div>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>

        <div style="font-size: 12px; color: #6b7280">
          정책: 최소 8자 + 특수문자 1개 이상
        </div>

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
import axios from "axios";
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
      router.replace({ name: "hq-safe-tbm-monitor" });
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
    if (axios.isAxiosError(e)) {
      const status = e.response?.status;
      if (status === 400) {
        errorMessage.value = "비밀번호 변경에 실패했습니다. 입력값을 확인하세요.";
      } else if (status === 403) {
        errorMessage.value = "현재 상태에서 비밀번호 변경이 허용되지 않습니다. 관리자에게 문의하세요.";
      } else {
        errorMessage.value = "네트워크 오류로 비밀번호 변경에 실패했습니다.";
      }
    } else {
      errorMessage.value = "알 수 없는 오류가 발생했습니다.";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped></style>

