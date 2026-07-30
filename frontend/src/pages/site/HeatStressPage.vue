<template>
  <div class="heat-page">
    <LocationWeatherOverview
      :site-id="auth.effectiveSiteId"
      :read-only="false"
      auto-apply
      @use-current="useWeatherValues"
    />

    <header class="page-head">
      <div><p class="eyebrow">온열질환 예방</p><h1>체감온도 기록</h1><p>온도·습도를 입력하면 체감온도와 필요 조치를 자동 안내합니다.</p></div>
      <button class="secondary" type="button" @click="loadRecords">새로고침</button>
    </header>

    <p v-if="auth.isRolePreviewActive" class="preview-help">
      읽기 전용 검증모드입니다. 화면 입력과 체감온도 계산은 시험할 수 있지만 기록 저장과 서명은 전송되지 않습니다.
    </p>

    <section class="panel form-panel">
      <h2>새 기록</h2>
      <div class="form-grid">
        <label><span>점검 일시</span><input v-model="form.measured_at" type="datetime-local" /></label>
        <label><span>측정 구분</span><select v-model="form.measurement_source"><option value="ON_SITE">현장 실측</option><option value="KMA_REFERENCE">기상청 자료</option><option value="WEATHER_REFERENCE">위치 기반 기상 참고값</option></select></label>
        <label><span>작업장소</span><input v-model="form.work_location" placeholder="예: 지상 3층 외부" /></label>
        <label><span>공정</span><input v-model="form.work_process" placeholder="예: 배관 설치" /></label>
        <label><span>온도(℃)</span><input v-model.number="form.air_temperature_c" type="number" inputmode="decimal" step="0.1" min="-20" max="60" /></label>
        <label><span>습도(%)</span><input v-model.number="form.relative_humidity_pct" type="number" inputmode="decimal" step="1" min="0" max="100" /></label>
      </div>
      <div class="temperature-result" :class="policy.risk_level.toLowerCase()">
        <div><small>자동 계산 체감온도</small><strong>{{ apparentTemperature.toFixed(1) }}℃</strong></div>
        <span class="risk">{{ policy.risk_label }}</span>
      </div>
      <div class="guidance">
        <p><strong>법정 필요조치</strong>{{ policy.legal_guidance }}</p>
        <p><strong>회사 안내</strong>{{ policy.company_guidance }}</p>
        <p class="notice">자동 안내는 실시 완료 기록이 아닙니다. 실제 실시한 조치를 아래에서 선택하세요.</p>
      </div>
      <fieldset>
        <legend>실제 실시조치</legend>
        <p class="action-default-note">체감온도 구간별 기본 조치입니다. 실제 실시한 내용과 다르면 서명 전에 수정하세요.</p>
        <label v-for="option in actionOptions" :key="option.code" class="check">
          <input v-model="form.actual_actions" type="checkbox" :value="option.code" />{{ option.label }}
        </label>
      </fieldset>
      <label class="wide"><span>특이사항·휴식시간 등</span><textarea v-model="form.action_notes" rows="3" placeholder="예: 13:30~13:50 휴식, 옥외작업 중지"></textarea></label>
      <div v-if="showRecorderSignature" class="signature-box">
        <h3>점검자 서명</h3>
        <p>{{ auth.user?.name }}님이 입력 내용과 실제 조치를 확인한 뒤 직접 서명하세요.</p>
        <SignaturePad ref="recorderPad" :height="180" />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions">
        <button v-if="!showRecorderSignature" type="button" :disabled="auth.isRolePreviewActive" @click="openSignature">입력 확인 및 서명</button>
        <button v-else type="button" :disabled="saving || auth.isRolePreviewActive" @click="saveRecord">{{ saving ? "저장 중…" : "서명하고 기록 확정" }}</button>
      </div>
    </section>

    <section class="panel">
      <div class="section-head"><h2>최근 기록</h2><span>{{ records.length }}건</span></div>
      <div v-if="!records.length" class="empty">아직 기록이 없습니다.</div>
      <div v-if="records.length" class="record-table-wrap">
        <table class="record-table">
          <thead>
            <tr>
              <th>측정일시·작성자</th>
              <th>온도</th>
              <th>습도</th>
              <th>체감온도</th>
              <th>조치사항</th>
              <th>확인</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in records" :key="row.id">
              <tr>
                <td><strong>{{ formatDate(row.measured_at) }}</strong><small>{{ row.recorder_name }} · {{ row.work_location }}</small></td>
                <td>{{ row.air_temperature_c.toFixed(1) }}℃</td>
                <td>{{ row.relative_humidity_pct.toFixed(0) }}%</td>
                <td><strong>{{ row.apparent_temperature_c.toFixed(1) }}℃</strong><span :class="['badge', row.risk_level.toLowerCase()]">{{ row.risk_label }}</span></td>
                <td>
                  {{ row.actual_action_labels.join(", ") || "실제 조치 미입력" }}
                  <small v-if="row.action_compliance === 'ACTION_REQUIRED'" class="warning">추가 조치 확인 필요</small>
                </td>
                <td>
                  <span class="badge status">{{ row.status === 'CONFIRMED' ? '확인 완료' : '확인 대기' }}</span>
                  <div class="record-actions">
                    <button class="secondary" type="button" :disabled="auth.isRolePreviewActive" @click="downloadPdf(row)">PDF</button>
                    <button v-if="row.status !== 'CONFIRMED' && canShowManagerConfirm" type="button" :disabled="auth.isRolePreviewActive" @click="confirmingId = confirmingId === row.id ? null : row.id">확인 서명</button>
                  </div>
                </td>
              </tr>
              <tr v-if="confirmingId === row.id">
                <td colspan="6">
                  <div class="confirm-box">
          <div class="form-grid compact">
            <label><span>확인자 성명</span><input v-model="confirmForm.name" /></label>
            <label><span>직책</span><select v-model="confirmForm.title"><option>현장소장</option><option>관리감독자</option><option>안전관리자</option><option>기타 현장관리자</option></select></label>
          </div>
          <SignaturePad ref="confirmerPad" :height="160" />
          <button type="button" :disabled="confirming" @click="confirmRecord(row.id)">확인 서명 완료</button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
        </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import SignaturePad from "@/components/SignaturePad.vue";
