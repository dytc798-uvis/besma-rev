const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const labels={PENDING:'접수 대기',RECEIVED:'접수됨·조치 중',DONE:'조치 완료'};
const dateText=value=>{if(!value)return '확인되지 않음';if(!/(Z|[+-]\d{2}:\d{2})$/.test(value))return value.replace('T',' ')+' (시각 기준 확인 필요)';const d=new Date(value);return Number.isNaN(d.valueOf())?'확인되지 않음':d.toLocaleString('ko-KR',{timeZone:'Asia/Seoul'});};
export function mountWorkerOpinions(host,{api,isCurrent,canRefresh=false,initialScope={},onScope=()=>{}}){
 let stopped=false,epoch=0,selected=null,filter='total',snapshot=null,refreshState=null;
 const current=()=>!stopped&&isCurrent(),root=N('section',null,'worker-opinions'),form=N('form',null,'voice-filters'),site=N('select'),from=N('input'),to=N('input'),submit=N('button','조회'),error=N('p',null,'voice-error'),fresh=N('p',null,'voice-freshness'),cards=N('div',null,'voice-counts'),columns=N('div',null,'voice-columns'),list=N('div',null,'voice-list'),detail=N('article',null,'voice-detail');
 site.setAttribute('aria-label','현장');site.append(new Option('허용된 전체 현장',''));from.type=to.type='date';from.value=initialScope.from_date||'';to.value=initialScope.to_date||'';site.dataset.requested=initialScope.site_code||'';submit.type='submit';error.setAttribute('role','alert');fresh.setAttribute('aria-live','polite');
 for(const [title,control]of [['현장',site],['시작일',from],['종료일',to]]){const label=N('label',title);label.append(control);form.append(label);}form.append(submit);columns.append(list,detail);detail.hidden=true;root.append(form,fresh,error,cards,columns);host.append(root);
 const save=()=>onScope({site_code:site.value,from_date:from.value,to_date:to.value,selected_id:selected?.id??null,filter});
 function clear(){snapshot=null;cards.replaceChildren();list.replaceChildren();detail.replaceChildren();detail.hidden=true;selected=null;}
 function message(s){error.textContent=s;error.hidden=!s;}
 function show(row){selected=row;save();detail.hidden=false;detail.replaceChildren();const back=N('button','목록으로 돌아가기');back.type='button';back.onclick=()=>{selected=null;detail.hidden=true;save();};detail.append(back,N('h2',row.worker_name||'성명 미확인'),N('p',row.matched_site_name||row.matched_site_code||'현장 연결 확인 필요'),N('p',dateText(row.submitted_at)),N('p',row.content||'의견 내용 없음','voice-content'),N('p','접수·조치: '+labels[row.action_status]),N('p',row.action_result||'조치 내용 미등록','voice-content'),N('p','본사 평가: '+(row.score_total==null?'미평가':row.score_total+'점')),N('p','가점: '+row.bonus_points+'점'));for(const b of list.querySelectorAll('[data-opinion-id]'))b.setAttribute('aria-pressed',String(b.dataset.opinionId===String(row.id)));}
 function draw(){
  cards.replaceChildren();for(const [key,label]of [['total','전체 의견'],['receipt_pending','접수 대기'],['action_incomplete','조치 미완료'],['hq_evaluation_pending','본사 평가 대기']]){const b=N('button',label);b.type='button';b.append(N('strong',snapshot.summary[key]));b.setAttribute('aria-pressed',String(key===filter));b.onclick=()=>{filter=key;selected=null;detail.hidden=true;save();draw();};cards.append(b);}
  const rows=snapshot.items.filter(r=>filter==='receipt_pending'?r.action_status==='PENDING':filter==='action_incomplete'?r.action_status!=='DONE':filter==='hq_evaluation_pending'?r.action_status==='DONE'&&r.score_total===null:true);list.replaceChildren(N('h2','의견 '+rows.length+'건'));
  for(const row of rows){const b=N('button',null,'voice-row');b.type='button';b.dataset.opinionId=String(row.id);b.setAttribute('aria-pressed',String(row.id===selected?.id));b.append(N('strong',(row.worker_name||'성명 미확인')+' · '+(row.matched_site_name||row.matched_site_code||'현장 연결 확인 필요')),N('span',row.content||'의견 내용 없음'),N('small',labels[row.action_status]+' · '+dateText(row.submitted_at)));b.onclick=()=>show(row);list.append(b);}if(!rows.length)list.append(N('p','이 조건의 의견이 없습니다.'));
 }
 function validDate(value){return !value||/^20\d{2}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;}
 async function load(refresh=false){
  const g=++epoch,prior=selected?.id??initialScope.selected_id,wanted=site.value||site.dataset.requested||'';delete site.dataset.requested;clear();message('');submit.disabled=true;submit.textContent=refresh&&canRefresh?'새 의견을 가져오는 중…':'조회 중…';
  try{
   if(!validDate(from.value)||!validDate(to.value)||Boolean(from.value)!==Boolean(to.value)||(from.value&&from.value>to.value))throw Error('시작일과 종료일을 함께 확인해 주세요.');
   let refreshFailed=false;if(refresh&&canRefresh){try{refreshState=await api('/worker-feedback/refresh',{method:'POST'});}catch{refreshFailed=true;}}
   const statePromise=api('/worker-feedback/refresh-status').catch(()=>null);let first=null,items=[],offset=0;
   for(;;){const params=new URLSearchParams({limit:'100',offset:String(offset)});if(wanted)params.set('site_code',wanted);if(from.value){params.set('from_date',from.value);params.set('to_date',to.value);}const d=await api('/worker-feedback/desktop-responses?'+params);if(!current()||g!==epoch)return;
    if(d.schema!=='besma.google-feedback.desktop.v1'||!Array.isArray(d.items)||!Array.isArray(d.sites)||typeof d.snapshot_token!=='string'||d.source_sync_performed!==false||typeof d.scope_complete!=='boolean'||!Number.isInteger(d.total_count)||d.total_count<0||d.total_count>10000||d.offset!==offset||d.returned_count!==d.items.length||typeof d.has_more!=='boolean'||!d.summary||['total','receipt_pending','action_incomplete','hq_evaluation_pending'].some(k=>!Number.isInteger(d.summary[k])||d.summary[k]<0)||d.items.some(r=>!Number.isSafeInteger(r.id)||r.id<1||!Object.hasOwn(labels,r.action_status)||!Object.hasOwn(r,'score_total')||(r.score_total!==null&&(!Number.isInteger(r.score_total)||r.score_total<0||r.score_total>15))))throw Error('의견의 조회 범위를 확인하지 못했습니다. 다시 조회해 주세요.');
    if(first&&(first.snapshot_token!==d.snapshot_token||first.total_count!==d.total_count))throw Error('조회 중 의견이 변경되었습니다. 다시 조회해 주세요.');first??=d;items.push(...d.items);if(!d.has_more)break;if(!d.items.length||items.length>10000)throw Error('의견 목록을 모두 확인하지 못했습니다.');offset+=d.items.length;
   }
   if(items.length!==first.total_count||new Set(items.map(x=>x.id)).size!==items.length||first.summary.total!==items.length)throw Error('의견 목록을 모두 확인하지 못했습니다.');
   refreshState=await statePromise;if(!current()||g!==epoch)return;snapshot={...first,items};site.replaceChildren(new Option('허용된 전체 현장',''));for(const s of first.sites)site.append(new Option(s.site_name||s.site_code+' (명칭 확인 필요)',s.site_code));site.value=wanted;save();draw();const chosen=items.find(r=>r.id===prior);if(chosen)show(chosen);
   fresh.textContent='Google 마지막 정상 수신: '+dateText(refreshState?.last_success_at)+' · 저장된 의견 조회: '+dateText(first.read_at_utc);
   if(refreshFailed||refreshState?.last_attempt_ok===false)message('새 의견을 가져오지 못해 저장된 의견을 표시합니다. 다시 조회해 주세요.');
   else if(!first.scope_complete)message('접수 날짜가 확인되지 않은 의견이 있어 이 기간의 전체 건수를 확정할 수 없습니다.');
   else if(refreshState?.held>0)message('기존 응답과 달라진 의견은 확인 후 반영합니다.');
  }catch(e){if(current()&&g===epoch){clear();fresh.textContent='의견을 확인하지 못했습니다.';message(e.message||'의견을 불러오지 못했습니다. 다시 조회해 주세요.');}}
  finally{if(current()&&g===epoch){submit.disabled=false;submit.textContent='조회';}}
 }
 form.onsubmit=e=>{e.preventDefault();save();void load(true);};void load();return()=>{stopped=true;epoch++;root.remove();};
}
