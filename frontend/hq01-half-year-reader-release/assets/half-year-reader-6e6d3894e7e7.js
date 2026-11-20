const API='https://api.besma.co.kr',BASE='/safety-features/half-year-reader',token=localStorage.getItem('besma_token');
const $=id=>document.getElementById(id),el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
let listing=null,chosen=null,state=null,form='report',generation=0,previewGeneration=0,fileGeneration=0,fileURL=null;
const labels={NOT_STARTED:'미작성',IN_PROGRESS:'평가 중',COMPLETED:'완료'};
function session(){if(!token||localStorage.getItem('besma_token')!==token)throw Error('로그인이 필요합니다.');}
async function response(path){session();const result=await fetch(API+BASE+path,{cache:'no-store',headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(30000)});session();if(!result.ok){let text='';try{const data=await result.json();if(typeof data.detail==='string')text=data.detail;}catch{}if(result.status===401)location.replace('/login?form=1');throw Error(text||'반기평가 자료를 확인하지 못했습니다.');}return result;}
async function json(path){return(await response(path)).json();}
function notice(text){$('status').textContent=text;}
function paintSites(){
  const query=$('site-search').value.trim().toLocaleLowerCase('ko'),items=(listing?.items||[]).filter(item=>item.site.toLocaleLowerCase('ko').includes(query));$('site-count').textContent='현장 '+items.length+'곳';$('sites').replaceChildren();
  for(const item of items){const b=el('button');b.type='button';b.dataset.plan=item.public_id;b.setAttribute('aria-current',String(chosen?.public_id===item.public_id));b.append(el('span',item.site),el('small',labels[item.status]||'확인 필요','state '+item.status));b.onclick=()=>void openSite(item);$('sites').append(b);}
  if(!items.length)$('sites').append(el('p','해당 현장이 없습니다.'));
}
async function load(){
  const seq=++generation;previewGeneration++;state=null;listing=null;$('sites').replaceChildren(el('p','조회 중입니다.'));$('site-count').textContent='현장';$('assessment-frame').hidden=true;$('forms').replaceChildren();$('files').replaceChildren();if($('file-dialog').open)$('file-dialog').close();$('refresh').disabled=true;notice('반기평가를 확인하고 있습니다.');
  try{const value=await json('/overview?'+new URLSearchParams({period:$('period').value}));if(seq!==generation)return;if(value.headquarters_reader!==true||value.can_write!==false||!Array.isArray(value.items))throw Error('조회 권한을 확인해 주세요.');listing=value;paintSites();notice('조회 전용 · '+value.items.length+'개 현장');
    const queryPlan=new URLSearchParams(location.search).get('plan');const next=value.items.find(item=>item.public_id===chosen?.public_id)||value.items.find(item=>item.public_id===queryPlan)||value.items.find(item=>item.status==='COMPLETED')||value.items[0];
    if(next)await openSite(next);else{chosen=null;state=null;$('site-title').textContent='등록된 반기평가 현장이 없습니다.';$('forms').replaceChildren();$('assessment-frame').hidden=true;$('files').replaceChildren();}
  }catch(error){if(seq===generation){notice(error.message);$('assessment-frame').hidden=true;}}finally{if(seq===generation)$('refresh').disabled=false;}
}
async function openSite(item){
  const seq=++previewGeneration;chosen=item;state=null;paintSites();$('site-title').textContent=item.site;$('assessment-status').textContent='평가 내용을 확인하고 있습니다.';$('assessment-frame').hidden=true;$('forms').replaceChildren();$('files').replaceChildren();
  try{const value=await json('/plans/'+encodeURIComponent(item.public_id)+'?'+new URLSearchParams({period:$('period').value}));if(seq!==previewGeneration)return;state=value;
    for(const id of listing.catalog.order){const button=el('button',listing.catalog.forms[id].title);button.type='button';button.dataset.form=id;button.onclick=()=>{form=id;void showForm();};$('forms').append(button);}
    for(const file of value.data.files||[]){const button=el('button',file.filename||file.caption||'첨부자료');button.type='button';button.onclick=()=>void openFile(file);$('files').append(button);}
    if(!value.data.files?.length)$('files').append(el('p','등록된 첨부자료가 없습니다.'));
    if(!listing.catalog.order.includes(form))form=listing.catalog.order[0];await showForm();
  }catch(error){if(seq===previewGeneration)$('assessment-status').textContent=error.message;}
}
async function showForm(){
  if(!state||!chosen)return;const schema=listing.catalog.forms[form],previous=$('subject').value;$('subject').replaceChildren();$('subject-label').hidden=!schema.needs_subject;
  for(const button of $('forms').querySelectorAll('button'))button.setAttribute('aria-pressed',String(button.dataset.form===form));
  if(schema.needs_subject){for(const subject of state.data.subjects?.[form]||[]){const option=el('option',subject.name||(form==='supervisor'?'현장 단위':'평가 대상'));option.value=subject.id;$('subject').append(option);}if([...$('subject').options].some(option=>option.value===previous))$('subject').value=previous;if(!$('subject').value){$('assessment-frame').hidden=true;$('assessment-status').textContent='등록된 평가 대상이 없습니다.';return;}}
  await renderForm();
}
async function renderForm(){
  const seq=++previewGeneration;if(!state||!chosen)return;const subject=listing.catalog.forms[form].needs_subject?$('subject').value:'site',saved=state.data.assessments?.[form+':'+subject];$('assessment-status').textContent=saved?.completed?'저장된 평가내용 · 조회 전용':saved?.draft?'작성 중인 평가내용 · 조회 전용':'저장된 평가내용이 없습니다. 첨부자료에서 평가서를 확인하세요.';$('assessment-frame').hidden=true;
  try{const html=await(await response('/plans/'+encodeURIComponent(chosen.public_id)+'/preview/'+encodeURIComponent(form)+'/'+encodeURIComponent(subject)+'?'+new URLSearchParams({period:$('period').value}))).text();if(seq!==previewGeneration)return;$('assessment-frame').srcdoc=html;$('assessment-frame').hidden=false;}catch(error){if(seq===previewGeneration)$('assessment-status').textContent=error.message;}
}
async function openFile(file){
  const seq=++fileGeneration;$('file-title').textContent=file.filename||'첨부자료';$('file-content').replaceChildren(el('p','자료를 확인하고 있습니다.'));$('file-dialog').showModal();
  try{const result=await response('/plans/'+encodeURIComponent(chosen.public_id)+'/files/'+encodeURIComponent(file.id)+'?'+new URLSearchParams({period:$('period').value})),blob=await result.blob();if(!$('file-dialog').open||seq!==fileGeneration)return;if(fileURL)URL.revokeObjectURL(fileURL);fileURL=URL.createObjectURL(blob);$('file-content').replaceChildren();if(blob.type.startsWith('image/')){const image=el('img');image.src=fileURL;image.alt=file.filename||'첨부자료';$('file-content').append(image);}else if(blob.type==='application/pdf'){const frame=el('iframe');frame.src=fileURL;frame.title=file.filename||'PDF 자료';frame.referrerPolicy='no-referrer';$('file-content').append(frame);}else $('file-content').append(el('p','화면에서 볼 수 있는 PDF·이미지 형식이 아닙니다.'));}catch(error){if(seq===fileGeneration)$('file-content').replaceChildren(el('p',error.message));}
}
$('close-file').onclick=()=>$('file-dialog').close();$('file-dialog').addEventListener('close',()=>{fileGeneration++;if(fileURL)URL.revokeObjectURL(fileURL);fileURL=null;$('file-content').replaceChildren();});
$('refresh').onclick=()=>void load();$('period').onchange=()=>void load();$('site-search').oninput=paintSites;$('subject').onchange=()=>void renderForm();
window.addEventListener('storage',event=>{if((event.key==='besma_token'||event.key===null)&&localStorage.getItem('besma_token')!==token){generation++;previewGeneration++;$('assessment-frame').srcdoc='';$('sites').replaceChildren();location.replace('/login?form=1');}});
const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit'}).formatToParts(new Date()).map(p=>[p.type,p.value])),year=Number(parts.year),requested=new URLSearchParams(location.search).get('period'),period=/^20\d{2}-H[12]$/.test(requested||'')?requested:year+'-H'+(Number(parts.month)<=6?'1':'2');
for(const y of [...new Set([year-1,year,year+1,Number(period.slice(0,4))])].sort())for(const h of [1,2]){const option=el('option',y+'년 '+(h===1?'상반기':'하반기'));option.value=y+'-H'+h;$('period').append(option);}$('period').value=period;
if(!token)location.replace('/login?form=1');else void load();