import LocationWeatherOverview from "@/components/weather/LocationWeatherOverview.vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { downloadBlobAsFile } from "@/utils/blobDownload";

interface HeatRecord { id:number; measured_at:string; work_location:string; work_process?:string|null; recorder_name:string; air_temperature_c:number; relative_humidity_pct:number; apparent_temperature_c:number; risk_level:string; risk_label:string; status:string; action_compliance:string; actual_action_labels:string[]; site_name?:string }
const actionOptions = [
  {code:"WATER",label:"물 제공 및 섭취"},{code:"SHADE_COOLING",label:"그늘·냉방장소 제공"},{code:"VENTILATION",label:"통풍·환기"},
  {code:"REST",label:"휴식 실시"},{code:"WORK_TIME_ADJUSTMENT",label:"작업시간 조정"},{code:"COOLING_GEAR",label:"개인 냉방장구 지급"},
  {code:"WORK_STOP",label:"옥외작업 중지"},{code:"HEALTH_MONITORING",label:"건강상태 확인"},{code:"NOT_IMPLEMENTED",label:"필요조치 미실시"},{code:"OTHER",label:"기타"},
];
const auth=useAuthStore(); const records=ref<HeatRecord[]>([]); const saving=ref(false); const confirming=ref(false); const error=ref(""); const showRecorderSignature=ref(false); const confirmingId=ref<number|null>(null);
const canShowManagerConfirm=computed(()=>auth.effectivePersona!=="SITE_STAFF");
const recorderPad=ref<InstanceType<typeof SignaturePad>|null>(null); const confirmerPad=ref<InstanceType<typeof SignaturePad>|null>(null);
const nowLocal=()=>{const d=new Date(Date.now()-new Date().getTimezoneOffset()*60000);return d.toISOString().slice(0,16)};
const form=reactive({measured_at:nowLocal(),measurement_source:"ON_SITE",work_location:"",work_process:"",air_temperature_c:30,relative_humidity_pct:60,actual_actions:[] as string[],action_notes:""});
const confirmForm=reactive({name:"",title:"현장소장"});
function apparent(t:number,rh:number){const tw=t*Math.atan(.151977*Math.sqrt(rh+8.313659))+Math.atan(t+rh)-Math.atan(rh-1.67633)+.00391838*Math.pow(rh,1.5)*Math.atan(.023101*rh)-4.686035;return Math.round((-0.2442+.55399*tw+.45535*t-.0022*tw*tw+.00278*tw*t+3)*10)/10}
const apparentTemperature=computed(()=>apparent(Number(form.air_temperature_c)||0,Number(form.relative_humidity_pct)||0));
const policy=computed(()=>{const v=apparentTemperature.value;if(v>=38)return{risk_level:"DANGER",risk_label:"극심한 폭염",legal_guidance:"체감온도 33℃ 이상: 매 2시간 이내 20분 이상 휴식이 필요합니다.",company_guidance:"긴급작업 외 옥외작업 중지와 건강상태 즉시 확인을 권고합니다."};if(v>=35)return{risk_level:"WARNING",risk_label:"경고",legal_guidance:"체감온도 33℃ 이상: 매 2시간 이내 20분 이상 휴식이 필요합니다.",company_guidance:"고강도·14~17시 옥외작업을 조정하고 냉방·건강확인을 강화하세요."};if(v>=33)return{risk_level:"CAUTION",risk_label:"주의",legal_guidance:"체감온도 33℃ 이상: 매 2시간 이내 20분 이상 휴식이 필요합니다.",company_guidance:"물·그늘·휴식과 취약근로자 건강상태를 확인하세요."};if(v>=31)return{risk_level:"INTEREST",risk_label:"관심",legal_guidance:"폭염작업에 해당할 수 있어 체감온도와 실제 조치를 일자별로 기록해야 합니다.",company_guidance:"물·그늘·환기·휴식·작업시간 조정 중 실제 조치를 확인하세요."};return{risk_level:"NORMAL",risk_label:"일반",legal_guidance:"체감온도를 확인하고 기본 예방조치를 유지하세요.",company_guidance:"물 제공, 환기 및 건강상태를 확인하세요."}});
function defaultActionsForRisk(level:string){if(level==="DANGER")return["WATER","SHADE_COOLING","REST","WORK_TIME_ADJUSTMENT","COOLING_GEAR","WORK_STOP","HEALTH_MONITORING"];if(level==="WARNING")return["WATER","SHADE_COOLING","REST","WORK_TIME_ADJUSTMENT","COOLING_GEAR","HEALTH_MONITORING"];if(level==="CAUTION")return["WATER","SHADE_COOLING","REST","HEALTH_MONITORING"];if(level==="INTEREST")return["WATER","SHADE_COOLING","VENTILATION","HEALTH_MONITORING"];return["WATER","VENTILATION"]}
watch(()=>policy.value.risk_level,(level,previous)=>{if(level!==previous)form.actual_actions=defaultActionsForRisk(level)},{immediate:true});
function openSignature(){error.value="";if(!form.work_location.trim()){error.value="작업장소를 입력하세요.";return}showRecorderSignature.value=true;nextTick(()=>recorderPad.value?.clear())}
async function saveRecord(){if(!recorderPad.value?.hasInk()){error.value="점검자 서명을 직접 입력하세요.";return}saving.value=true;error.value="";try{await api.post("/heat-stress/records",{...form,recorder_signature_data:recorderPad.value.toDataUrl()});Object.assign(form,{measured_at:nowLocal(),actual_actions:defaultActionsForRisk(policy.value.risk_level),action_notes:""});showRecorderSignature.value=false;await loadRecords()}catch(e:any){error.value=e?.response?.data?.detail||"기록 저장에 실패했습니다."}finally{saving.value=false}}
async function loadRecords(){const res=await api.get("/heat-stress/records",{params:{limit:100,site_id:auth.effectiveSiteId||undefined}});records.value=res.data.items;const latest=records.value[0];if(latest){if(!form.work_location.trim())form.work_location=latest.work_location||"";if(!form.work_process.trim())form.work_process=latest.work_process||""}}
function useWeatherValues(payload:{temperature:number|null;humidity:number|null;source:string}){if(payload.temperature!=null)form.air_temperature_c=Number(payload.temperature);if(payload.humidity!=null)form.relative_humidity_pct=Number(payload.humidity);form.measurement_source=payload.source.startsWith("KMA")?"KMA_REFERENCE":"WEATHER_REFERENCE"}
function formatDate(v:string){return new Date(v).toLocaleString("ko-KR",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})}
async function downloadPdf(row:HeatRecord){const res=await api.get(`/heat-stress/records/${row.id}/pdf`,{responseType:"blob"});downloadBlobAsFile(res.data,`${row.site_name||"현장"}_체감온도기록_${row.id}.pdf`)}
async function confirmRecord(id:number){if(!confirmForm.name.trim()){error.value="확인자 성명을 입력하세요.";return}if(!confirmerPad.value?.hasInk()){error.value="확인자 서명을 직접 입력하세요.";return}confirming.value=true;try{await api.post(`/heat-stress/records/${id}/confirm`,{confirmer_name:confirmForm.name,confirmer_title:confirmForm.title,confirmer_signature_data:confirmerPad.value.toDataUrl()});confirmingId.value=null;confirmForm.name="";await loadRecords()}catch(e:any){error.value=e?.response?.data?.detail||"확인 서명에 실패했습니다."}finally{confirming.value=false}}
onMounted(loadRecords);
</script>

