<template>
  <div class="issue-backdrop" @click.self="emit('close')">
    <div class="issue-modal" role="dialog" aria-modal="true" aria-labelledby="issue-title">
      <header class="issue-head">
        <h2 id="issue-title">{{ mode === "lookup" ? "나의 아이디 확인" : "비밀번호 찾기" }}</h2>
        <button type="button" class="issue-close" aria-label="닫기" @click="emit('close')">×</button>
      </header>

      <template v-if="mode === 'lookup'">
        <p class="issue-guide">
          이름, 생년월일, ERP 아이디를 입력하면 사용 가능한 BESMA 아이디를 확인할 수 있습니다.
        </p>
        <form class="issue-form" @submit.prevent="submitLookup">
          <label>
            <span>이름</span>
            <input v-model="lookupName" type="text" autocomplete="name" />
          </label>
          <label>
            <span>생년월일 6자리</span>
            <input v-model="lookupBirth6" type="text" inputmode="numeric" maxlength="6" autocomplete="off" placeholder="예: 991231" />
          </label>
          <label>
            <span>ERP 아이디</span>
            <input v-model="lookupErpId" type="text" autocomplete="username" placeholder="예: sijung" />
          </label>
          <button class="primary issue-submit" type="submit" :disabled="loading">
            {{ loading ? "확인 중..." : "나의 아이디 확인" }}
          </button>
          <p v-if="errorMessage" class="issue-error" role="alert">{{ errorMessage }}</p>
        </form>

        <div v-if="lookupResult" class="issue-result">
          <p class="issue-result-lead">{{ lookupResult.message }}</p>
          <div v-for="account in lookupResult.accounts" :key="account.login_id" class="issue-account-block">
            <p><strong>{{ account.role_label }}</strong> {{ account.name }}</p>
            <p>아이디: {{ account.login_id }}</p>
            <p class="issue-result-meta">ERP 아이디로도 로그인할 수 있습니다.</p>
          </div>
        </div>

        <div class="issue-actions">
          <button type="button" class="secondary" @click="openReset">비밀번호 찾기</button>
          <button type="button" class="primary" @click="emit('close')">닫기</button>
        </div>
      </template>

      <template v-else>
        <p class="issue-guide">
          이름, 생년월일, ERP 아이디가 일치하면 새 비밀번호를 설정할 수 있습니다.
        </p>
        <form class="issue-form" @submit.prevent="submitReset">
          <label>
            <span>이름</span>
            <input v-model="resetName" type="text" autocomplete="name" />
          </label>
          <label>
            <span>생년월일 6자리</span>
            <input v-model="resetBirth6" type="text" inputmode="numeric" maxlength="6" autocomplete="off" placeholder="예: 991231" />
          </label>
          <label>
            <span>ERP 아이디</span>
            <input v-model="resetErpId" type="text" autocomplete="username" placeholder="예: sijung" />
          </label>
          <label>
            <span>새 비밀번호</span>
            <input v-model="newPassword" type="password" autocomplete="new-password" />
          </label>
          <label>
            <span>새 비밀번호 확인</span>
            <input v-model="newPasswordConfirm" type="password" autocomplete="new-password" />
          </label>
          <button class="primary issue-submit" type="submit" :disabled="loading">
            {{ loading ? "변경 중..." : "새 비밀번호 설정" }}
          </button>
          <p v-if="errorMessage" class="issue-error" role="alert">{{ errorMessage }}</p>
          <p v-if="resetMessage" class="issue-copy-msg" role="status">{{ resetMessage }}</p>
        </form>

        <div class="issue-actions">
          <button type="button" class="secondary" @click="mode = 'lookup'">아이디 확인으로 돌아가기</button>
          <button type="button" class="primary" @click="emit('close')">닫기</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import axios from "axios";
import { api } from "@/services/api";

interface LoginIdLookupItem {
  login_id: string;
  name: string;
  role_label: string;
}

interface LookupResult {
  message: string;
  accounts: LoginIdLookupItem[];
}

const emit = defineEmits<{ close: [] }>();

const mode = ref<"lookup" | "reset">("lookup");
const loading = ref(false);
const errorMessage = ref("");
const resetMessage = ref("");
const lookupResult = ref<LookupResult | null>(null);

const lookupName = ref("");
const lookupBirth6 = ref("");
const lookupErpId = ref("");
const resetName = ref("");
const resetBirth6 = ref("");
const resetErpId = ref("");
const newPassword = ref("");
const newPasswordConfirm = ref("");

function formatError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data?.detail;
    if (typeof d === "string" && d.trim()) return d;
  }
  return "요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.";
}

function openReset() {
  resetName.value = lookupName.value;
  resetBirth6.value = lookupBirth6.value;
  resetErpId.value = lookupErpId.value;
  errorMessage.value = "";
  resetMessage.value = "";
  mode.value = "reset";
}

async function submitLookup() {
  loading.value = true;
  errorMessage.value = "";
  resetMessage.value = "";
  lookupResult.value = null;
  try {
    const res = await api.post("/auth/find-login-ids", {
      name: lookupName.value.trim(),
      birth6: lookupBirth6.value.trim(),
      erp_login_id: lookupErpId.value.trim(),
    });
    lookupResult.value = res.data as LookupResult;
  } catch (err) {
    errorMessage.value = formatError(err);
  } finally {
    loading.value = false;
  }
}

async function submitReset() {
  loading.value = true;
  errorMessage.value = "";
  resetMessage.value = "";
  try {
    const res = await api.post("/auth/reset-password-public", {
      name: resetName.value.trim(),
      birth6: resetBirth6.value.trim(),
      erp_login_id: resetErpId.value.trim(),
      new_password: newPassword.value,
      new_password_confirm: newPasswordConfirm.value,
    });
    resetMessage.value = res.data?.message || "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.";
    newPassword.value = "";
    newPasswordConfirm.value = "";
  } catch (err) {
    errorMessage.value = formatError(err);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.issue-backdrop {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(15, 23, 42, 0.5);
}
.issue-modal {
  width: min(480px, 100%);
  max-height: min(90vh, 720px);
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  padding: 18px 18px 16px;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.2);
}
.issue-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.issue-head h2 {
  margin: 0;
  font-size: 18px;
}
.issue-close {
  border: none;
  background: transparent;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  color: #64748b;
}
.issue-guide {
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 10px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  line-height: 1.5;
}
.issue-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.issue-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #475569;
}
.issue-form input {
  font-size: 16px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}
.issue-submit {
  margin-top: 4px;
  min-height: 44px;
}
.issue-error {
  margin: 0;
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.45;
}
.issue-result {
  margin-top: 14px;
}
.issue-result-lead {
  margin: 0 0 8px;
  font-weight: 700;
  color: #0f172a;
}
.issue-result-meta {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}
.issue-account-block {
  margin-top: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}
.issue-account-block p {
  margin: 0 0 4px;
  font-size: 15px;
}
.issue-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.issue-actions button {
  flex: 1;
  min-height: 42px;
}
.issue-copy-msg {
  margin: 0;
  font-size: 13px;
  color: #15803d;
  line-height: 1.45;
}
</style>
