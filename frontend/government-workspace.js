/* Government forms and two-way HQ correspondence. Uses the existing BESMA session. */
const API='https://api.besma.co.kr';
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(label,fn)=>{const b=node('button',label);b.type='button';b.onclick=fn;return b;};
let session='',context=null,pending=false,settingsRoot=null,contactDialog=null,contactState=null;
let catalog=null,folders=[],filter='',visibility='ALL';
async function api(path,options={}){
 const token=localStorage.getItem('besma_token');if(!token)throw Error('로그인이 필요합니다.');
 const r=await fetch(API+path,{...options,headers:{Authorization:'Bearer '+token,...options.headers},cache:'no-store'});
 if(token!==localStorage.getItem('besma_token'))throw Error('로그인 계정이 변경됐습니다.');
 if(!r.ok)throw Error(r.status===403?'이 작업의 권한이 없습니다.':'처리하지 못했습니다. ('+r.status+')');return r.json();
}
function modal(title){const d=node('dialog',undefined,'cm-dialog gov-dialog');d.append(node('h2',title),button('닫기',()=>d.close()));d.addEventListener('close',()=>{if(contactDialog===d){contactDialog=null;contactState=null;}d.remove();});document.body.append(d);d.showModal();return d;}
const put=(url,payload)=>api(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
async function loadSettings(){
 if(!settingsRoot)return;try{const result=await Promise.all([api('/document-explorer/government-document-catalog'),api('/document-explorer/government-folders')]);catalog=result[0];folders=result[1].folders;renderSettings();}catch(e){settingsRoot.replaceChildren(node('h2','관급공사 공개 설정'),node('p',e.message),button('다시 시도',loadSettings));}
}
function renderSettings(){
 if(!settingsRoot||!catalog)return;settingsRoot.replaceChildren(node('h2','전체 서류목록 · 관급공사 공개 설정'));
 settingsRoot.append(node('p','공개용 사본이 등록되고 폴더와 파일의 제공 설정이 모두 허용된 양식만 관급 현장에 표시됩니다.'),node('strong','전체 '+catalog.total+'건 · 공개 후보 '+catalog.public_candidates+'건 · 현재 공개 '+catalog.public+'건 · 비공개 '+catalog.private+'건'));
 const tools=node('div',undefined,'cm-tools');const search=node('input');search.placeholder='폴더·서류명 검색';search.value=filter;search.oninput=()=>{filter=search.value;drawCatalog();};search.setAttribute('aria-label','서류 검색');tools.append(search);
 const select=node('select');select.setAttribute('aria-label','공개 상태');for(const [v,t] of [['ALL','공개 상태 전체'],['PUBLIC','공개'],['PRIVATE','비공개']]){const o=node('option',t);o.value=v;select.append(o);}select.value=visibility;select.onchange=()=>{visibility=select.value;drawCatalog();};tools.append(select,button('목록 새로고침',loadSettings));settingsRoot.append(tools);
 const fs=node('details');fs.append(node('summary','폴더별 공개 설정'));
 for(const f of folders){const row=node('div',undefined,'gov-folder');row.append(node('span',f.folder.replace(/^관급 공개 양식\//,'')));const b=button(f.visible?'공개 · 비공개로 변경':'비공개 · 공개로 변경',async()=>{b.disabled=true;try{await put('/document-explorer/government-folders',{folder:f.folder,visible:!f.visible});await loadSettings();}catch(e){row.append(node('p',e.message));b.disabled=false;}});row.append(b);fs.append(row);}settingsRoot.append(fs);
 const table=node('div',undefined,'cm-table-wrap');table.id='gov-catalog';settingsRoot.append(table);drawCatalog();
}
async function uploadCopy(item){
 const d=modal('공개용 사본 등록');d.append(node('p',item.name),node('p','관급 현장에 제공할 내용을 확인한 파일을 선택하세요.'));
 const input=node('input');input.type='file';input.setAttribute('aria-label','공개용 양식');d.append(input);const info=node('p');
 const send=button('사본 저장',async()=>{send.disabled=true;try{const file=input.files[0];if(!file)throw Error('파일을 선택하세요.');if(file.name!==item.name)throw Error('목록과 같은 이름의 파일을 선택하세요.');const form=new FormData();form.append('relative_path','관급 공개 양식/'+item.relative_path);form.append('file',file);await api('/document-explorer/upload',{method:'POST',body:form});await loadSettings();d.close();}catch(e){info.textContent=e.message;send.disabled=false;}});d.append(send,info);
}
function drawCatalog(){
 const host=settingsRoot?.querySelector('#gov-catalog');if(!host)return;host.replaceChildren();const table=node('table');const head=node('tr');['폴더','서류명','검토 분류','실제 공개 상태','제공 설정'].forEach(t=>head.append(node('th',t)));const thead=node('thead');thead.append(head);table.append(thead);const body=node('tbody');
 for(const item of catalog.items.filter(i=>(visibility==='ALL'||i.visibility===visibility)&&(!filter||(i.folder+' '+i.name).toLowerCase().includes(filter.toLowerCase())))){
  const row=node('tr');row.append(node('td',item.folder),node('td',item.name),node('td',item.recommended_visibility==='PUBLIC_CANDIDATE'?'공개 후보':'비공개 권고'),node('td',item.visibility==='PUBLIC'?'공개':'비공개'));const actions=node('td');
  const b=button(item.file_enabled?'제공 허용 · 제한하기':'제공 제한 · 허용하기',async()=>{b.disabled=true;try{await put('/document-explorer/government-files',{relative_path:item.relative_path,visible:!item.file_enabled});await loadSettings();}catch(e){actions.append(node('p',e.message));b.disabled=false;}});b.disabled=!item.public_copy_prepared;actions.append(b);
  if(!item.public_folder_visible)actions.append(node('small','폴더 비공개'));actions.append(button(item.public_copy_prepared?'공개 사본 갱신':'공개용 사본 등록',()=>uploadCopy(item)));row.append(actions);body.append(row);
 }table.append(body);host.append(table);
}
async function openContact(){
 if(contactDialog){contactDialog.focus();return;}
 const d=modal(context.side==='HQ'?'관급공사 현장 소통':'본사 소통');contactDialog=d;
 const status=node('p','대화 목록을 불러오고 있습니다.');d.append(status);
 try{
  const sites=context.side==='HQ'?(await api('/government-contact/sites')).items:[{site_id:context.site_id,site_name:context.site_name}];if(contactDialog!==d)return;
  if(!sites.length){status.textContent='활성 관급 현장이 없습니다.';return;}
  const selector=node('select');selector.setAttribute('aria-label','소통 현장');for(const s of sites){const o=node('option',s.site_name+(s.unread_count?' · 미확인 '+s.unread_count:''));o.value=String(s.site_id);selector.append(o);}d.append(selector);
  const history=node('div',undefined,'gov-message-list');history.setAttribute('aria-live','polite');d.append(history);const older=button('이전 대화',()=>loadMessages(true));older.hidden=true;d.append(older);
  const text=node('textarea');text.rows=3;text.maxLength=4000;text.placeholder='본사와 현장에 전달할 내용을 입력하세요.';text.setAttribute('aria-label','전달 내용');d.append(text);
  const send=button('등록',async()=>{send.disabled=true;try{if(!text.value.trim())throw Error('전달 내용을 입력하세요.');await api('/government-contact/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site_id:contactState.siteId,body:text.value.trim()})});text.value='';await loadMessages();}catch(e){status.textContent=e.message;}finally{send.disabled=false;}});d.append(send,button('새로고침',()=>loadMessages()));
  contactState={siteId:Number(selector.value),items:[],history,status,older,pending:false};selector.onchange=()=>{contactState.siteId=Number(selector.value);contactState.items=[];loadMessages();};await loadMessages();
 }catch(e){status.textContent=e.message;}
}
async function loadMessages(previous=false){
 const state=contactState;if(!state||state.pending||!contactDialog)return;state.pending=true;const siteId=state.siteId;
 try{let path='/government-contact/messages?site_id='+siteId;if(previous&&state.items.length)path+='&before_id='+state.items[0].id;const payload=await api(path);if(contactState!==state||state.siteId!==siteId)return;
  state.items=previous?[...payload.items,...state.items]:payload.items;state.older.hidden=!payload.has_more;state.status.textContent=payload.site_name+' · '+state.items.length+'개 대화';state.history.replaceChildren();
  for(const m of state.items){const row=node('article',undefined,m.sender_side===context.side?'gov-message own':'gov-message');row.append(node('strong',(m.sender_side==='HQ'?'본사':'현장')+' · '+m.sender_name),node('p',m.body),node('small',new Date(m.created_at.endsWith('Z')?m.created_at:m.created_at+'Z').toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' · '+(m.read_at?'읽음':'미확인')));state.history.append(row);}
  if(!previous&&state.items.length){state.history.scrollTop=state.history.scrollHeight;await api('/government-contact/read?site_id='+siteId+'&through_id='+state.items.at(-1).id,{method:'POST'});}
 }catch(e){state.status.textContent=e.message;}finally{state.pending=false;}
}
async function sitePriority(){
 const host=document.querySelector('.cm-gov-info');if(!host||document.querySelector('#gov-site-priority'))return;
 const panel=node('section',undefined,'collection-monitor');panel.id='gov-site-priority';host.after(panel);panel.append(node('h2','우선 취합 서류'));
 try{const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(new Date());const payload=await api('/documents/requirements/status?period=all&site_id='+context.site_id+'&date='+today);if(!panel.isConnected)return;
  const codes=['GOV_RISK_INITIAL','GOV_MANAGER_APPOINTMENT','GOV_SAFETY_MANAGER_APPOINTMENT','GOV_SUPERVISOR_DESIGNATION','GOV_RISK_MONTHLY','GOV_NONCONFORMITY_LEDGER','GOV_WORKER_OPINION_LEDGER'];
  panel.append(node('p','착공 시 필수 서류 4종과 주기 제출 서류 3종을 먼저 제출합니다.'));
  const labels=['최초 위험성평가','안전보건관리책임자 지정서','안전관리자 선임계','관리감독자 지정서','위험성평가','부적합사항 관리대장','의견청취 관리대장'];
  for(const [index,code] of codes.entries()){const item=payload.items.find(i=>i.document_type_code===code);if(!item)continue;if(index===0||index===4)panel.append(node('h3',index===0?'착공 시 필수 서류':'주기 제출 서류'));const row=node('div',undefined,'gov-folder');const status=item.current_cycle_status||item.status;row.append(node('span',labels[index]+' · '+({NOT_SUBMITTED:'미제출',SUBMITTED:'제출됨',IN_REVIEW:'검토중',APPROVED:'승인',REJECTED:'반려',NOT_REQUIRED:'대상 아님'}[status]||status)),button('업로드',()=>uploadPriority(item,today)));panel.append(row);}
 }catch(e){panel.append(node('p',e.message));}
}
function uploadPriority(item,today){
 const d=modal(item.title);const date=node('input');date.type='date';date.value=today;date.setAttribute('aria-label','제출 기준일');const file=node('input');file.type='file';file.setAttribute('aria-label','제출서류');const note=node('p');d.append(date,file);const b=button('업로드',async()=>{b.disabled=true;try{if(!file.files[0])throw Error('서류를 선택하세요.');const f=new FormData();f.append('site_id',String(context.site_id));f.append('requirement_id',String(item.requirement_id));f.append('document_type_code',item.document_type_code);f.append('work_date',date.value);f.append('file',file.files[0]);await api('/document-submissions/upload',{method:'POST',body:f});d.close();document.querySelector('#gov-site-priority')?.remove();await sitePriority();window.dispatchEvent(new Event('besma-document-refresh'));}catch(e){note.textContent=e.message;b.disabled=false;}});d.append(b,note);
}
async function reconcile(){
 const token=localStorage.getItem('besma_token')||'';
 if(token!==session){session=token;context=null;settingsRoot?.remove();settingsRoot=null;document.querySelectorAll('.gov-contact-menu,.gov-contact-page,#gov-site-priority').forEach(n=>n.remove());contactDialog?.close();}
 if(!token)return;
 if(!context){if(pending)return;pending=true;try{context=await api('/government-contact/access');}catch{return;}finally{pending=false;}}
 if(!context.allowed)return;
 const anchor=document.querySelector(context.side==='HQ'?'a[href="/hq-safe/documents"]':'a[href="/site/documents"]');
 if(anchor&&!document.querySelector('.gov-contact-menu')){const b=button(context.side==='HQ'?'관급공사 현장 소통':'본사 소통',openContact);b.className='gov-contact-menu';anchor.after(b);}
 if(context.side==='HQ'&&location.pathname==='/hq-safe/settings'){
  const host=document.querySelector('.doc-settings-page');if(host&&!host.querySelector('#gov-settings')){settingsRoot=node('section',undefined,'collection-monitor');settingsRoot.id='gov-settings';host.querySelector('header')?.after(settingsRoot);if(!settingsRoot.isConnected)host.prepend(settingsRoot);loadSettings();}
 }else if(settingsRoot){settingsRoot.remove();settingsRoot=null;}
 if(context.side==='SITE'&&location.pathname==='/site/documents')await sitePriority();
 const visibleHost=context.side==='HQ'?document.querySelector('#collection-monitor,#gov-settings'):document.querySelector('#gov-site-priority');
 if(visibleHost&&!visibleHost.querySelector('.gov-contact-page')){const b=button(context.side==='HQ'?'관급공사 현장 소통':'본사 소통',openContact);b.className='gov-contact-page';visibleHost.prepend(b);}
}
let scheduled=false;function schedule(){if(scheduled)return;scheduled=true;setTimeout(()=>{scheduled=false;reconcile();},250);}
new MutationObserver(schedule).observe(document.documentElement,{subtree:true,childList:true});addEventListener('storage',schedule);addEventListener('popstate',schedule);setInterval(schedule,3000);setInterval(()=>{if(document.visibilityState==='visible')loadMessages();},15000);schedule();