<style scoped>
.heat-page{max-width:1120px;margin:0 auto;display:grid;gap:18px}.page-head,.section-head,.record-actions,.actions{display:flex;justify-content:space-between;align-items:center;gap:12px}.eyebrow{color:#0f766e;font-weight:800;margin:0}.page-head h1{margin:3px 0}.page-head p:last-child{color:#64748b;margin:0}.panel{background:#fff;border:1px solid #dbe4ee;border-radius:18px;padding:22px}.panel h2{margin-top:0}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.form-grid label,.wide{display:flex;flex-direction:column;gap:6px;font-weight:700}input,select,textarea{border:1px solid #cbd5e1;border-radius:10px;padding:11px;background:#fff;font:inherit}.temperature-result{margin:18px 0;padding:18px;border-radius:15px;background:#f0fdfa;display:flex;justify-content:space-between;align-items:center}.temperature-result div{display:flex;flex-direction:column}.temperature-result strong{font-size:34px}.risk,.badge{display:inline-block;padding:6px 11px;border-radius:999px;background:#dbeafe;font-weight:800}.temperature-result.caution,.temperature-result.warning{background:#fff7ed}.temperature-result.danger{background:#fef2f2}.guidance{border-left:4px solid #0f766e;padding:2px 14px;margin:16px 0}.guidance p{display:grid;grid-template-columns:110px 1fr;gap:8px}.notice{color:#b45309;font-size:13px}fieldset{border:1px solid #dbe4ee;border-radius:12px;padding:12px;margin:14px 0}.action-default-note{margin:4px 0 10px;color:#92400e;font-size:13px}.check{display:inline-flex;gap:6px;margin:7px 14px 7px 0}.signature-box,.confirm-box{background:#f8fafc;border-radius:14px;padding:16px;margin-top:16px}.error,.warning{color:#b91c1c;font-weight:700}.empty{text-align:center;color:#64748b;padding:25px}.badge.status{background:#e2e8f0}.record-table-wrap{overflow-x:auto}.record-table{width:100%;min-width:940px;border-collapse:collapse}.record-table th,.record-table td{padding:13px 11px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}.record-table th{background:#f8fafc;color:#475569;font-size:13px;white-space:nowrap}.record-table td>small,.record-table td>strong{display:block}.record-table td>small{margin-top:4px;color:#64748b}.record-table td .badge{margin-top:6px;font-size:12px}.record-actions{justify-content:flex-start;margin-top:8px}.record-actions button{padding:7px 10px;font-size:12px}.compact{margin-bottom:12px}button{border:0;border-radius:10px;background:#0f766e;color:#fff;padding:10px 15px;font-weight:800;cursor:pointer}button.secondary{background:#e2e8f0;color:#334155}button:disabled{opacity:.55}@media(max-width:768px){.heat-page{padding:2px}.page-head{align-items:flex-start}.panel{padding:15px;border-radius:14px}.form-grid{grid-template-columns:1fr}.guidance p{display:block}.guidance strong{display:block;margin-bottom:4px}}
.preview-help{margin:0;border:1px solid #fdba74;border-radius:12px;background:#fff7ed;color:#9a3412;padding:11px 14px;font-weight:800}
</style>
