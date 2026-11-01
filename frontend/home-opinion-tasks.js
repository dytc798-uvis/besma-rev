const KEY='besma-home-opinion-tasks-v1',TTL=14400000;
const roles=['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'];
const count=value=>Number.isSafeInteger(value)&&value>=0;
const dateText=value=>typeof value==='string'&&/(Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}):null;
export function createHomeOpinionTasks({anchor,api,token,onNavigate=()=>{}}){
 const n=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;},host=n('details');host.id='today-opinion-tasks';host.className='government-document-tasks';host.hidden=true;anchor.after(host);
 let seq=0,owner='',opened=false,last=null;
 const current=()=>!!token&&localStorage.getItem('besma_token')===token;
 const ready=crypto.subtle.digest('SHA-256',new TextEncoder().encode(token||'')).then(bytes=>{owner=[...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');try{const old=JSON.parse(sessionStorage.getItem(KEY)||'null');if(old?.owner===owner&&Date.now()-old.at>=0&&Date.now()-old.at<TTL)opened=old.open===true;}catch{}}).catch(()=>{});
 function remember(){if(owner&&current())try{sessionStorage.setItem(KEY,JSON.stringify({owner,at:Date.now(),open:opened}));}catch{}}
 host.addEventListener('toggle',()=>{opened=host.open;remember();});
 function failure(message){host.hidden=false;host.open=opened;host.replaceChildren(n('summary','근로자의견 확인 필요'),n('p',message));const retry=n('button','다시 확인');retry.type='button';retry.onclick=()=>last&&refresh(last);host.append(retry);}
 function clear(message){seq++;last=null;failure(message||'근로자의견을 다시 확인해 주세요.');}
 async function refresh(bootstrap){
  const pass=++seq;last=bootstrap;await ready;if(!current()||pass!==seq)return;
  if(!bootstrap?.user||!bootstrap.permissions){failure('근로자의견 조회 권한을 확인하지 못했습니다.');return;}
  if(!roles.includes(bootstrap.user.role)||bootstrap.permissions.worker_voice_read!==true){host.hidden=true;host.replaceChildren();return;}
  host.hidden=false;host.open=opened;host.replaceChildren(n('summary','근로자의견 확인 중'));
  async function get(path){const r=await fetch(api+path,{headers:{Authorization:'Bearer '+token},credentials:'omit',redirect:'error',cache:'no-store',signal:AbortSignal.timeout(15000)});if(!current()||pass!==seq)throw Error('STALE_CONTEXT');if(!r.ok)throw Error(r.status===403?'근로자의견 조회 권한을 확인해 주세요.':r.status===401?'로그인 후 확인해 주세요.':'근로자의견을 불러오지 못했습니다.');return r.json();}
  try{
   const [value,sync]=await Promise.all([get('/worker-feedback/desktop-responses?limit=1&offset=0'),get('/worker-feedback/refresh-status').catch(()=>null)]);if(!current()||pass!==seq)return;
   const s=value.summary;
   if(value.schema!=='besma.google-feedback.desktop.v1'||value.source!=='GOOGLE_FORMS'||value.source_sync_performed!==false||typeof value.scope_complete!=='boolean'||typeof value.snapshot_token!=='string'||!(/^[a-f0-9]{64}$/).test(value.snapshot_token)||!value.scope||value.scope.site_code!==null||value.scope.from_date!==null||value.scope.to_date!==null||value.scope.period_basis!=='stored_submitted_at'||value.offset!==0||value.limit!==1||!Array.isArray(value.items)||value.items.length>1||value.returned_count!==value.items.length||!count(value.total_count)||value.total_count>10000||value.items.length!==Math.min(1,value.total_count)||value.has_more!==(value.total_count>value.items.length)||!s||!['total','receipt_pending','action_incomplete','hq_evaluation_pending'].every(k=>count(s[k]))||s.total!==value.total_count||s.receipt_pending>s.action_incomplete||s.action_incomplete>s.total||s.hq_evaluation_pending>s.total-s.action_incomplete)throw Error('근로자의견의 조회 범위를 확인하지 못했습니다.');
   const received=dateText(sync?.last_success_at),read=dateText(value.read_at_utc),uncertain=!value.scope_complete||sync?.last_attempt_ok===false||!received;
   host.replaceChildren(n('summary',!value.scope_complete||s.total===0&&uncertain?'근로자의견 확인 필요':'근로자의견 · 조치 미완료 '+s.action_incomplete+'건'));
   host.open=opened;host.append(n('p','저장된 의견 '+s.total+'건 · 접수 대기 '+s.receipt_pending+' · 본사 평가 대기 '+s.hq_evaluation_pending));
   const list=n('ul');list.className='document-task-list';for(const[key,label]of [['action_incomplete','조치 미완료'],['receipt_pending','접수 대기'],['hq_evaluation_pending','본사 평가 대기']]){const li=n('li'),a=n('a',label+' '+s[key]+'건');a.href='/workspace.html#voice?'+new URLSearchParams({filter:key,from:'home'});a.dataset.opinionFilter=key;a.onclick=()=>{remember();onNavigate();};li.append(a);list.append(li);}host.append(list);
   if(uncertain)host.append(n('p',!value.scope_complete?'확인되지 않은 의견이 있어 전체 건수를 확정할 수 없습니다.':sync?.last_attempt_ok===false?'새 의견 수신을 확인하지 못해 저장된 의견을 표시합니다.':'마지막 정상 수신 시각을 확인해야 합니다. 저장된 의견을 표시합니다.'));
   host.append(n('small',(received?'Google 마지막 정상 수신: '+received:'수신 시각 확인 필요')+(read?' · 저장 의견 조회: '+read:'')));
  }catch(error){if(current()&&pass===seq)failure(error.message||'근로자의견을 확인하지 못했습니다.');}
 }
 addEventListener('pagehide',remember);addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null){try{sessionStorage.removeItem(KEY);}catch{}clear('로그인 계정이 변경되었습니다. 화면을 다시 열어 주세요.');}});
 return{refresh,clear};
}
