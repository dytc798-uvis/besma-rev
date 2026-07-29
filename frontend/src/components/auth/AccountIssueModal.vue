<template>
  <div class="request-backdrop" @click.self="emit('close')">
    <section class="request-modal" role="dialog" aria-modal="true" aria-labelledby="account-help-title">
      <header class="request-head">
        <div>
          <p class="eyebrow">BESMA 계정 안내</p>
          <h2 id="account-help-title">직원 계정 찾기 · 계정 신청</h2>
        </div>
        <button class="close-btn" type="button" aria-label="닫기" @click="emit('close')">×</button>
      </header>

      <div class="mode-tabs">
        <button type="button" :class="{ active: mode === 'find' }" @click="reset('find')">기존 직원 아이디 찾기</button>
        <button type="button" :class="{ active: mode === 'request' }" @click="reset('request')">신규 계정·업무 권한 신청</button>
      </div>

      <div v-if="resultMessage" class="result-card" role="status">
        <strong>{{ resultMessage }}</strong>
        <p v-if="requestNo">신청번호: {{ requestNo }}</p>
        <p v-for="account in foundAccounts" :key="account.login_id">아이디: {{ account.login_id }}</p>
        <button type="button" class="primary" @click="emit('close')">확인</button>
      </div>

      <form v-else-if="mode === 'find'" class="request-form" @submit.prevent="findAccount">
        <p class="help">이미 인사·ERP·출역 명부에 등록된 직원의 기존 계정만 찾습니다. 새 계정은 생성하지 않습니다.</p>
        <div class="scope-tabs">
          <button type="button" :class="{ active: find.scope === 'site' }" @click="find.scope = 'site'">현장</button>
          <button type="button" :class="{ active: find.scope === 'hq' }" @click="find.scope = 'hq'">본사</button>
        </div>
        <label v-if="find.scope === 'site'">현장코드<input v-model.trim="find.site_code" required /></label>
        <label v-else>부서<input v-model.trim="find.department" required placeholder="예: 안전보건실" /></label>
        <label>이름<input v-model.trim="find.name" required autocomplete="name" /></label>
        <label>생년월일 6자리<input v-model.trim="find.birth6" required maxlength="6" inputmode="numeric" autocomplete="off" /></label>
        <button class="primary" type="submit" :disabled="loading">{{ loading ? "확인 중…" : "기존 계정 확인" }}</button>
      </form>

      <form v-else class="request-form" @submit.prevent="submitRequest">
        <p class="help">ERP 아이디가 없거나 명부에 없는 경우 신청만 접수됩니다. 관리자 승인 전에는 계정이나 권한이 부여되지 않습니다.</p>
        <div class="form-grid">
          <label>이름<input v-model.trim="request.name" required autocomplete="name" /></label>
          <label>휴대전화<input v-model.trim="request.phone_mobile" required inputmode="tel" autocomplete="tel" /></label>
          <label>소속 회사<input v-model.trim="request.company_name" required /></label>
          <label>본사·현장
            <select v-model="request.scope"><option value="HQ">본사</option><option value="SITE">현장</option></select>
          </label>
          <label>부서
            <select v-model="request.department" required>
              <option value="" disabled>부서를 선택하세요</option>
              <option v-for="department in departmentOptions" :key="department" :value="department">{{ department }}</option>
            </select>
          </label>
          <label v-if="request.scope === 'SITE'" class="wide">소속 현장
            <select v-model="request.site_id" required :disabled="optionsLoading">
              <option :value="null" disabled>{{ optionsLoading ? "현장 목록을 불러오는 중…" : "등록된 현장을 선택하세요" }}</option>
              <option v-for="site in options.sites" :key="site.id" :value="site.id">{{ site.name }}</option>
            </select>
          </label>
        </div>
        <label>요청 사유<textarea v-model.trim="request.request_reason" required rows="3" /></label>
        <label class="consent"><input v-model="request.privacy_consent" type="checkbox" /> 계정 신청 처리를 위한 개인정보 수집·이용에 동의합니다.</label>
        <button class="primary" type="submit" :disabled="loading || !request.privacy_consent">{{ loading ? "접수 중…" : "신청 접수" }}</button>
      </form>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import axios from "axios";
import { api } from "@/services/api";
import {
  emptyAccountRequestOptions,
  fetchAccountRequestOptions,
  type AccountRequestOptions,
  type AccountRequestScope,
} from "@/services/accountRequestOptions";

