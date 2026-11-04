import {loadGovernmentDocuments,governmentTasks,governmentTaskHref} from '/assets/government-document-status.js';
import {restoreDocumentTaskView,mountDocumentTaskView} from '/assets/document-task-view.js';
const KEY='besma-home-document-tasks-v1',TTL=4*60*60*1000;
const validMonth=value=>typeof value==='string'&&/^20\d{2}-(0[1-9]|1[0-2])$/.test(value);
export function createHomeDocumentTasks({anchor,api,token,onNavigate,onSummary=()=>{}}){
 const node=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const host=node('details');host.id='today-document-tasks';host.className='government-document-tasks';host.hidden=true;anchor.after(host);
 let sequence=0,owner='',open=false,state=restoreDocumentTaskView(null),month='',monthExplicit=false,latest=null,view=null;
 const current=()=>!!token&&localStorage.getItem('besma_token')===token;
 const ready=crypto.subtle.digest('SHA-256',new TextEncoder().encode(token||'')).then(hash=>{owner=[...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('');try{const saved=JSON.parse(sessionStorage.getItem(KEY)||'null');if(saved?.owner===owner&&Date.now()-saved.at>=0&&Date.now()-saved.at<TTL){state=restoreDocumentTaskView(saved.state);open=saved.open===true;if(validMonth(saved.month)){month=saved.month;monthExplicit=saved.monthExplicit===true;}}}catch{}}).catch(()=>{});
 function remember(){if(!owner||!current())return;try{sessionStorage.setItem(KEY,JSON.stringify({owner,at:Date.now(),state,open,month,monthExplicit}));}catch{}}
 host.addEventListener('toggle',()=>{open=host.open;remember();});
 function clear(message){onSummary({state:"UNKNOWN"});sequence++;latest=null;view=null;host.hidden=false;host.removeAttribute('aria-busy');host.replaceChildren(node('summary','관급 문서 확인 필요'),node('p',message||'문서 현황을 다시 확인해 주세요.'));}
 function periodControls(){
  const controls=node('div');controls.className='document-task-controls document-month-controls';
  const group=node('div'),label=node('label','취합월'),input=node('input');input.id='home-document-month';input.type='month';input.value=validMonth(month)?month:'';label.htmlFor=input.id;
  function choose(value,explicit){if(!current()||!validMonth(value)||!latest)return;if(month!==value)state.selected='';month=value;monthExplicit=explicit;remember();refresh(latest.home,latest.role);}
  input.onchange=()=>{if(!validMonth(input.value)){input.value=validMonth(month)?month:'';input.setCustomValidity('취합월을 선택해 주세요.');input.reportValidity();return;}input.setCustomValidity('');choose(input.value,true);};group.append(label,input);
  const today=latest?.home?.date?.slice(0,7),reset=node('button','이번달');reset.id='home-document-current-month';reset.type='button';reset.disabled=!validMonth(today)||(!monthExplicit&&month===today);reset.onclick=()=>choose(today,false);controls.append(group,reset);return controls;
 }
 async function refresh(home,role){
  const pass=++sequence;onSummary({state:"LOADING"});latest={home,role};await ready;if(!current()||pass!==sequence)return;
  if(role&&!['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'].includes(role)){onSummary({state:'HIDDEN'});view=null;host.hidden=true;host.removeAttribute('aria-busy');host.replaceChildren();return;}
  const today=home?.date?.slice(0,7),nextMonth=validMonth(today)?today:'';if(!monthExplicit||!validMonth(month)){if(month!==nextMonth)state.selected='';month=nextMonth;monthExplicit=false;}
  host.hidden=false;if(view){view.summary.textContent='관급 문서 새로 확인 중';view.loading.hidden=false;}else host.replaceChildren(node('summary','관급 문서 확인 중'),periodControls());host.open=open;host.setAttribute('aria-busy','true');
  const codes=Array.isArray(home?.sites)?home.sites.filter(s=>s.is_government===true).map(s=>s.code):null;
  const snapshot=await loadGovernmentDocuments({api,token,month,codes,current:()=>current()&&pass===sequence});if(!snapshot||!current()||pass!==sequence)return;
  host.removeAttribute('aria-busy');if(snapshot.state==='NOT_APPLICABLE'){view=null;host.replaceChildren();onSummary({state:'HIDDEN'});host.hidden=true;remember();return;}
  const model=governmentTasks(snapshot);
  if(model.state!=='VERIFIED'){onSummary({state:'UNKNOWN'});view=null;host.replaceChildren();
   host.append(node('summary','관급 문서 확인 필요'),node('p',model.state==='FORBIDDEN'?'관급 문서 조회 권한을 확인해 주세요.':model.state==='AUTH_REQUIRED'?'로그인 후 확인해 주세요.':'관급 문서 현황을 불러오지 못했습니다.'));
   if(!['FORBIDDEN','AUTH_REQUIRED'].includes(model.state)){host.append(periodControls());const retry=node('button','다시 확인');retry.type='button';retry.onclick=()=>latest&&refresh(latest.home,latest.role);host.append(retry);}remember();return;
  }
  onSummary({state:'VERIFIED',count:model.tasks.length,unknown:model.unknown.length,overdue:model.tasks.filter(x=>x.overdue===true).length,scope:month+' 관급공사 취합 원장'});
  const missing=model.tasks.filter(x=>x.status==='NOT_SUBMITTED').length,review=model.tasks.filter(x=>['SUBMITTED','IN_REVIEW','UNDER_REVIEW','RESUBMITTED'].includes(x.status)).length,rejected=model.tasks.filter(x=>x.status==='REJECTED').length;
  const options={tasks:model.tasks,unknown:model.unknown,month,sites:home.sites,state,buildHref:(task,value)=>governmentTaskHref(task,value,'/company.html'),onChange:remember,onNavigate:()=>{remember();onNavigate();},current};
  if(!view){
   host.replaceChildren();const summary=node('summary'),period=periodControls(),counts=node('p'),loading=node('p','새로 확인 중 · 이전 조회 내용을 표시합니다.');loading.hidden=true;host.append(summary,period,counts,loading);
   const editor=mountDocumentTaskView(host,options);view={summary,period,counts,loading,editor};
   host.append(node('small','관급공사 취합 원장 기준 · 제출기한이 확인된 문서만 기한 초과로 표시합니다.'));
  }else view.editor.update(options);
  view.summary.textContent='관급 문서 확인 '+model.tasks.length+'건 · 미확인 '+model.unknown.length+'건';view.counts.textContent=month+' · 미제출 '+missing+' · 검토 '+review+' · 반려 '+rejected;view.loading.hidden=true;
  const monthInput=view.period.querySelector('input');if(monthInput.value!==month)monthInput.value=month;view.period.querySelector('button').disabled=!validMonth(today)||(!monthExplicit&&month===today);
  remember();
 }
 addEventListener('pagehide',remember);addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null){try{sessionStorage.removeItem(KEY);}catch{}clear('로그인 계정이 변경되었습니다. 화면을 다시 열어 주세요.');}});
 return {refresh,clear};
}
