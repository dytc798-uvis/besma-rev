import {inspectionHref,inspectionPlanId} from '/assets/inspection-work-entry.js';
const KEY='besma-home-inspection-tasks-v1',TTL=14400000,DAY=86400000;
const date=value=>typeof value==='string'&&/^20\d{2}-(0[1-9]|1[0-2])-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value;
export function createHomeInspectionTasks({anchor,api,token,onNavigate,onSummary=()=>{}}){
 const n=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const host=n('details');host.className='government-document-tasks';host.id='today-inspection-tasks';host.hidden=true;anchor.after(host);
 let sequence=0,owner='',opened=false,last=null,view=null,checking=false,state={query:'',filter:'all',selected:''};const current=()=>!!token&&localStorage.getItem('besma_token')===token;
 const ready=crypto.subtle.digest('SHA-256',new TextEncoder().encode(token||'')).then(bytes=>{owner=[...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');try{const old=JSON.parse(sessionStorage.getItem(KEY)||'null');if(old?.owner===owner&&Date.now()-old.at>=0&&Date.now()-old.at<TTL){opened=old.open===true;state={query:typeof old.query==='string'?old.query.slice(0,100):'',filter:['all','overdue','planned','progress','hold'].includes(old.filter)?old.filter:'all',selected:inspectionPlanId(old.selected)||''};}}catch{}}).catch(()=>{});
 function remember(){if(current()&&owner)try{sessionStorage.setItem(KEY,JSON.stringify({owner,at:Date.now(),open:opened,...state}));}catch{}}
 host.addEventListener('toggle',()=>{opened=host.open;remember();});addEventListener('pagehide',remember);
 function clear(message){onSummary({state:"UNKNOWN"});sequence++;last=null;view=null;checking=false;host.removeAttribute('aria-busy');host.hidden=false;host.replaceChildren(n('summary','내 점검 확인 필요'),n('p',message||'점검계획을 다시 확인해 주세요.'));}
 async function refresh(home,user){
  const pass=++sequence;onSummary({state:"LOADING"});last={home,user};await ready;if(!current()||pass!==sequence)return;
  if(!user){failure('계정의 점검계획 조회 권한을 확인하지 못했습니다.');return;}
  if(!['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'].includes(user.role)){onSummary({state:'HIDDEN'});view=null;checking=false;host.hidden=true;host.removeAttribute('aria-busy');host.replaceChildren();return;}
  const today=home?.date;if(!date(today)){failure('점검계획의 기준일과 계정을 확인해야 합니다.');return;}
  host.hidden=false;host.open=opened;checking=true;host.setAttribute('aria-busy','true');if(view){view.summary.textContent='내 점검 새로 확인 중';view.draw();}else host.replaceChildren(n('summary','내 점검 확인 중'));
  const start=new Date(Date.parse(today)-350*DAY).toISOString().slice(0,10),end=new Date(Date.parse(today)+14*DAY).toISOString().slice(0,10);
  async function get(path){const r=await fetch(api+path,{headers:{Authorization:'Bearer '+token},credentials:'omit',redirect:'error',cache:'no-store',signal:AbortSignal.timeout(15000)});if(!current()||pass!==sequence)throw Error('STALE_CONTEXT');if(!r.ok)throw Error(r.status===403?'점검계획 조회 권한을 확인해 주세요.':'점검계획을 불러오지 못했습니다.');return r.json();}
  try{
   user=await get('/auth/me');if(!Number.isSafeInteger(user.id)||user.id<1||!['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'].includes(user.role))throw Error('점검계획의 계정 정보를 확인해야 합니다.');
   const capabilities=await get('/safety-features/team-schedule/capabilities?surface=PC_WEB');if(capabilities.can_read!==true)throw Error('점검계획 조회 권한을 확인해 주세요.');
   const value=await get('/safety-features/team-schedule/items?'+new URLSearchParams({from_date:start,to_date:end,inspection_only:'true',mine_only:'true'}));if(!current()||pass!==sequence)return;
   if(!Array.isArray(value.items)||value.items.length>2000)throw Error('점검계획의 조회 범위를 확인해야 합니다.');
   const seen=new Set();for(const row of value.items){if(!inspectionPlanId(row.public_id)||seen.has(row.public_id)||row.owner_user_id!==user.id||!date(row.scheduled_date)||row.due_date!=null&&(!date(row.due_date)||row.due_date<row.scheduled_date)||typeof row.title!=='string'||!['PLANNED','IN_PROGRESS','ON_HOLD','COMPLETED'].includes(row.status))throw Error('점검계획의 담당·현장·기간을 확인해야 합니다.');seen.add(row.public_id);}
   const rows=value.items.filter(r=>!r.archived&&['PLANNED','IN_PROGRESS','ON_HOLD'].includes(r.status)).sort((a,b)=>(a.due_date||a.scheduled_date).localeCompare(b.due_date||b.scheduled_date)||a.public_id.localeCompare(b.public_id));
   const overdue=rows.filter(row=>(row.due_date||row.scheduled_date)<today).length;
   onSummary({state:'VERIFIED',count:rows.length,overdue,scope:start+' ~ '+end+' 본인 점검'});
   checking=false;host.removeAttribute('aria-busy');
   if(!view){
   const summary=n('summary'),scope=n('small');host.replaceChildren(summary,scope);
   const controls=n('div');controls.className='document-task-controls';
   const searchGroup=n('div'),searchLabel=n('label','현장·주소 검색'),search=n('input');search.id='home-inspection-query';searchLabel.htmlFor=search.id;search.type='search';search.maxLength=100;search.placeholder='현장명·주소';search.value=state.query;searchGroup.append(searchLabel,search);
   const filterGroup=n('div'),filterLabel=n('label','확인 구분'),filter=n('select');filter.id='home-inspection-filter';filterLabel.htmlFor=filter.id;
   for(const[key,text]of[['all','미완료 전체'],['overdue','예정일 지남'],['planned','예정'],['progress','진행 중'],['hold','보류']]){const option=n('option',text);option.value=key;filter.append(option);}filter.value=state.filter;filterGroup.append(filterLabel,filter);controls.append(searchGroup,filterGroup);
   const result=n('p');result.className='document-task-result';result.setAttribute('role','status');const list=n('ul');list.className='document-task-list';host.append(controls,result,list);view={summary,scope,search,filter,result,list,draw:()=>{}};
   const all=n('a','내 점검 전체 보기');all.href='/inspection-plan.html';all.onclick=()=>{remember();onNavigate();};host.append(all);
   }
   const {search,filter,result,list}=view;view.summary.textContent='내 점검 · '+rows.length+'건'+(overdue?' · 예정일 지남 '+overdue+'건':'');view.scope.textContent='본인의 미완료 점검과 14일 이내 예정 · 조회 '+start+' ~ '+end;
   function draw(){
    const terms=state.query.normalize('NFC').trim().toLocaleLowerCase('ko-KR').split(/\s+/).filter(Boolean);
    const visible=rows.filter(row=>terms.every(term=>[row.title,row.detail_text||''].join(' ').normalize('NFC').toLocaleLowerCase('ko-KR').includes(term))&&(state.filter==='all'||state.filter==='overdue'&&(row.due_date||row.scheduled_date)<today||state.filter==='planned'&&row.status==='PLANNED'||state.filter==='progress'&&row.status==='IN_PROGRESS'||state.filter==='hold'&&row.status==='ON_HOLD'));
    result.textContent=(checking?'새로 확인 중 · 이전 조회 내용 · ':'')+'표시 '+visible.length+'건 / 미완료 '+rows.length+'건';list.replaceChildren();
    for(const row of visible){const li=n('li'),link=n('a',row.title.replace(/^\[점검\]\s*/,''));link.href=inspectionHref(row);link.dataset.inspectionPlan=row.public_id;if(state.selected===row.public_id){li.className='selected';link.setAttribute('aria-current','true');}link.onclick=()=>{state.selected=row.public_id;remember();onNavigate();};const endDate=row.due_date||row.scheduled_date;li.append(link,n('small',row.scheduled_date+(row.due_date?' ~ '+row.due_date:'')+' · '+(row.status==='ON_HOLD'?'보류':endDate<today?'예정일 지남':row.status==='IN_PROGRESS'?'진행 중':'예정')));list.append(li);}
    if(!visible.length)list.append(n('li',rows.length?'현재 검색·확인 조건에 맞는 점검이 없습니다.':'이 조회기간의 미완료·예정 점검이 없습니다.'));
   }
   view.draw=draw;search.oninput=()=>{if(!current())return;state.query=search.value.slice(0,100);view.draw();remember();};filter.onchange=()=>{if(!current())return;state.filter=filter.value;view.draw();remember();};draw();
  }catch(e){if(current()&&pass===sequence)failure(e.message||'점검계획을 확인하지 못했습니다.');}
 }
 function failure(message){onSummary({state:'UNKNOWN'});view=null;checking=false;host.removeAttribute('aria-busy');host.hidden=false;host.replaceChildren(n('summary','내 점검 확인 필요'),n('p',message));const retry=n('button','다시 확인');retry.type='button';retry.onclick=()=>last&&refresh(last.home,last.user);host.append(retry);}
 addEventListener('storage',e=>{if(e.key==='besma_token'||e.key===null){try{sessionStorage.removeItem(KEY);}catch{}clear('로그인 계정이 변경되었습니다. 화면을 다시 열어 주세요.');}});
 return {refresh,clear};
}