const emit = defineEmits<{ close: [] }>();
const mode = ref<"find" | "request">("find");
const loading = ref(false);
const errorMessage = ref("");
const resultMessage = ref("");
const requestNo = ref("");
const foundAccounts = ref<Array<{ login_id: string }>>([]);
const options = ref<AccountRequestOptions>(emptyAccountRequestOptions());
const optionsLoading = ref(false);
const find = reactive({ scope: "site", site_code: "", department: "", name: "", birth6: "" });
const request = reactive({
  name: "", phone_mobile: "", company_name: "부현전기", scope: "HQ" as AccountRequestScope,
  department: "", site_id: null as number | null, request_reason: "", privacy_consent: false,
});
const departmentOptions = computed(() => options.value.departments[request.scope] || []);

watch(
  () => request.scope,
  () => {
    request.department = "";
    request.site_id = null;
  },
);

function errorText(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail === "OPEN_REQUEST_ALREADY_EXISTS") return "같은 업무의 처리 중 신청이 이미 있습니다.";
    if (detail === "SITE_REQUIRED") return "등록된 소속 현장을 선택해 주세요.";
    if (detail === "INVALID_DEPARTMENT" || detail === "DEPARTMENT_REQUIRED") return "본사·현장 구분에 맞는 부서를 선택해 주세요.";
    if (typeof detail === "string" && detail) return detail;
  }
  return "요청을 처리할 수 없습니다. 관리자에게 문의해 주세요.";
}

function reset(next: "find" | "request") {
  mode.value = next; errorMessage.value = ""; resultMessage.value = ""; requestNo.value = ""; foundAccounts.value = [];
}

async function findAccount() {
  loading.value = true; errorMessage.value = "";
  try {
    const { data } = await api.post("/auth/issue-accounts", find);
    resultMessage.value = data.message;
    foundAccounts.value = data.accounts || [];
  } catch (error) { errorMessage.value = errorText(error); }
  finally { loading.value = false; }
}

async function submitRequest() {
  loading.value = true; errorMessage.value = "";
  try {
    const { data } = await api.post("/account-requests/public", request);
    resultMessage.value = data.message; requestNo.value = data.request_no;
  } catch (error) { errorMessage.value = errorText(error); }
  finally { loading.value = false; }
}

onMounted(async () => {
  optionsLoading.value = true;
  try {
    options.value = await fetchAccountRequestOptions();
  } catch {
    errorMessage.value = "부서·현장 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  } finally {
    optionsLoading.value = false;
  }
});
</script>

<style scoped>
.request-backdrop{position:fixed;inset:0;z-index:500;display:grid;place-items:center;padding:16px;background:rgba(15,23,42,.55)}
.request-modal{width:min(680px,100%);max-height:92vh;overflow:auto;background:#fff;border-radius:18px;padding:22px;box-shadow:0 24px 70px rgba(15,23,42,.3)}
.request-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.request-head h2{margin:3px 0 0;font-size:22px}.eyebrow{margin:0;color:#2563eb;font-weight:700;font-size:12px}
.close-btn{border:0;background:none;font-size:28px;cursor:pointer}.mode-tabs,.scope-tabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:18px 0}
.mode-tabs button,.scope-tabs button{padding:11px;border:1px solid #cbd5e1;background:#f8fafc;border-radius:10px}.mode-tabs .active,.scope-tabs .active{background:#e0ecff;border-color:#2563eb;color:#174ea6;font-weight:700}
.request-form{display:grid;gap:13px}.help{margin:0;padding:12px;background:#f1f5f9;border-radius:10px;color:#475569;line-height:1.55}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:grid;gap:6px;font-weight:650;color:#334155}input,select,textarea{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:9px;padding:10px;font:inherit}.consent{display:flex;grid-template-columns:auto 1fr;align-items:start;font-weight:500}.consent input{width:auto;margin-top:3px}
.wide{grid-column:1 / -1}
.primary{border:0;border-radius:10px;padding:11px 16px;background:#1d4ed8;color:white;font-weight:700;cursor:pointer}.primary:disabled{opacity:.55}.error{color:#b91c1c;background:#fef2f2;padding:10px;border-radius:8px}.result-card{display:grid;gap:10px;margin-top:18px;padding:18px;border-radius:12px;background:#eff6ff}.result-card p{margin:0}
@media(max-width:640px){.request-modal{padding:16px}.form-grid{grid-template-columns:1fr}.request-head h2{font-size:19px}.mode-tabs button{font-size:13px;padding:9px 6px}}
</style>
