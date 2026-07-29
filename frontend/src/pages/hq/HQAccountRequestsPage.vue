<template>
  <section class="page">
    <header><p class="eyebrow">관리자</p><h1>계정·업무 권한 신청 관리</h1><p>업무 구분에 따른 최소권한 추천을 확인하고 승인·반려합니다.</p></header>
    <div class="toolbar"><select v-model="statusFilter" @change="load"><option value="">전체</option><option v-for="s in statuses" :key="s">{{ s }}</option></select><button @click="load">새로고침</button></div>
    <div class="cards">
      <article v-for="item in items" :key="item.id" class="card">
        <div class="card-head"><div><strong>{{ item.name }}</strong> <span>{{ item.request_no }}</span></div><b>{{ item.status }}</b></div>
        <dl><div><dt>신청</dt><dd>{{ item.request_type }} / {{ item.work_category }}</dd></div><div><dt>소속</dt><dd>{{ item.company_name }} · {{ item.department || "-" }}</dd></div><div><dt>현장</dt><dd>{{ item.site_name || item.site_code || "-" }}</dd></div><div><dt>명부/중복</dt><dd>{{ item.roster_match_status }} / {{ item.duplicate_candidate_ids.join(", ") || "-" }}</dd></div><div><dt>현재/추천</dt><dd>{{ item.current_role_snapshot || "-" }} → {{ item.recommended_role || "조직 확인 필요" }}</dd></div></dl>
        <p class="reason">{{ item.request_reason }}</p>
        <div v-if="open(item.status)" class="decision">
          <select v-model="draft[item.id].approved_role"><option value="">추천 역할 사용</option><option v-for="r in roles" :key="r">{{ r }}</option></select>
          <input v-model="draft[item.id].approved_site_id" type="number" placeholder="현장 ID" />
          <input v-model="draft[item.id].comment" placeholder="처리 의견" />
          <label><input v-model="draft[item.id].replace_existing_role" type="checkbox" /> 기존 역할 교체 확인</label>
          <button @click="act(item,'START_REVIEW')">검토중</button><button @click="act(item,'REQUEST_INFO')">보완요청</button>
          <button class="approve" @click="act(item,'APPROVE')">승인</button><button class="reject" @click="act(item,'REJECT')">반려</button>
        </div>
      </article>
    </div>
    <div v-if="temporary" class="temporary"><h2>임시 로그인 정보</h2><p>이 화면에서 한 번만 표시됩니다.</p><code>{{ temporary.login }} / {{ temporary.password }}</code><button @click="temporary=null">확인 후 닫기</button></div>
    <p v-if="message" class="message">{{ message }}</p>
  </section>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"; import { api } from "@/services/api";
const statuses=["REQUESTED","IN_REVIEW","NEEDS_INFO","APPROVED","REJECTED","CANCELLED","EXPIRED"]; const roles=["HQ_SAFE","HQ_BUDGET_ESTIMATE","HQ_OUTSOURCING_PURCHASE","FUNCTIONAL_EVAL_VIEWER","SITE","SITE_FUNCTIONAL_EVAL","HQ_OTHER"];
const statusFilter=ref("");const items=ref<any[]>([]);const draft=reactive<Record<number,any>>({});const message=ref("");const temporary=ref<any>(null);
const open=(s:string)=>["REQUESTED","IN_REVIEW","NEEDS_INFO"].includes(s);
async function load(){const {data}=await api.get("/account-requests/admin",{params:statusFilter.value?{status:statusFilter.value}:{}});items.value=data;for(const i of data)draft[i.id]??={approved_role:"",approved_site_id:"",comment:"",replace_existing_role:false}}
async function act(item:any,action:string){message.value="";try{const d=draft[item.id];const {data}=await api.patch(`/account-requests/admin/${item.id}`,{action,comment:d.comment||undefined,approved_role:d.approved_role||undefined,approved_site_id:d.approved_site_id?Number(d.approved_site_id):undefined,replace_existing_role:d.replace_existing_role});if(data.temporary_password)temporary.value={login:data.temporary_login_id,password:data.temporary_password};await load()}catch(e:any){message.value=e?.response?.data?.detail||"처리에 실패했습니다."}}
onMounted(load);
</script>
<style scoped>
.page{display:grid;gap:16px}.eyebrow{color:#2563eb;font-weight:700}.page h1{margin:3px 0}.toolbar{display:flex;gap:8px}.toolbar select,.toolbar button,.decision input,.decision select,.decision button{padding:9px;border:1px solid #cbd5e1;border-radius:8px}.cards{display:grid;gap:12px}.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px}.card-head{display:flex;justify-content:space-between}.card-head span{color:#64748b;font-size:13px}dl{display:grid;grid-template-columns:1fr 1fr;gap:8px}dl div{display:grid;grid-template-columns:80px 1fr}dt{color:#64748b}.reason{background:#f8fafc;padding:10px}.decision{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.decision label{font-size:13px}.approve{background:#166534;color:#fff}.reject{background:#991b1b;color:#fff}.temporary{position:fixed;inset:auto 20px 20px auto;background:#fff7ed;border:2px solid #f97316;padding:18px;border-radius:12px;box-shadow:0 12px 40px #0003}.temporary code{display:block;font-size:18px;margin:10px 0}.message{color:#b91c1c}@media(max-width:700px){dl{grid-template-columns:1fr}.decision>*{width:100%}.temporary{inset:auto 10px 10px 10px}}
</style>
