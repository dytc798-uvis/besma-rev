<template>
  <section class="page">
    <header><p class="eyebrow">내 계정</p><h1>업무 권한 추가·변경 신청</h1><p>새 계정을 만들지 않고 현재 계정의 부서·현장·업무 권한 변경을 신청합니다.</p></header>
    <form class="card" @submit.prevent="submit">
      <div class="grid">
        <label>휴대전화<input v-model.trim="form.phone_mobile" required /></label>
        <label>소속 회사<input v-model.trim="form.company_name" required /></label>
        <label>본사·현장<select v-model="form.scope"><option value="HQ">본사</option><option value="SITE">현장</option></select></label>
        <label>부서<input v-model.trim="form.department" /></label>
        <label>업무 구분<select v-model="form.work_category">
          <option value="SAFETY">안전</option><option value="CONSTRUCTION">공사</option><option value="PUBLIC_WORKS">공무</option>
          <option value="BUDGET_ESTIMATE">예산·견적</option><option value="OUTSOURCING_PURCHASE">외주·구매</option>
          <option value="SITE">현장</option><option value="FUNCTIONAL_EVAL_VIEW">기능인 평가 조회</option><option value="OTHER">기타</option>
        </select></label>
        <label v-if="form.scope==='SITE'">현장코드<input v-model.trim="form.site_code" required /></label>
        <label v-if="form.scope==='SITE'">현장명<input v-model.trim="form.site_name" /></label>
      </div>
      <label>요청 사유<textarea v-model.trim="form.request_reason" required rows="4" /></label>
      <label>재직·업무관계 확인 메모<textarea v-model.trim="form.employment_evidence_note" rows="2" /></label>
      <label class="consent"><input v-model="form.privacy_consent" type="checkbox" /> 개인정보 수집·이용에 동의합니다.</label>
      <button class="primary" :disabled="loading || !form.privacy_consent">{{ loading ? "접수 중…" : "신청 접수" }}</button>
      <p v-if="message" class="message">{{ message }}</p>
    </form>
    <section class="card"><h2>내 신청 이력</h2>
      <div class="table-wrap"><table><thead><tr><th>신청번호</th><th>구분</th><th>상태</th><th>신청일</th><th>처리 의견</th></tr></thead>
      <tbody><tr v-for="item in items" :key="item.id"><td>{{ item.request_no }}</td><td>{{ item.work_category }}</td><td>{{ item.status }}</td><td>{{ item.created_at.slice(0,10) }}</td><td>{{ item.decision_comment || "-" }}</td></tr></tbody></table></div>
    </section>
  </section>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"; import { api } from "@/services/api"; import { useAuthStore } from "@/stores/auth";
const auth=useAuthStore(); const loading=ref(false); const message=ref(""); const items=ref<any[]>([]);
const form=reactive({request_type:"ACCESS_CHANGE",name:auth.user?.name||"",phone_mobile:"",company_name:"부현전기",scope:auth.user?.site_id?"SITE":"HQ",department:auth.user?.department||"",work_category:"SAFETY",site_code:"",site_name:"",request_reason:"",employment_evidence_note:"",privacy_consent:false});
async function load(){try{items.value=(await api.get("/account-requests/me")).data}catch{}}
async function submit(){loading.value=true;message.value="";try{const {data}=await api.post("/account-requests/me",form);message.value=`${data.message} 신청번호 ${data.request_no}`;await load()}catch(e:any){message.value=e?.response?.data?.detail||"신청에 실패했습니다."}finally{loading.value=false}}
onMounted(load);
</script>
<style scoped>
.page{display:grid;gap:18px;max-width:1000px;margin:auto}.page h1{margin:3px 0}.eyebrow{color:#2563eb;font-weight:700}.card{display:grid;gap:14px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{display:grid;gap:6px;font-weight:650}input,select,textarea{border:1px solid #cbd5e1;border-radius:8px;padding:10px;font:inherit}.consent{display:flex;gap:8px}.primary{border:0;border-radius:9px;padding:11px;background:#1d4ed8;color:#fff;font-weight:700}.message{padding:10px;background:#eff6ff}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap}@media(max-width:640px){.grid{grid-template-columns:1fr}}
</style>
