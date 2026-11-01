const N=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
export function createSiteCorrectionEditor({site,request,onSaved,onNotice,isCurrent=()=>true,open=false,canEdit=false,fallback=null}){
 if(!canEdit)return null;
 if(site.correction_available!==true){
  if(site.correction_status==='UNAVAILABLE'){const p=N('p','수정 정보를 확인하지 못했습니다. 새로고침 후 확인해 주세요.');p.className='error';return p;}
  return fallback?.()||null;
 }
 const root=N('section'),toggle=N('button',site.correction_can_edit?'현장 정보 수정':'수정 이력 보기'),box=N('div'),notice=N('p');root.className='site-info-editor site-correction-editor';box.className='missing-info-fields';box.hidden=true;toggle.type='button';toggle.setAttribute('aria-expanded','false');notice.setAttribute('role','status');root.append(toggle,box,notice);
 const current=()=>root.isConnected&&isCurrent();let state=null,busy=false,pending=null,unknown=false;
 if(site.correction_review_required)root.prepend(N('p','원본이 바뀐 수정 항목이 있습니다. 내용을 확인해 주세요.'));
 function mark(){root.dataset.dirty=String(controls.some(f=>f.input.value.trim()!==f.original||f.reviewChoice));}
 const controls=[];
 function draw(value){
  state=value;controls.length=0;box.replaceChildren();
  if(!value.available){box.append(N('p','수정 정보를 확인하지 못했습니다. 새로고침 후 확인해 주세요.'));return;}
  if(value.unmatched_corrections?.length)box.append(N('p','담당자 정보가 바뀐 과거 수정 항목이 있습니다. 이력을 확인해 주세요.'));
  for(const f of value.fields){const row=N('label'),input=N(f.field==='description'?'textarea':'input');row.append(N('span',f.label));if(input.tagName==='INPUT')input.type=f.field==='phone'?'tel':'text';else input.rows=3;input.setAttribute('aria-label',f.label);input.maxLength=f.field==='description'?2000:f.field==='address'?400:f.field==='phone'?40:20;input.value=f.value;input.disabled=!value.can_edit;input.autocomplete='off';input.oninput=mark;row.append(input);if(f.review_required){row.append(N('small','원본 값이 바뀌었습니다. 이전 수정: '+f.previous_correction));}const control={field:f,input,original:f.value,reviewChoice:null};controls.push(control);if(f.review_required){for(const [label,value,choice]of [['이전 수정 사용',f.previous_correction,'previous'],['원본값 사용',f.source_value,'source']]){const b=N('button',label);b.type='button';b.disabled=!state.can_edit;b.onclick=()=>{input.value=value;control.reviewChoice=choice;mark();};row.append(b);}}box.append(row);}
  if(value.can_edit){const actions=N('div'),save=N('button','저장'),cancel=N('button','취소');actions.className='site-info-actions';save.type=cancel.type='button';save.onclick=()=>submit(save,cancel);cancel.onclick=()=>{if(busy||unknown)return;draw(state);root.dataset.dirty='false';box.hidden=true;toggle.setAttribute('aria-expanded','false');};actions.append(save,cancel);box.append(actions);}
  const history=N('details'),summary=N('summary','수정 이력');history.append(summary);for(const row of value.history){const item=N('p');item.textContent=row.label+' · '+(row.before_value===row.value?'원본값 확인':(row.before_value||'미등록')+' → '+(row.value||'미등록'))+' · '+row.actor_name+' · '+String(row.changed_at).replace('T',' ').slice(0,19);history.append(item);}if(!value.history.length)history.append(N('p','저장된 수정 이력이 없습니다.'));box.append(history);
 }
 async function completed(){unknown=false;pending=null;root.dataset.dirty='false';root.dataset.busy='false';if(current())onNotice('현장 정보를 저장했습니다.');try{await onSaved();}catch{if(current())notice.textContent='저장은 완료됐습니다. 화면을 새로고침해 주세요.';}}
 async function submit(save,cancel){
  if(busy||!current())return;
  if(!pending){for(const c of controls){const value=c.input.value.trim();if(c.field.field==='phone'&&value&&(!/^[+0-9() -]+$/.test(value)||value.replace(/\D/g,'').length<4||value.replace(/\D/g,'').length>20)){onNotice('전화번호를 확인해 주세요.');c.input.focus();return;}if(c.field.field==='rank'&&value&&!/^[가-힣A-Za-z ]+$/.test(value)){onNotice('직급을 확인해 주세요.');c.input.focus();return;}}const changes=controls.filter(c=>c.input.value.trim()!==c.original||c.reviewChoice).map(c=>({field:c.field.field,contact_id:c.field.contact_id,value:c.input.value.trim(),expected_source_sha256:c.field.source_sha256}));if(!changes.length){onNotice('바뀐 내용을 입력해 주세요.');return;}pending={expected_revision:state.revision,request_id:crypto.randomUUID().replaceAll('-',''),changes};}
  busy=true;root.dataset.busy='true';toggle.disabled=save.disabled=cancel.disabled=true;for(const c of controls)c.input.disabled=true;notice.textContent=unknown?'저장 결과를 확인하고 있습니다.':'저장하고 있습니다.';
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000);
  try{await request('/workspace/site-corrections/'+encodeURIComponent(site.code),{method:'PUT',body:JSON.stringify(pending),signal:controller.signal});if(current())await completed();}
  catch(error){if(!current())return;const wasUnknown=unknown;
   const lookup=new AbortController(),lookupTimeout=setTimeout(()=>lookup.abort(),10000);try{await request('/workspace/site-corrections/'+encodeURIComponent(site.code)+'/receipts/'+pending.request_id,{signal:lookup.signal});if(current())await completed();}
   catch{if(!current())return;if(!wasUnknown&&[400,403,404,409,422].includes(error.status)){pending=null;notice.textContent=error.status===409?'다른 수정이나 원본 변경이 있습니다. 새로고침 후 확인해 주세요.':error.message;for(const c of controls)c.input.disabled=false;if(error.status===409){const reload=N('button','새로고침');reload.type='button';reload.onclick=async()=>{try{const value=await request('/workspace/site-corrections/'+encodeURIComponent(site.code));if(current()){draw(value);root.dataset.dirty='false';notice.textContent='현재 정보로 다시 불러왔습니다.';}}catch(e){if(current())notice.textContent=e.message;}};notice.append(reload);}}else{unknown=true;notice.textContent='저장 결과를 아직 확인하지 못했습니다. 저장 확인을 눌러 주세요.';save.textContent='저장 확인';}}finally{clearTimeout(lookupTimeout);}
  }finally{clearTimeout(timeout);busy=false;root.dataset.busy=String(unknown);if(current()){save.disabled=false;toggle.disabled=cancel.disabled=unknown;if(!unknown)for(const c of controls)c.input.disabled=false;}}
 }
 toggle.onclick=async()=>{if(busy||!current())return;if(state){box.hidden=!box.hidden;toggle.setAttribute('aria-expanded',String(!box.hidden));return;}toggle.disabled=true;notice.textContent='현장 정보를 확인하고 있습니다.';try{const value=await request('/workspace/site-corrections/'+encodeURIComponent(site.code));if(!current())return;draw(value);box.hidden=false;toggle.setAttribute('aria-expanded','true');notice.textContent='';}catch(e){if(current())notice.textContent=e.message;}finally{if(current())toggle.disabled=false;}};
 if(open)queueMicrotask(()=>{if(current())toggle.click();});return root;
}
