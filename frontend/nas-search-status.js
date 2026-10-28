const labelTime=value=>new Date(value).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
export function describeNasIndex(value,now=Date.now()){
 if(!value||!Array.isArray(value.sources))return {phase:'unknown'};
 const rows=value.sources.filter(x=>x?.scope==='TEAM_SAFETY_NAS');
 if(!rows.length)return {phase:'missing'};
 if(rows.length!==1)return {phase:'unknown'};
 const row=rows[0],date=Date.parse(row.generated_at);
 if(row.status!=='ACTIVE'||row.logical_root_id!=='team-safety-nas-z4'||!Number.isSafeInteger(row.entry_count)||row.entry_count<0||typeof row.generated_at!=='string'||!/(?:Z|[+-]\d\d:\d\d)$/.test(row.generated_at)||!Number.isFinite(date)||date>now+300000)return {phase:'unknown'};
 return {phase:now-date>36*3600000?'stale':'ready',generatedAt:row.generated_at,count:row.entry_count};
}

export function createNasSearchStatus({api,isCurrent,now=()=>Date.now()}){
 const element=document.createElement('section'),text=document.createElement('p'),check=document.createElement('button');
 element.className='request-index-status';element.setAttribute('aria-label','NAS 검색목록 상태');
 text.setAttribute('role','status');check.type='button';check.textContent='목록 확인';element.append(text,check);
 let alive=true,state={phase:'loading'},lastGood=null,pending=null,lastChecked=0,controller=null;
 const current=()=>alive&&isCurrent();
 function render(){
  if(!current())return;const prior=state.phase==='error'||state.phase==='loading'?lastGood:null,meta=state.generatedAt?state:prior;
  const basis=meta?'검색목록 기준 '+labelTime(meta.generatedAt)+' · '+meta.count.toLocaleString('ko-KR')+'개':'';
  const messages={loading:'검색목록 상태를 확인하고 있습니다.',missing:'검색목록을 준비하고 있습니다. 자료가 없다는 뜻은 아닙니다.',unknown:'검색목록 기준을 확인하지 못했습니다.',error:'검색목록 상태를 확인하지 못했습니다.',stale:'목록이 오래되어 갱신 확인이 필요합니다.',ready:'기준 시각 이후의 새 자료는 다음 목록 갱신 후 검색됩니다.'};
  text.textContent=(basis?basis+(prior?' (마지막 확인값)':'')+'\n':'')+messages[state.phase];
  element.dataset.state=state.phase;check.disabled=state.phase==='loading';
 }
 async function refresh(force=false){
  if(!current())return state;if(pending)return pending;
  if(!force&&lastChecked&&now()-lastChecked<60000)return state;
  state={phase:'loading'};render();controller=new AbortController();const active=controller,timeout=setTimeout(()=>active.abort(),5000);
  pending=(async()=>{
   try{const value=await api('/desktop/v1/file-search/state',{signal:active.signal});if(!current())return state;state=describeNasIndex(value,now());if(['ready','stale'].includes(state.phase))lastGood={...state};else lastGood=null;}
   catch{if(current())state={phase:'error'};}
   finally{clearTimeout(timeout);if(controller===active)controller=null;if(current()){lastChecked=now();render();}pending=null;}
   return state;
  })();return pending;
 }
 check.onclick=()=>refresh(true);
 function emptyMessage(fallback){
  if(state.phase==='ready')return fallback;
  if(state.phase==='stale')return '이전 검색목록에서 자료를 찾지 못했습니다. 목록 갱신 상태를 확인해 주세요.';
  if(state.phase==='missing')return '검색목록을 준비하고 있습니다. 자료가 없다고 확정할 수 없습니다.';
  return '검색목록 상태를 확인하지 못했습니다. 자료가 없다고 확정할 수 없습니다. 목록 확인 후 다시 찾아 주세요.';
 }
 return {element,refresh,emptyMessage,getState:()=>({...state}),dispose(){alive=false;controller?.abort();}};
}
