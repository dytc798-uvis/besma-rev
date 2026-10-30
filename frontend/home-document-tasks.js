import {loadGovernmentDocuments,governmentTasks,governmentTaskHref} from '/assets/government-document-status.js';
import {restoreDocumentTaskView,mountDocumentTaskView} from '/assets/document-task-view.js';
const KEY='besma-home-document-tasks-v1',TTL=4*60*60*1000;
export function createHomeDocumentTasks({anchor,api,token,onNavigate}){
 const node=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const host=node('details');host.id='today-document-tasks';host.className='government-document-tasks';host.hidden=true;anchor.after(host);
 let sequence=0,owner='',open=false,state=restoreDocumentTaskView(null),month='',latest=null;
 const current=()=>!!token&&localStorage.getItem('besma_token')===token;
 const ready=crypto.subtle.digest('SHA-256',new TextEncoder().encode(token||'')).then(hash=>{owner=[...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('');try{const saved=JSON.parse(sessionStorage.getItem(KEY)||'null');if(saved?.owner===owner&&Date.now()-saved.at>=0&&Date.now()-saved.at<TTL){state=restoreDocumentTaskView(saved.state);open=saved.open===true;month=typeof saved.month==='string'?saved.month:'';}}catch{}}).catch(()=>{});
 function remember(){if(!owner||!current())return;try{sessionStorage.setItem(KEY,JSON.stringify({owner,at:Date.now(),state,open,month}));}catch{}}
 host.addEventListener('toggle',()=>{open=host.open;remember();});
 function clear(message){sequence++;latest=null;host.hidden=false;host.replaceChildren(node('summary','관급 문서 확인 필요'),node('p',message||'문서 현황을 다시 확인해 주세요.'));}
 async function refresh(home,role){
  const pass=++sequence;latest={home,role};await ready;if(!current()||pass!==sequence)return;
  if(role&&!['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'].includes(role)){host.hidden=true;host.replaceChildren();return;}
  host.hidden=false;host.replaceChildren(node('summary','관급 문서 확인 중'));host.open=open;
  const nextMonth=home?.date?.slice(0,7);if(month&&month!==nextMonth)state.selected='';month=nextMonth;
  const codes=Array.isArray(home?.sites)?home.sites.filter(s=>s.is_government===true).map(s=>s.code):null;
  const snapshot=await loadGovernmentDocuments({api,token,month,codes,current:()=>current()&&pass===sequence});if(!snapshot||!current()||pass!==sequence)return;
  host.replaceChildren();if(snapshot.state==='NOT_APPLICABLE'){host.hidden=true;return;}
  const model=governmentTasks(snapshot);
  if(model.state!=='VERIFIED'){
   host.append(node('summary','관급 문서 확인 필요'),node('p',model.state==='FORBIDDEN'?'관급 문서 조회 권한을 확인해 주세요.':model.state==='AUTH_REQUIRED'?'로그인 후 확인해 주세요.':'관급 문서 현황을 불러오지 못했습니다.'));
   if(!['FORBIDDEN','AUTH_REQUIRED'].includes(model.state)){const retry=node('button','다시 확인');retry.type='button';retry.onclick=()=>latest&&refresh(latest.home,latest.role);host.append(retry);}return;
  }
  const missing=model.tasks.filter(x=>x.status==='NOT_SUBMITTED').length,review=model.tasks.filter(x=>['SUBMITTED','IN_REVIEW','UNDER_REVIEW','RESUBMITTED'].includes(x.status)).length,rejected=model.tasks.filter(x=>x.status==='REJECTED').length;
  host.append(node('summary','관급 문서 확인 '+model.tasks.length+'건 · 미확인 '+model.unknown.length+'건'),node('p',month+' · 미제출 '+missing+' · 검토 '+review+' · 반려 '+rejected));
  mountDocumentTaskView(host,{tasks:model.tasks,unknown:model.unknown,month,sites:home.sites,state,buildHref:(task,value)=>governmentTaskHref(task,value,'/company.html'),onChange:remember,onNavigate:()=>{remember();onNavigate();},current:()=>current()&&pass===sequence});
  host.append(node('small','관급공사 취합 원장 기준 · 제출기한이 확인된 문서만 기한 초과로 표시합니다.'));
 }
 addEventListener('pagehide',remember);addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null){try{sessionStorage.removeItem(KEY);}catch{}clear('로그인 계정이 변경되었습니다. 화면을 다시 열어 주세요.');}});
 return {refresh,clear};
}
