import {drawFunctionalReadiness} from '/assets/functional-readiness.js';
const readers=new Set(['HQ_OTHER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE','FUNCTIONAL_EVAL_VIEWER']);
const editors=new Set(['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN']);
const queries={overview:['/workspace/functional-overview','기존 평가 요약'],preparation:['/workspace/functional-readiness','평가 준비자료'],history:['/workspace/evaluation-status','기존 평가 이력']};
const entryLinks=[['평가·등급 조회','기능·안전 평가와 기존 등급 확인','/hq-safe/functional-eval'],['진행현황','평가·서명·승인 진행상황','/hq-safe/functional-eval-monitoring'],['포상·제재 및 검토·승인','안전보건실 검토와 포상·제재 처리','/hq-safe/functional-eval-rewards-sanctions'],['등급 보고서','기존 등급 통계·보고서 확인','/hq-safe/functional-eval/grade-report']];
function validOverview(d){
 if(!d||!Array.isArray(d.grades)||d.period!==null&&(!Number.isSafeInteger(d.period?.id)||d.period.id<1||typeof d.period.title!=='string'))return false;
 const seen=new Set();for(const r of d.grades){const key=r?.eval_type+':'+r?.grade_code;if(!['FUNCTIONAL','SAFETY'].includes(r?.eval_type)||![null,'S','A','B','C'].includes(r?.grade_code)||!Number.isSafeInteger(r?.count)||r.count<0||seen.has(key))return false;seen.add(key);}return d.period!==null||d.grades.length===0;
}
function validHistory(d){
 if(d?.state==='NO_PERIOD')return !Array.isArray(d.sites)||d.sites.length===0;
 if(d?.state!=='VERIFIED'||d.scope!=='REGISTERED_EVALUATION_TARGETS'||!Number.isSafeInteger(d.period?.id)||d.period.id<1||!Array.isArray(d.sites)||d.sites.length>10000)return false;
 const seen=new Set();for(const r of d.sites){if(typeof r?.site_code!=='string'||!r.site_code||r.site_code.length>100||/[\\/\u0000-\u001f\u007f]/.test(r.site_code)||seen.has(r.site_code)||!Number.isSafeInteger(r.total)||r.total<0||!Number.isSafeInteger(r.fully_complete)||r.fully_complete<0||r.fully_complete>r.total)return false;seen.add(r.site_code);}return true;
}
export function mountFunctionalWorkspace(host,{api,role,initialScope={},onScope=()=>{},isCurrent=()=>true}){
 const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
 if(!readers.has(role)&&!editors.has(role))return()=>{};
 let alive=true,scope=initialScope;const current=()=>alive&&isCurrent(),parts={};
 if(editors.has(role)){const nav=N('nav',null,'section-links');nav.setAttribute('aria-label','평가 업무');for(const[title,desc,href]of entryLinks){const a=N('a',null,'section-link'),copy=N('span');a.href=href;copy.append(N('strong',title),N('small',desc));a.append(copy,N('em','↗'));nav.append(a);}host.append(nav);}
 else host.append(N('p','본사 조회 계정입니다. 평가 입력·승인은 지정된 담당자가 진행합니다.','top-note'));
 host.append(N('div','기능·안전 평가기준과 기존 평가·서명 이력을 유지합니다.','info-strip'));
 for(const key of Object.keys(queries)){const box=N('section',null,'panel');box.dataset.evaluationPart=key;parts[key]={box,phase:'loading',value:null,request:0,controller:null,timer:null};host.append(box);}
 function status(key){
  const cell=parts[key],box=cell.box;box.replaceChildren();box.setAttribute('aria-busy',String(cell.phase==='loading'));box.append(N('h2',queries[key][1]));
  const note=N('p',cell.phase==='loading'?queries[key][1]+' 확인 중':queries[key][1]+'를 확인하지 못했습니다.','top-note');note.setAttribute('role','status');box.append(note);
  if(cell.phase==='failed'){const b=N('button','다시 확인');b.type='button';b.dataset.evaluationRetry=key;b.style.minHeight='44px';b.onclick=()=>void load(key);box.append(b);}
 }
 function renderOverview(){
  const cell=parts.overview;if(cell.phase!=='ready'){status('overview');return;}const d=cell.value,box=cell.box;box.replaceChildren();box.setAttribute('aria-busy','false');
  if(!d.period){box.append(N('h2','평가기간 확인'),N('p','현재 등록된 평가기간이 없습니다.'));return;}
  box.append(N('h2',d.period.title+' · 기존 평가 현황'));for(const[type,label]of[['FUNCTIONAL','기능'],['SAFETY','안전']]){box.append(N('p',label+' 평가  '+['S','A','B','C'].map(grade=>grade+' '+(d.grades.find(x=>x.eval_type===type&&x.grade_code===grade)?.count??0)+'명').join('  /  ')));}
 }
 function renderPreparation(){
  const cell=parts.preparation;if(cell.phase!=='ready'){status('preparation');return;}const box=cell.box,active=document.activeElement,focused=box.contains(active)?{id:active.id,label:active.getAttribute('aria-label'),start:active.selectionStart,end:active.selectionEnd}:null;
  box.replaceChildren();box.setAttribute('aria-busy','false');drawFunctionalReadiness(box,{data:cell.value,period:parts.overview.phase==='ready'?parts.overview.value.period:null,historyStatus:parts.history.phase==='ready'?parts.history.value:null,role,initialScope:scope,onScope:value=>{if(current()){scope=value;onScope(value);}},isCurrent:current});
  if(focused){const target=[...box.querySelectorAll('input,select')].find(e=>focused.id?e.id===focused.id:e.getAttribute('aria-label')===focused.label);if(target){target.focus({preventScroll:true});if(typeof focused.start==='number'&&target.setSelectionRange)try{target.setSelectionRange(focused.start,focused.end);}catch{}}}
 }
 function renderHistory(){
  if(parts.history.phase!=='ready'){status('history');return;}const box=parts.history.box;box.replaceChildren();box.setAttribute('aria-busy','false');const value=parts.history.value;
  box.append(N('h2','기존 평가 이력'),N('p',value.state==='NO_PERIOD'?'등록된 평가 이력이 없습니다.':'기존 원장의 평가 이력을 확인했습니다. 현장별 연결은 평가 준비 현황에서 확인하세요.','top-note'));
 }
 async function load(key){
  if(!current())return;const cell=parts[key],request=++cell.request;cell.controller?.abort();clearTimeout(cell.timer);cell.controller=new AbortController();const controller=cell.controller;cell.phase='loading';cell.value=null;status(key);
  const timer=setTimeout(()=>controller.abort(),15000);cell.timer=timer;
  try{const d=await api(queries[key][0],{signal:controller.signal});if(!current()||request!==cell.request)return;
   const valid=key==='overview'?validOverview(d):key==='preparation'?d&&typeof d.source_current==='boolean'&&typeof d.can_evaluate==='boolean':validHistory(d);
   if(!valid)throw Error('SOURCE_SCHEMA_UNCONFIRMED');cell.value=d;cell.phase='ready';
  }catch(e){if(!current()||request!==cell.request)return;if(e.status===401){dispose();return;}cell.value=null;cell.phase='failed';}
  finally{clearTimeout(timer);if(cell.timer===timer)cell.timer=null;if(cell.controller===controller)cell.controller=null;}
  if(current()){renderOverview();renderHistory();renderPreparation();}
 }
 function dispose(){if(!alive)return;alive=false;for(const cell of Object.values(parts)){clearTimeout(cell.timer);cell.controller?.abort();}removeEventListener('pagehide',dispose);removeEventListener('storage',accountChanged);}
 function accountChanged(e){if(e.key==='besma_token'||e.key===null)dispose();}
 addEventListener('pagehide',dispose);addEventListener('storage',accountChanged);
 for(const key of Object.keys(parts))void load(key);
 return dispose;
}
