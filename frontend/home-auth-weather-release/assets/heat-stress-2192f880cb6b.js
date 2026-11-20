const api='https://api.besma.co.kr',token=localStorage.getItem('besma_token');
const $=id=>document.getElementById(id),node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;if(cls)el.className=cls;return el;};
let user=null,weather=null,siteMode=false,weatherSequence=0,policySequence=0,confirmedRecord=null,saveBusy=false;
let coordinates={latitude:37.5665,longitude:126.9780};
function status(text){$('heat-status').textContent=text;}
function current(){return token&&localStorage.getItem('besma_token')===token;}
async function request(path,options={}){
  if(!current())throw Error('로그인을 다시 확인해 주세요.');
  const response=await fetch(api+path,{...options,headers:{Authorization:'Bearer '+token,...options.body?{'Content-Type':'application/json'}:{},...options.headers},cache:'no-store',signal:options.signal||AbortSignal.timeout(25000)});
  if(!current())throw Error('로그인 계정이 변경되었습니다.');
  if(!response.ok){let detail='';try{const body=await response.json();if(typeof body.detail==='string')detail=body.detail;}catch{}if(response.status===401){location.replace('/login?form=1');throw Error('로그인이 필요합니다.');}throw Error(detail||'처리하지 못했습니다. 다시 확인해 주세요.');}
  return response;
}
async function json(path,options){return(await request(path,options)).json();}
const number=(value,suffix,digits=1)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits)+suffix:'확인 중';
function kst(value){if(!value)return '시각 확인 중';const parsed=new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value)?value:value+'+09:00');return Number.isFinite(parsed.getTime())?parsed.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false}):'시각 확인 중';}
function localDateTime(at=new Date()){const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(at).map(p=>[p.type,p.value]));return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;}
async function loadWeather(){
  const seq=++weatherSequence;$('weather-refresh').disabled=true;status('기상자료를 확인하고 있습니다.');
  try{
    const params=new URLSearchParams(siteMode&&user.site_id&&!coordinates.gps?{site_id:String(user.site_id)}:{latitude:String(coordinates.latitude),longitude:String(coordinates.longitude)});
    const value=await json('/weather/location-overview?'+params);if(seq!==weatherSequence)return;
    if(!value.available||!value.current)throw Error('기상자료를 확인하지 못했습니다.');weather=value;const c=value.current;
    $('weather-location').textContent=value.location_name||'서울';$('weather-temperature').textContent=number(c.temperature_c,'℃');$('weather-apparent').textContent=number(c.provider_apparent_temperature_c,'℃');$('weather-humidity').textContent=number(c.relative_humidity_pct,'%',0);
    $('weather-source').replaceChildren(node('span',(value.source_label||'기상자료')+' · '+kst(c.observed_at)+' · 체감온도: Open-Meteo 기상자료 '));
    const credit=node('a','출처');credit.href='https://open-meteo.com/';credit.target='_blank';credit.rel='noopener';$('weather-source').append(credit);status('');
  }catch(error){if(seq===weatherSequence){weather=null;for(const id of ['weather-temperature','weather-apparent','weather-humidity'])$(id).textContent='확인 중';status(error.message);}}
  finally{if(seq===weatherSequence)$('weather-refresh').disabled=false;}
}
function signature(id,clearId){
  const canvas=$(id),ctx=canvas.getContext('2d');let drawing=false,ink=false;
  const point=event=>{const rect=canvas.getBoundingClientRect();return{x:(event.clientX-rect.left)*canvas.width/rect.width,y:(event.clientY-rect.top)*canvas.height/rect.height};};
  function clear(){ctx.clearRect(0,0,canvas.width,canvas.height);ink=false;}
  canvas.addEventListener('pointerdown',event=>{event.preventDefault();drawing=true;canvas.setPointerCapture(event.pointerId);const p=point(event);ctx.beginPath();ctx.arc(p.x,p.y,1.6,0,Math.PI*2);ctx.fillStyle='#152e42';ctx.fill();ctx.beginPath();ctx.moveTo(p.x,p.y);ink=true;});
  canvas.addEventListener('pointermove',event=>{if(!drawing)return;event.preventDefault();const p=point(event);ctx.lineWidth=2.4;ctx.lineCap='round';ctx.strokeStyle='#152e42';ctx.lineTo(p.x,p.y);ctx.stroke();});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(type,()=>{drawing=false;});
  $(clearId).onclick=clear;
  return{clear,data(){if(!ink)throw Error('서명란에 직접 서명해 주세요.');return canvas.toDataURL('image/png');}};
}
const recorder=signature('recorder-signature','clear-recorder'),confirmer=signature('confirmer-signature','clear-confirmer');
async function refreshPolicy(){
  const seq=++policySequence;const temperature=$('air-temperature').value,humidity=$('relative-humidity').value;
  if(temperature===''||humidity===''){$('record-policy').replaceChildren(node('p','기온과 습도를 입력하세요.'));return;}
  if(!$('air-temperature').checkValidity()||!$('relative-humidity').checkValidity())return;
  try{
    const value=await json('/heat-stress/policy?'+new URLSearchParams({air_temperature_c:temperature,relative_humidity_pct:humidity}));if(seq!==policySequence)return;
    $('record-policy').replaceChildren(node('strong','기록 체감온도 '+number(value.apparent_temperature_c,'℃')),node('p',value.risk_label||''),node('p',value.legal_guidance||''),node('p',value.company_guidance||''));
    const checked=new Set([...$('action-options').querySelectorAll('input:checked')].map(input=>input.value));$('action-options').replaceChildren();
    for(const action of value.action_options||[]){const label=node('label'),input=node('input');input.type='checkbox';input.value=action.code;input.checked=checked.has(action.code);label.append(input,document.createTextNode(action.label));$('action-options').append(label);}
  }catch(error){if(seq===policySequence){$('record-policy').replaceChildren(node('p','기록 체감온도를 확인하지 못했습니다.'));status(error.message);}}
}
function filterQuery(){const query=new URLSearchParams({limit:'100'});if($('date-from').value)query.set('date_from',$('date-from').value);if($('date-to').value)query.set('date_to',$('date-to').value);return query;}
async function download(path,name){
  try{const response=await request(path),blob=await response.blob();if(!current())return;const href=URL.createObjectURL(blob),link=node('a');link.href=href;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(href),30000);}catch(error){status(error.message);}
}
async function loadRecords(){
  $('records-refresh').disabled=true;
  try{
    const result=await json('/heat-stress/records?'+filterQuery());$('heat-records').replaceChildren();
    if(!result.items?.length){$('heat-records').append(node('p','조회기간에 기록된 내용이 없습니다.'));return;}
    for(const item of result.items){
      const row=node('article',null,'record-row'),info=node('div'),actions=node('div',null,'row-actions');
      info.append(node('h3',(item.site_name||'현장')+' · '+item.work_location),node('p',kst(item.measured_at)),node('p','기온 '+number(item.air_temperature_c,'℃')+' · 습도 '+number(item.relative_humidity_pct,'%',0)+' · 기록 체감온도 '+number(item.apparent_temperature_c,'℃')),node('p',(item.actual_action_labels||[]).join(', ')||'실제 조치 미입력'),node('span',item.status==='CONFIRMED'?'확인 완료':'확인 서명 대기','record-state'+(item.status==='CONFIRMED'?' confirmed':'')));
      const pdf=node('button','PDF');pdf.type='button';pdf.onclick=()=>void download('/heat-stress/records/'+item.id+'/pdf','체감온도기록_'+item.id+'.pdf');actions.append(pdf);
      if(siteMode&&item.status!=='CONFIRMED'){const button=node('button','확인 서명');button.type='button';button.onclick=()=>{confirmedRecord=item.id;$('confirm-record-label').textContent=item.work_location+' · '+kst(item.measured_at);$('confirmer-name').value=user.name||'';$('confirmer-title').value='';confirmer.clear();$('confirm-dialog').showModal();};actions.append(button);}
      row.append(info,actions);$('heat-records').append(row);
    }
  }catch(error){$('heat-records').replaceChildren(node('p','기록을 확인하지 못했습니다.'));status(error.message);}
  finally{$('records-refresh').disabled=false;}
}
$('heat-form').onsubmit=async event=>{
  event.preventDefault();if(!siteMode||saveBusy)return;saveBusy=true;$('save-record').disabled=true;
  try{
    const actions=[...$('action-options').querySelectorAll('input:checked')].map(input=>input.value);if(!actions.length)throw Error('실제 실시한 조치를 선택해 주세요.');
    const payload={measured_at:$('measured-at').value+':00+09:00',work_location:$('work-location').value.trim(),work_process:$('work-process').value.trim()||null,measurement_source:$('measurement-source').value,air_temperature_c:Number($('air-temperature').value),relative_humidity_pct:Number($('relative-humidity').value),actual_actions:actions,action_notes:$('action-notes').value.trim()||null,recorder_signature_data:recorder.data()};
    await json('/heat-stress/records',{method:'POST',body:JSON.stringify(payload)});recorder.clear();await loadRecords();status('서명한 기록을 저장했습니다.');
  }catch(error){status(error.message);}finally{saveBusy=false;$('save-record').disabled=false;}
};
$('confirm-form').onsubmit=async event=>{
  event.preventDefault();if(!siteMode||!confirmedRecord||$('confirm-record').disabled)return;$('confirm-record').disabled=true;
  try{await json('/heat-stress/records/'+confirmedRecord+'/confirm',{method:'POST',body:JSON.stringify({confirmer_name:$('confirmer-name').value.trim(),confirmer_title:$('confirmer-title').value.trim(),confirmer_signature_data:confirmer.data()})});$('confirm-dialog').close();await loadRecords();status('확인 서명을 저장했습니다.');}catch(error){status(error.message);}finally{$('confirm-record').disabled=false;}
};
$('close-confirm').onclick=()=>$('confirm-dialog').close();
$('weather-refresh').onclick=()=>void loadWeather();$('records-refresh').onclick=()=>void loadRecords();$('records-filter').onsubmit=event=>{event.preventDefault();void loadRecords();};
$('copy-weather').onclick=()=>{const c=weather?.current;if(typeof c?.temperature_c!=='number'||typeof c?.relative_humidity_pct!=='number'){status('기온과 습도를 먼저 확인해 주세요.');return;}const stamp=c.observed_at,at=new Date(typeof stamp==='string'&&(/[zZ]|[+-]\d\d:\d\d$/.test(stamp))?stamp:stamp+'+09:00');if(!Number.isFinite(at.getTime())||Date.now()-at.getTime()>7200000||at.getTime()-Date.now()>300000){status('최신 기상자료의 기준시각을 먼저 확인해 주세요.');return;}$('air-temperature').value=c.temperature_c;$('relative-humidity').value=c.relative_humidity_pct;$('measured-at').value=localDateTime(at);$('measurement-source').value='WEATHER_REFERENCE';void refreshPolicy();};
let policyTimer;for(const id of ['air-temperature','relative-humidity'])$(id).addEventListener('input',()=>{clearTimeout(policyTimer);policyTimer=setTimeout(()=>void refreshPolicy(),350);});
$('ledger-pdf').onclick=()=>{const query=filterQuery();query.delete('limit');void download('/heat-stress/ledger.pdf?'+query,'체감온도관리대장.pdf');};
$('weather-gps').onclick=()=>{if(!navigator.geolocation){status('위치를 확인할 수 없습니다.');return;}navigator.geolocation.getCurrentPosition(position=>{coordinates={latitude:position.coords.latitude,longitude:position.coords.longitude,gps:true};void loadWeather();},()=>status('위치 권한을 확인해 주세요. 현재 표시된 지역의 기상자료를 유지합니다.'),{timeout:10000,maximumAge:300000});};
window.addEventListener('storage',event=>{if((event.key==='besma_token'||event.key===null)&&!current())location.replace('/login?form=1');});
async function start(){
  if(!token){location.replace('/login?form=1');return;}
  try{user=await json('/auth/me');siteMode=['SITE','SITE_FUNCTIONAL_EVAL'].includes(user.role)&&!!user.site_id;$('record-section').hidden=!siteMode;$('record-scope').textContent=siteMode?'당 현장의 기록입니다.':'본사에서는 현장 기록을 조회합니다. 기록·서명은 현장 계정에서 진행합니다.';$('recorder-name').textContent=user.name||'';$('measured-at').value=localDateTime();const date=$('measured-at').value.slice(0,10);$('date-from').value=date.slice(0,7)+'-01';$('date-to').value=date;await Promise.allSettled([loadWeather(),loadRecords()]);}catch(error){status(error.message);}
}
void start();
