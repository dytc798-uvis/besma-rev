import {monthlyCandidates,monthlyQuery,monthlyHandoff,monthlyRequestBody} from './monthly-source-flow.js';
import {receiveVerifiedFile} from './request-file-download.js';
const N=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
const categoryNames={theme:'테마점검',risk:'위험성평가','legal-training':'법정교육',opinions:'근로자 의견청취','safety-cost':'산업안전보건관리비'};
export function createMonthlyEvidence({host,evidenceId,refs,api,loadSources,onLink,onUnlink,current,pending}){
 const wrap=N('section'),note=N('p'),list=N('div'),find=N('button','취합자료 찾기'),choices=N('div');wrap.className='hyr-monthly';find.type='button';find.className='hyr-monthly-find';note.setAttribute('role','status');
 let alive=true,loading=false;const here=()=>alive&&host.isConnected&&current();
 const linked=refs.filter(r=>r.active&&r.evidence_id===evidenceId);
 for(const ref of linked){const line=N('div'),name=N('span',ref.filename),meta=N('small',ref.month+' · '+categoryNames[ref.category]+' · '+ref.team),download=N('button','원본 받기'),remove=N('button','연결 해제');line.className='hyr-monthly-reference';name.title=ref.filename;download.type=remove.type='button';remove.className='hyr-monthly-unlink';download.onclick=()=>receive(ref,download);remove.onclick=()=>Promise.resolve().then(()=>here()&&onUnlink(ref)).catch(e=>{if(here())note.textContent=e.message;});line.append(name,meta,download,remove);list.append(line);}
 async function receive(ref,button){
  if(loading||!here())return;loading=true;button.disabled=true;note.textContent='원본을 확인하고 있습니다.';
  try{
   if(ref.bytes>32*1024*1024)throw Error('32MB를 넘는 원본은 아직 채팅으로 받을 수 없습니다. 연결 기록은 유지됩니다.');
   let job=pending.get(ref.id);
   if(!job){
    const options=await loadSources();if(!here())return;
    const item=options.items.find(x=>x.id===ref.source_id&&x.source_version===ref.source_version);if(!item)throw Error('연결 후 수신자료가 변경되었습니다. 연결 기록은 유지되니 취합자료에서 다시 확인해 주세요.');
    const access=await api('/work-requests/availability');if(!here())return;
    if(!access.enabled||!access.nas_files)throw Error('이 계정의 원본 자료 이용 권한을 확인해 주세요.');
    const found=await api('/work-requests/nas/search',{method:'POST',body:JSON.stringify({q:monthlyQuery(item)})});if(!here())return;
    const candidates=monthlyCandidates(item,found.items);if(candidates.length!==1)throw Error(candidates.length?'같은 이름의 원본이 여러 개입니다. 취합현황에서 폴더를 확인해 주세요.':'원본 검색 반영 상태를 확인해 주세요. 연결 기록은 유지됩니다.');
    const handoff=monthlyHandoff(item,candidates[0]);job={key:handoff.requestKey,body:{request_key:handoff.requestKey,kind:'FILE',title:item.filename.slice(0,100),body:monthlyRequestBody(handoff),nas_file_id:candidates[0].nas_file_id}};pending.set(ref.id,job);
   }
   if(!job.id){const created=await api('/work-requests',{method:'POST',body:JSON.stringify(job.body)});if(!/^[a-f0-9]{32}$/.test(created.id||''))throw Error('원본 요청 결과를 확인해 주세요.');job.id=created.id;}
   const start=Date.now();let request;
   while(here()&&Date.now()-start<120000){
    request=await api('/work-requests/'+job.id);if(!here())return;
    if(request.status==='COMPLETED')break;
    if(['AWAITING_REVIEW','AWAITING_RELEASE'].includes(request.status))throw Error('원본 제공 확인을 기다리고 있습니다. 베스마채팅에서도 같은 요청을 확인할 수 있습니다.');
    if(!['QUEUED','RUNNING'].includes(request.status))throw Error(request.reply||'원본을 받지 못했습니다. 연결 기록은 유지됩니다.');
    note.textContent='원본을 준비하고 있습니다. 평가 입력은 계속할 수 있습니다.';await new Promise(resolve=>setTimeout(resolve,1000));
   }
   if(!here())return;if(request?.status!=='COMPLETED')throw Error('원본 준비가 이어지고 있습니다. 다시 누르면 같은 요청을 확인합니다.');
   if(request.source_access===false)throw Error('원본 자료 이용 권한을 다시 확인해 주세요.');
   const file=request.files?.find(f=>f.sha256===ref.sha256&&f.bytes===ref.bytes&&/^[a-f0-9]{32}$/.test(f.id));if(!file)throw Error('원본 내용이 수신 당시와 다릅니다. 이전 연결 기록은 유지됩니다.');
   const response=await api('/work-requests/'+job.id+'/files/'+file.id,{response:true});if(!here())return;
   const bytes=await receiveVerifiedFile(response,file,{guard:()=>{if(!here())throw Error('현재 평가 화면이 변경되었습니다.');},onProgress:({phase,loaded,total})=>{if(here())note.textContent=phase==='VERIFYING'?'원본 내용을 확인하고 있습니다.':'원본 받는 중 '+Math.floor(100*loaded/total)+'%';}});if(!here())return;
   const url=URL.createObjectURL(new Blob([bytes])),a=N('a');a.href=url;a.download=ref.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);note.textContent='원본을 받았습니다. 내용을 확인한 뒤 평가자료 확인란에 표시해 주세요.';
   if(request.completion_token)await api('/work-requests/'+job.id+'/read',{method:'POST',body:JSON.stringify({completion_token:request.completion_token})}).catch(()=>{});
  }catch(e){if(here())note.textContent=e.message||'원본을 받지 못했습니다.';}finally{loading=false;if(here())button.disabled=false;}
 }
 find.onclick=async()=>{if(!here()||loading)return;loading=true;find.disabled=true;note.textContent='이 현장·반기의 취합자료를 확인하고 있습니다.';try{
  const result=await loadSources();if(!here())return;choices.replaceChildren();
  const registrationNote=result.site_registry_confirmed===false?' 점검계획의 현장 반영은 현장 정보 확인 후 가능합니다.':'';
  if(result.state!=='AVAILABLE'){note.textContent=result.state==='SITE_UNCONFIRMED'?'점검계획의 현장 연결을 먼저 확인해 주세요.':'아직 이 범위의 자료 수신을 확인하지 못했습니다.';note.textContent+=registrationNote;return;}
  note.textContent=result.count?'이 현장·반기의 수신자료 '+result.count+'개입니다. 확인할 항목에 연결해 주세요.':'이 현장·반기에 수신이 확인된 자료가 없습니다.';
  note.textContent+=registrationNote;
  const filter=N('input');filter.type='search';filter.placeholder='파일명·자료월 찾기';filter.setAttribute('aria-label','취합자료 검색');choices.append(filter);
  const rows=[];for(const item of result.items){const line=N('div'),pick=N('button','이 항목에 연결');pick.type='button';line.className='hyr-monthly-choice';line.append(N('span',item.filename),N('small',item.month+' · '+categoryNames[item.category]+' · '+item.team),pick);pick.disabled=linked.some(r=>r.source_id===item.id&&r.source_version===item.source_version);pick.onclick=()=>Promise.resolve().then(()=>here()&&onLink(item)).catch(e=>{if(here())note.textContent=e.message;});choices.append(line);rows.push({line,text:(item.filename+' '+item.month+' '+categoryNames[item.category]).normalize('NFC')});}
  filter.oninput=()=>{const words=filter.value.normalize('NFC').trim().split(/\s+/).filter(Boolean);for(const x of rows)x.line.hidden=!words.every(w=>x.text.includes(w));};
 }catch(e){if(here())note.textContent=e.message||'취합자료를 확인하지 못했습니다.';}finally{loading=false;if(here())find.disabled=false;}};
 wrap.append(list,find,note,choices);host.append(wrap);return()=>{alive=false;};
}
