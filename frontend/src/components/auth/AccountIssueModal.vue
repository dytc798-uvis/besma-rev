<template>
  <div class="issue-backdrop" @click.self="emit('close')">
    <div class="issue-modal" role="dialog" aria-modal="true" aria-labelledby="issue-title">
      <header class="issue-head">
        <h2 id="issue-title">아이디 발급</h2>
        <button type="button" class="issue-close" aria-label="닫기" @click="emit('close')">×</button>
      </header>

      <template v-if="!result">
        <div class="issue-scope">
          <button
            type="button"
            class="scope-btn"
            :class="{ active: scope === 'site' }"
            @click="scope = 'site'"
          >
            현장
          </button>
          <button
            type="button"
            class="scope-btn"
            :class="{ active: scope === 'hq' }"
            @click="scope = 'hq'"
          >
            본사
          </button>
        </div>

        <form class="issue-form" @submit.prevent="submitIssue">
          <label v-if="scope === 'site'">
            <span>현장코드 (선택)</span>
            <input v-model="siteCode" type="text" inputmode="numeric" autocomplete="off" placeholder="예: 24044" />
          </label>
          <label v-else>
            <span>부서 또는 구분 (선택)</span>
            <input v-model="department" type="text" autocomplete="off" placeholder="예: 안전보건실" />
          </label>
          <label>
            <span>이름</span>
            <input v-model="name" type="text" autocomplete="name" />
          </label>
          <label>
            <span>생년월일 6자리</span>
            <input v-model="birth6" type="text" inputmode="numeric" maxlength="6" autocomplete="off" placeholder="예: 640303" />
          </label>
          <button class="primary issue-submit" type="submit" :disabled="loading">
            {{ loading ? "발급 중..." : "아이디 발급" }}
          </button>
          <p v-if="errorMessage" class="issue-error" role="alert">{{ errorMessage }}</p>
        </form>
      </template>

      <div v-else class="issue-result">
        <p class="issue-result-lead">{{ result.message }}</p>
        <p v-if="result.site_label" class="issue-result-meta">현장: {{ result.site_label }} {{ result.site_code }}</p>
        <p v-if="result.recipient_name" class="issue-result-meta">수령자: {{ result.recipient_name }}</p>

        <div v-for="(account, idx) in result.accounts" :key="account.login_id" class="issue-account-block">
          <h3 v-if="scope === 'site' && account.role_label === '소장'">소장 계정</h3>
          <h3 v-else-if="scope === 'site'">팀장 계정 {{ teamLeaderIndex(account, idx) }}</h3>
          <h3 v-else>발급 계정</h3>
          <p>아이디: {{ account.login_id }}</p>
          <p>초기 비밀번호: {{ account.initial_password }}</p>
          <p v-if="account.role_label && scope === 'hq'" class="issue-result-meta">역할: {{ account.role_label }}</p>
        </div>

        <p class="issue-note">초기 비밀번호는 최초 로그인 시 반드시 변경해야 합니다.</p>
        <p v-if="scope === 'site' && hasTeamLeaderAccounts" class="issue-note">
          팀장 계정은 현장소장이 해당 팀장에게 직접 안내해 주세요.
        </p>

        <div class="issue-actions">
          <button type="button" class="secondary" @click="copyResult">복사하기</button>
          <button type="button" class="primary" @click="emit('close')">닫기</button>
        </div>
        <p v-if="copyMessage" class="issue-copy-msg" role="status">{{ copyMessage }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import axios from "axios";
import { api } from "@/services/api";

export interface IssuedAccount {
  role_label: string;
  name: string;
  login_id: string;
  initial_password: string;
}

interface IssueResult {
  message: string;
  site_code?: string;
  site_label?: string;
  recipient_name?: string;
  accounts: IssuedAccount[];
}

const emit = defineEmits<{ close: [] }>();

const scope = ref<"site" | "hq">("site");
const siteCode = ref("");
const department = ref("");
const name = ref("");
const birth6 = ref("");
const loading = ref(false);
const errorMessage = ref("");
const result = ref<IssueResult | null>(null);
const copyMessage = ref("");

const hasTeamLeaderAccounts = computed(
  () => (result.value?.accounts || []).some((a) => a.role_label === "팀장"),
);

function teamLeaderIndex(account: IssuedAccount, idx: number) {
  if (!result.value) return idx + 1;
  const leaders = result.value.accounts.filter((a) => a.role_label === "팀장");
  const pos = leaders.findIndex((a) => a.login_id === account.login_id);
  return pos >= 0 ? pos + 1 : idx;
}

function formatIssueError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data?.detail;
    if (typeof d === "string" && d.trim()) return d;
  }
  return "요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.";
}

async function submitIssue() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const res = await api.post("/auth/issue-accounts", {
      scope: scope.value,
      site_code: scope.value === "site" ? siteCode.value.trim() || undefined : undefined,
      department: scope.value === "hq" ? department.value.trim() || undefined : undefined,
      name: name.value.trim(),
      birth6: birth6.value.trim(),
    });
    result.value = res.data as IssueResult;
  } catch (err) {
    errorMessage.value = formatIssueError(err);
  } finally {
    loading.value = false;
  }
}

function buildCopyText(): string {
  if (!result.value) return "";
  const lines: string[] = [result.value.message, ""];
  if (result.value.site_label) {
    lines.push(`현장: ${result.value.site_label} ${result.value.site_code || ""}`.trim());
  }
  if (result.value.recipient_name) {
    lines.push(`수령자: ${result.value.recipient_name}`);
  }
  lines.push("");
  result.value.accounts.forEach((account, idx) => {
    if (scope.value === "site") {
      lines.push(account.role_label === "소장" ? "[소장 계정]" : `[팀장 계정 ${teamLeaderIndex(account, idx)}]`);
    }
    lines.push(`아이디: ${account.login_id}`);
    lines.push(`초기 비밀번호: ${account.initial_password}`);
    lines.push("");
  });
  lines.push("초기 비밀번호는 최초 로그인 시 반드시 변경해야 합니다.");
  return lines.join("\n");
}

async function copyResult() {
  const text = buildCopyText();
  try {
    await navigator.clipboard.writeText(text);
    copyMessage.value = "복사했습니다.";
  } catch {
    copyMessage.value = "복사에 실패했습니다. 내용을 직접 선택해 복사해 주세요.";
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
  margin-bottom: 14px;
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
.issue-scope {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.scope-btn {
  flex: 1;
  min-height: 40px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  cursor: pointer;
  font-weight: 600;
}
.scope-btn.active {
  border-color: #ea580c;
  background: #fff7ed;
  color: #c2410c;
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
.issue-result-lead {
  margin: 0 0 8px;
  font-weight: 700;
  color: #0f172a;
}
.issue-result-meta {
  margin: 0 0 6px;
  font-size: 14px;
  color: #475569;
}
.issue-account-block {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}
.issue-account-block h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #1e3a5f;
}
.issue-account-block p {
  margin: 0 0 4px;
  font-size: 15px;
}
.issue-note {
  margin: 12px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
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
  margin: 8px 0 0;
  font-size: 12px;
  color: #15803d;
}
</style>


