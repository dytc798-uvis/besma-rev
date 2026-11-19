const n=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
const digest=async raw=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(x=>x.toString(16).padStart(2,'0')).join('');
const signatureStates=new Map();
async function signedState({origin,token,session,context,force=false}){
 const c=context(),key=origin+'|'+token+'|'+c.period,now=Date.now();let entry=signatureStates.get(key);
 if(force||!entry||now-entry.at>1000){
  const query=new URLSearchParams({period:c.period});
  session();entry={at:now,promise:fetch(origin+'/safety-features/half-year-reviews/aggregate-scores?'+query,{cache:'no-store',headers:{Authorization:'Bearer '+token}}).then(async r=>{session();if(!r.ok)throw Error('SIGNATURE_STATUS_UNAVAILABLE');const value=await r.json();return new Map(value.items.map(row=>[row.public_id,row.signature_completed===true]));})};signatureStates.set(key,entry);
 }
 const states=await entry.promise;session();return states.get(c.plan)===true;
}
export function signingBundleButton({origin,token,session,context,beforeDownload=async()=>true,label='서명용 파일 받기'}){
 const button=n('button',label);button.type='button';button.className='signing-bundle-button';let ready=null,busy=false,signed=false,statusSequence=0,lastContext=JSON.stringify(context());
 const paint=()=>{button.classList.toggle('signing-complete',signed);button.disabled=busy||signed;if(signed){button.textContent='서명 완료';button.style.cssText='background:#18723b;color:#fff;border:1px solid #125b2e;opacity:1;cursor:default;';button.setAttribute('aria-label','서명 완료');}else{button.style.cssText='';button.removeAttribute('aria-label');if(!busy)button.textContent=ready?'서명용 파일 다시 받기':label;}};
 const check=async(force=false)=>{const sequence=++statusSequence,key=JSON.stringify(context());try{const value=await signedState({origin,token,session,context,force});if(sequence===statusSequence&&key===JSON.stringify(context())){signed=value;paint();}return value;}catch{return false;}};
 const save=()=>{const url=URL.createObjectURL(new Blob([ready.raw],{type:'application/pdf'})),a=n('a');a.href=url;a.download=ready.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);};
 button.onclick=async()=>{if(busy||signed)return;busy=true;button.disabled=true;let note=button.nextElementSibling;if(!note?.classList.contains('signing-bundle-status')){note=n('small');note.className='signing-bundle-status';note.setAttribute('role','status');button.after(note);}
 try{
  if(await check(true))return;
  if(!await beforeDownload())return;
  const c=context(),key=JSON.stringify(c),base='/safety-features/half-year-reviews/plans/'+encodeURIComponent(c.plan),q='?'+new URLSearchParams({period:c.period});
  const current=()=>{session();if(JSON.stringify(context())!==key)throw Error('평가내용이 바뀌었습니다. 다시 눌러 최신 파일을 받아 주세요.');};
  const api=async(path,options={})=>{current();const r=await fetch(origin+path,{...options,cache:'no-store',headers:{Authorization:'Bearer '+token,...options.headers}});current();if(!r.ok)throw Error('파일을 준비하지 못했습니다. 다시 눌러 주세요.');return r;};
  if(ready?.key===key){save();return;}
  ready=null;button.textContent='서명용 파일 준비 중…';note.textContent='4종 평가서를 확인하고 있습니다.';
  let result=await(await api(base+'/weekly-pdf'+q)).json();
  if(!result.ready){
   const prepared=await(await api(base+'/signature-bundle'+q)).json();
   if(!prepared.eligible){note.textContent='4종 평가의 작성내용을 모두 저장하고 완료해 주세요.';return;}
   if(prepared.missing?.length&&!confirm(prepared.missing.map(r=>r.label).join(', ')+'이 아직입니다. 다운로드 받으시겠습니까?'))return;
   result=await(await api(base+'/signature-bundle'+q,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:'download-'+crypto.randomUUID().replaceAll('-',''),fingerprint:prepared.fingerprint,allow_incomplete:!!prepared.missing?.length})})).json();
   const deadline=Date.now()+180000;
   while(result.status!=='READY'){
    if(result.status==='FAILED')throw Error('파일을 준비하지 못했습니다. 다시 눌러 주세요.');
    if(Date.now()>=deadline)throw Error('파일을 준비 중입니다. 잠시 후 다시 눌러 주세요.');
    note.textContent='서명용 평가서 준비 중 · '+(result.completed_parts||0)+' / '+(result.total_parts||4);
    await new Promise(resolve=>setTimeout(resolve,1500));
    result=await(await api(base+'/signature-bundle/'+result.id+q)).json();
   }
  }else if(result.missing?.length&&!confirm(result.missing.map(r=>r.label).join(', ')+'이 아직입니다. 다운로드 받으시겠습니까?'))return;
  current();const raw=await(await api(base+'/signature-bundle/'+result.id+'/file'+q)).arrayBuffer();
  if(raw.byteLength!==result.result.bytes||await digest(raw)!==result.result.sha256)throw Error('파일을 다시 확인해 주세요.');
  current();ready={raw,filename:result.filename,key};save();note.textContent='서명용 4종 평가서를 받았습니다.';
 }catch(e){note.textContent=/[가-힣]/.test(e.message||'')?e.message:'인터넷 연결을 확인한 뒤 다시 눌러 주세요.';}
 finally{busy=false;paint();}
 };button.refresh=()=>{const key=JSON.stringify(context()),changed=key!==lastContext;lastContext=key;if(ready&&ready.key!==key)ready=null;signed=false;paint();void check(changed);};void check();return button;
}
