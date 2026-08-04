<template>
  <div class="hq-heat">
    <header class="head">
      <div><p>전 현장 폭염관리</p><h1>체감온도 기록 현황</h1><small>미작성·고온·조치 필요·확인 대기를 한 화면에서 확인합니다.</small></div>
      <label>기준일 <input v-model="targetDate" type="date" @change="loadAll" /></label>
    </header>
    <section class="summary">
      <article><span>오늘 기록</span><strong>{{ summary.total_record_count }}</strong></article>
      <article><span>미작성 현장</span><strong>{{ summary.missing_site_count }}</strong></article>
      <article><span>31℃ 이상</span><strong>{{ summary.at_or_above_31_count }}</strong></article>
      <article class="hot"><span>33℃ 이상</span><strong>{{ summary.at_or_above_33_count }}</strong></article>
      <article class="alert"><span>조치 확인 필요</span><strong>{{ summary.action_required_count }}</strong></article>
      <article><span>관리자 확인 대기</span><strong>{{ summary.confirm_pending_count }}</strong></article>
    </section>
    <section class="panel">
      <div class="filters">
        <label>상태<select v-model="statusFilter" @change="loadRecords"><option value="">전체</option><option value="CONFIRM_PENDING">확인 대기</option><option value="CONFIRMED">확인 완료</option></select></label>
        <button v-if="canExportLedger" class="ledger" type="button" :disabled="ledgerDownloading" title="전체 기간 기록을 날짜별 관리대장으로 출력" @click="downloadLedger">
          {{ ledgerDownloading ? "관리대장 생성 중" : "체감온도관리대장" }}
        </button>
        <button type="button" @click="loadAll">새로고침</button>
      </div>
      <p v-if="ledgerError" class="error">{{ ledgerError }}</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>현장</th><th>일시</th><th>장소</th><th>온도/습도</th><th>체감온도</th><th>실제 조치</th><th>상태</th><th></th></tr></thead>
          <tbody>
            <tr v-for="row in records" :key="row.id">
              <td><strong>{{ row.site_name }}</strong></td><td>{{ formatDate(row.measured_at) }}</td><td>{{ row.work_location }}</td>
              <td>{{ row.air_temperature_c.toFixed(1) }}℃ / {{ row.relative_humidity_pct.toFixed(0) }}%</td>
              <td><span :class="['risk',row.risk_level.toLowerCase()]">{{ row.apparent_temperature_c.toFixed(1) }}℃ · {{ row.risk_label }}</span></td>
              <td>{{ row.actual_action_labels.join(", ") || "미입력" }}<b v-if="row.action_compliance==='ACTION_REQUIRED'">조치 확인 필요</b></td>
              <td>{{ row.status==='CONFIRMED' ? '확인 완료' : '확인 대기' }}</td>
              <td><button type="button" @click="downloadPdf(row)">PDF</button></td>
            </tr>
            <tr v-if="!records.length"><td colspan="8" class="empty">해당 기록이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { downloadBlobAsFile } from "@/utils/blobDownload";
interface Row{id:number;site_name:string;measured_at:string;work_location:string;air_temperature_c:number;relative_humidity_pct:number;apparent_temperature_c:number;risk_level:string;risk_label:string;actual_action_labels:string[];action_compliance:string;status:string}
const auth=useAuthStore();
const today=()=>new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
const targetDate=ref(today()),statusFilter=ref(""),records=ref<Row[]>([]);
const ledgerDownloading=ref(false),ledgerError=ref("");
const canExportLedger=computed(()=>["HQ_SAFE","HQ_SAFE_ADMIN","SUPER_ADMIN","ACCIDENT_ADMIN"].includes(auth.user?.role||""));
const summary=reactive({total_record_count:0,missing_site_count:0,at_or_above_31_count:0,at_or_above_33_count:0,action_required_count:0,confirm_pending_count:0});
async function loadSummary(){Object.assign(summary,(await api.get("/heat-stress/hq-summary",{params:{target_date:targetDate.value}})).data)}
async function loadRecords(){const res=await api.get("/heat-stress/records",{params:{date_from:targetDate.value,date_to:targetDate.value,status:statusFilter.value||undefined,limit:500}});records.value=res.data.items}
async function loadAll(){await Promise.all([loadSummary(),loadRecords()])}
function formatDate(v:string){return new Date(v).toLocaleString("ko-KR",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})}
async function downloadPdf(row:Row){const res=await api.get(`/heat-stress/records/${row.id}/pdf`,{responseType:"blob"});downloadBlobAsFile(res.data,`${row.site_name}_체감온도기록_${row.id}.pdf`)}
async function downloadLedger(){ledgerDownloading.value=true;ledgerError.value="";try{const res=await api.get("/heat-stress/ledger.pdf",{responseType:"blob"});downloadBlobAsFile(res.data,"체감온도관리대장_전체기간.pdf")}catch(e:any){ledgerError.value=e?.response?.data?.detail||"체감온도관리대장을 생성하지 못했습니다."}finally{ledgerDownloading.value=false}}
onMounted(loadAll);
</script>

<style scoped>
.hq-heat{display:grid;gap:18px}.head,.filters{display:flex;justify-content:space-between;align-items:center;gap:15px}.head p{color:#0f766e;font-weight:800;margin:0}.head h1{margin:4px 0}.head small{color:#64748b}.head label,.filters label{display:flex;gap:8px;align-items:center;font-weight:700}.summary{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}.summary article{background:#fff;border:1px solid #dbe4ee;border-radius:14px;padding:16px;display:flex;flex-direction:column}.summary span{color:#64748b;font-size:13px}.summary strong{font-size:29px}.summary .hot{background:#fff7ed}.summary .alert{background:#fef2f2}.panel{background:#fff;border:1px solid #dbe4ee;border-radius:16px;padding:18px}.filters{justify-content:flex-end;margin-bottom:12px}input,select{padding:8px;border:1px solid #cbd5e1;border-radius:8px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:1000px}th,td{padding:11px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:13px}th{background:#f8fafc}.risk{white-space:nowrap;padding:5px 8px;border-radius:999px;background:#dcfce7;font-weight:800}.risk.caution,.risk.warning{background:#ffedd5}.risk.danger{background:#fee2e2}td b{display:block;color:#b91c1c;margin-top:4px}.empty{text-align:center;color:#64748b;padding:30px}.error{margin:0 0 12px;color:#b91c1c;font-weight:700}button{border:0;border-radius:8px;padding:8px 11px;background:#0f766e;color:white;font-weight:800}button.ledger{background:#1d4ed8}button:disabled{opacity:.6}@media(max-width:1100px){.summary{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){.head{align-items:flex-start;flex-direction:column}.summary{grid-template-columns:repeat(2,1fr)}}
</style>
