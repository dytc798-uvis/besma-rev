/* Government forms and two-way HQ correspondence. Uses the existing BESMA session. */
const API='https://api.besma.co.kr';
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(label,fn)=>{const b=node('button',label);b.type='button';b.onclick=fn;return b;};
let session='',context=null,pending=false,settingsRoot=null,contactDialog=null,contactState=null;
let catalog=null,folders=[],filter='',visibility='ALL';
async function api(path,options={}){
 const token=localStorage.getItem('besma_token');if(!token)throw Error('로그인이 필요합니다.');
 const key=workspaceKey(),preview=previewSite();
 if(preview){if(!['GET','HEAD','OPTIONS'].includes((options.method||'GET').toUpperCase()))throw Error('관점 전환에서는 조회만 가능합니다.');if(/^\/(government-contact|document-explorer|collection-monitor)\//.test(path))path+=(path.includes('?')?'&':'?')+'preview_site_id='+encodeURIComponent(preview);}
 const r=await fetch(API+path,{...options,headers:{Authorization:'Bearer '+token,...options.headers},cache:'no-store'});
 if(token!==localStorage.getItem('besma_token')||key!==workspaceKey())throw Error('로그인 계정 또는 관점이 변경됐습니다.');
 if(!r.ok)throw Error(r.status===403?'이 작업의 권한이 없습니다.':'처리하지 못했습니다. ('+r.status+')');return r.json();
}
function modal(title){const d=node('dialog',undefined,'cm-dialog gov-dialog');d.append(node('h2',title),button('닫기',()=>d.close()));d.addEventListener('close',()=>{if(contactDialog===d){contactDialog=null;contactState=null;}d.remove();});document.body.append(d);d.showModal();return d;}
const put=(url,payload)=>api(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
function previewSite(){return ['SITE_STAFF','SITE_MANAGER'].includes(localStorage.getItem('besma_test_persona'))?localStorage.getItem('besma_test_site_context_id')||'':'';}
function workspaceKey(){return (localStorage.getItem('besma_token')||'')+'|'+(localStorage.getItem('besma_test_persona')||'')+'|'+previewSite();}
// Keep the existing Vue document browser on the same public-only preview scope.
const originalXhrOpen=XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open=function(method,url,...rest){const preview=previewSite();if(preview){const parsed=new URL(url,location.href);if(parsed.origin===API&&/^\/(document-explorer|government-contact|collection-monitor)\//.test(parsed.pathname)){parsed.searchParams.set('preview_site_id',preview);url=parsed.href;}}return originalXhrOpen.call(this,method,url,...rest);};
async function loadSettings(){
 if(!settingsRoot)return;if(collectionDirty){renderSettings();drawCollectionSettings();return;}try{const result=await Promise.all([api('/document-explorer/government-document-catalog'),api('/document-explorer/government-folders')]);catalog=result[0];folders=result[1].folders;renderSettings();await loadCollectionSettings();}catch(e){settingsRoot.replaceChildren(node('h2','관급공사 공개 설정'),node('p',e.message),button('다시 시도',loadSettings));}
}
function renderSettings(){
 if(!settingsRoot||!catalog)return;settingsRoot.replaceChildren(node('h2','전체 서류목록 · 관급공사 공개 설정'));
 const collectionPanel=node('div');collectionPanel.id='gov-collection-settings';settingsRoot.append(collectionPanel);
 settingsRoot.append(node('p','공개용 사본이 등록되고 폴더와 파일의 제공 설정이 모두 허용된 양식만 관급 현장에 표시됩니다.'),node('strong','전체 '+catalog.total+'건 · 공개 후보 '+catalog.public_candidates+'건 · 현재 공개 '+catalog.public+'건 · 비공개 '+catalog.private+'건'));
 const tools=node('div',undefined,'cm-tools');const search=node('input');search.placeholder='폴더·서류명 검색';search.value=filter;search.oninput=()=>{filter=search.value;drawCatalog();};search.setAttribute('aria-label','서류 검색');tools.append(search);
 const select=node('select');select.setAttribute('aria-label','공개 상태');for(const [v,t] of [['ALL','공개 상태 전체'],['PUBLIC','공개'],['PRIVATE','비공개']]){const o=node('option',t);o.value=v;select.append(o);}select.value=visibility;select.onchange=()=>{visibility=select.value;drawCatalog();};tools.append(select,button('목록 새로고침',loadSettings));settingsRoot.append(tools);
 const fs=node('details');fs.append(node('summary','폴더별 공개 설정'));
 for(const f of folders){const row=node('div',undefined,'gov-folder');row.append(node('span',f.folder.replace(/^관급 공개 양식\//,'')));const b=button(f.visible?'공개 · 비공개로 변경':'비공개 · 공개로 변경',async()=>{b.disabled=true;try{await put('/document-explorer/government-folders',{folder:f.folder,visible:!f.visible});await loadSettings();}catch(e){row.append(node('p',e.message));b.disabled=false;}});row.append(b);fs.append(row);}settingsRoot.append(fs);
 const table=node('div',undefined,'cm-table-wrap');table.id='gov-catalog';settingsRoot.append(table);drawCatalog();
}
let collectionConfig=null,collectionDirty=false,collectionSaving=false;
async function loadCollectionSettings(){const host=settingsRoot?.querySelector('#gov-collection-settings');if(!host)return;try{collectionConfig=await api('/collection-monitor/settings');collectionDirty=false;drawCollectionSettings();}catch(e){host.replaceChildren(node('p',e.message));}}
function collectionSelect(values,value,label,change){const input=node('select');input.setAttribute('aria-label',label);for(const [v,text] of values){const option=node('option',text);option.value=v;input.append(option);}input.value=value;input.onchange=()=>{change(input.value);collectionDirty=true;drawCollectionSettings();};return input;}
function collectionInput(value,label,change){const input=node('input');input.value=value;input.maxLength=100;input.setAttribute('aria-label',label);input.oninput=()=>{change(input.value);collectionDirty=true;};return input;}
function drawCollectionSettings(){const host=settingsRoot?.querySelector('#gov-collection-settings');if(!host||!collectionConfig)return;host.replaceChildren(node('h2','관급공사 취합 서류 설정'),node('p','서류명과 구분명은 NAS 저장 폴더에도 적용됩니다.'));
const groups=node('div',undefined,'gov-collection-groups');for(const group of collectionConfig.groups.slice().sort((a,b)=>a.order-b.order)){const field=node('label',({MONTHLY:'월간',WEEKLY:'주간',EVENT:'착공시'})[group.id]+' 구분명');field.append(collectionInput(group.label,'구분명 '+group.id,value=>{group.label=value;}));const earlier=button('앞으로',()=>{const sorted=collectionConfig.groups.slice().sort((a,b)=>a.order-b.order);const index=sorted.findIndex(g=>g.id===group.id);if(index>0){[group.order,sorted[index-1].order]=[sorted[index-1].order,group.order];collectionDirty=true;drawCollectionSettings();}});earlier.disabled=collectionConfig.groups.slice().sort((a,b)=>a.order-b.order)[0].id===group.id;field.append(earlier);groups.append(field);}host.append(groups);
const wrap=node('div',undefined,'cm-table-wrap');const table=node('table');table.className='gov-collection-table';const head=node('tr');['서류명 / 문서 폴더','제출 주기','상위 취합폴더','우선 취합','사용'].forEach(text=>head.append(node('th',text)));const thead=node('thead');thead.append(head);table.append(thead);const tbody=node('tbody');
for(const item of collectionConfig.items.slice().sort((a,b)=>{const groupOrder=item=>collectionConfig.groups.find(g=>g.id===(['EVENT','ADHOC'].includes(item.frequency)?'EVENT':item.frequency==='WEEKLY'?'WEEKLY':'MONTHLY'))?.order||0;return groupOrder(a)-groupOrder(b)||a.order-b.order;})){const row=node('tr');row.dataset.code=item.code||'';const name=node('td');name.append(collectionInput(item.title,'서류명 '+(item.code||'신규'),value=>{if(item.collection_folder===item.title)item.collection_folder=value;item.title=value;const folderInput=row.querySelector('td:nth-child(3) input');if(folderInput)folderInput.value=item.collection_folder;}));const freq=node('td');const frequencies=[['MONTHLY','월간'],['WEEKLY','주간'],['EVENT','착공시']];if(!frequencies.some(x=>x[0]===item.frequency))frequencies.push([item.frequency,({HALF_YEARLY:'반기',QUARTERLY:'분기',YEARLY:'연간',DAILY:'일간',ADHOC:'해당 시'})[item.frequency]||item.frequency]);freq.append(collectionSelect(frequencies,item.frequency,'제출 주기 '+(item.code||'신규'),value=>{item.frequency=value;item.group_id=['EVENT','ADHOC'].includes(value)?'EVENT':value==='WEEKLY'?'WEEKLY':'MONTHLY';}));const folder=node('td');folder.append(collectionInput(item.collection_folder,'상위 취합폴더 '+(item.code||'신규'),value=>{item.collection_folder=value;}));const toggle=(key,label)=>{const td=node('td');const checkbox=node('input');checkbox.type='checkbox';checkbox.checked=item[key];checkbox.setAttribute('aria-label',label+' '+(item.code||'신규'));checkbox.onchange=()=>{item[key]=checkbox.checked;collectionDirty=true;};td.append(checkbox);return td;};row.append(name,freq,folder,toggle('priority','우선 취합'),toggle('enabled','사용'));tbody.append(row);}table.append(tbody);wrap.append(table);host.append(wrap);
const tools=node('div',undefined,'cm-tools');tools.append(button('취합 서류 추가',()=>{const title='새 취합 서류 '+(collectionConfig.items.filter(i=>!i.code).length+1);collectionConfig.items.push({code:null,title,frequency:'MONTHLY',group_id:'MONTHLY',collection_folder:title,priority:true,enabled:true,required:true,order:collectionConfig.items.length});collectionDirty=true;drawCollectionSettings();}));const status=node('p');status.setAttribute('aria-live','polite');const save=button(collectionSaving?'저장중':'취합 설정 저장',async()=>{collectionSaving=true;save.disabled=true;try{collectionConfig=await put('/collection-monitor/settings',collectionConfig);collectionDirty=false;collectionSaving=false;drawCollectionSettings();const note=host.querySelector('[aria-live]');note.textContent='저장했습니다. 현장 제출 목록과 다음 NAS 저장에 적용됩니다.';window.dispatchEvent(new Event('besma-document-refresh'));}catch(e){status.textContent=e.message;}finally{collectionSaving=false;save.disabled=false;}});save.disabled=collectionSaving;tools.append(save);host.insertBefore(tools,wrap);host.append(status,node('small','저장 경로: 상위 취합폴더 / 관급 / 구분명 / 제출월 / 현장 / 서류명'));
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
async function openContact(selectedId=null){
 if(contactDialog){contactDialog.focus();return;}
 const d=modal(context.side==='HQ'?'관급공사 현장 소통':'본사 소통');contactDialog=d;
 const status=node('p','대화 목록을 불러오고 있습니다.');d.append(status);
 try{
  const testing=context.test_mode||Number(selectedId)<0;
  const sites=testing?(await api('/government-contact/test-sites')).items:context.side==='HQ'?(await api('/government-contact/sites')).items:[{site_id:context.site_id,site_name:context.site_name}];if(contactDialog!==d)return;
  if(!sites.length){status.textContent='활성 관급 현장이 없습니다.';return;}
  if(testing)d.append(node('strong','검증용 소통'));
  const selector=node('select');selector.setAttribute('aria-label','소통 현장');for(const site of sites){const o=node('option',site.site_name);o.value=String(site.site_id);selector.append(o);}if(selectedId&&sites.some(s=>s.site_id===Number(selectedId)))selector.value=String(selectedId);d.append(selector);
  const subject=node('select');subject.setAttribute('aria-label','소통 구분');d.append(subject);
  const history=node('div',undefined,'gov-message-list');history.setAttribute('aria-live','polite');d.append(history);const older=button('이전 대화',()=>loadMessages(true));older.hidden=true;d.append(older);
  const text=node('textarea');text.rows=3;text.maxLength=4000;text.placeholder='문의 또는 답변을 입력하세요.';text.setAttribute('aria-label','전달 내용');if(!context.read_only)d.append(text);else d.append(node('p','관급 현장 관점 · 조회 전용'));
  const send=button('등록',async()=>{const state=contactState;if(!state||state.pending)return;send.disabled=true;try{if(!text.value.trim())throw Error('전달 내용을 입력하세요.');const selected=state.siteId;const category=state.category;await api('/government-contact/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site_id:selected,body:text.value.trim(),document_code:category==='GENERAL'?null:category})});if(contactState!==state||state.siteId!==selected||state.category!==category)return;text.value='';await loadMessages();}catch(e){status.textContent=e.message;}finally{send.disabled=false;}});d.append(send,button('새로고침',()=>loadMessages()));
  if(context.read_only){text.disabled=true;send.remove();}
  contactState={siteId:Number(selector.value),category:'GENERAL',items:[],history,status,older,subject,send,pending:false,generation:0};
  const changeSite=async()=>{const state=contactState;if(!state)return;state.siteId=Number(selector.value);state.items=[];state.category='GENERAL';state.generation++;send.disabled=true;try{const selected=state.siteId;const definitions=await api('/government-contact/subjects?site_id='+selected);if(contactState!==state||state.siteId!==selected)return;subject.replaceChildren();for(const item of definitions.items){const option=node('option',item.title);option.value=item.code||'GENERAL';subject.append(option);}subject.value='GENERAL';await loadMessages();}catch(e){status.textContent=e.message;}finally{send.disabled=false;}};
  selector.onchange=changeSite;subject.onchange=()=>{if(!contactState)return;contactState.category=subject.value;contactState.items=[];contactState.generation++;loadMessages();};await changeSite();
 }catch(e){status.textContent=e.message;}
}
function contactParams(state){return '&'+(state.category==='GENERAL'?'general_only=true':'document_code='+encodeURIComponent(state.category));}
async function loadMessages(previous=false){
 const state=contactState;if(!state||!contactDialog)return;const siteId=state.siteId,category=state.category,generation=++state.generation;state.pending=true;state.send.disabled=true;
 try{let path='/government-contact/messages?site_id='+siteId+contactParams(state);if(previous&&state.items.length)path+='&before_id='+state.items[0].id;const payload=await api(path);if(contactState!==state||state.siteId!==siteId||state.category!==category||state.generation!==generation)return;
  state.items=previous?[...payload.items,...state.items]:payload.items;state.older.hidden=!payload.has_more;state.status.textContent=payload.site_name+' · '+state.subject.selectedOptions[0]?.textContent+' · '+state.items.length+'개 대화';state.history.replaceChildren();
  if(!state.items.length)state.history.append(node('p','아직 소통 내역이 없습니다.'));
  for(const m of state.items){const row=node('article',undefined,m.sender_side===context.side?'gov-message own':'gov-message');row.append(node('strong',(m.sender_side==='HQ'?'본사':'현장')+' · '+m.sender_name),node('small',m.document_title||'일반 소통 (문서 없음)'),node('p',m.body),node('small',new Date(m.created_at.endsWith('Z')?m.created_at:m.created_at+'Z').toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' · '+(m.read_at?'읽음':'미확인')));state.history.append(row);}
  if(!previous&&state.items.length){state.history.scrollTop=state.history.scrollHeight;if(!context.read_only)await api('/government-contact/read?site_id='+siteId+'&through_id='+state.items.at(-1).id+contactParams(state),{method:'POST'});}
 }catch(e){if(contactState===state&&state.generation===generation)state.status.textContent=e.message;}finally{if(state.generation===generation){state.pending=false;state.send.disabled=false;}}
}
let contactHub=null,hubTesting=false,hubBusy=false;
async function drawContactHub(){
 if(!contactHub||hubBusy)return;hubBusy=true;const host=contactHub;
 try{const testing=context.test_mode||hubTesting;const sites=testing?(await api('/government-contact/test-sites')).items:context.side==='HQ'?(await api('/government-contact/sites')).items:[{site_id:context.site_id,site_name:context.site_name}];if(contactHub!==host)return;
  host.replaceChildren(node('h1','본사–관급현장 소통'),node('p','현장별로 일반 문의와 서류별 문의·답변을 주고받습니다.'));
  if(context.side==='HQ'){const tools=node('div',undefined,'cm-tools');for(const [value,label] of [[false,'관급 현장'],[true,'검증용 test1·test2·test3']]){const b=button(label,()=>{hubTesting=value;drawContactHub();});b.setAttribute('aria-pressed',String(testing===value));tools.append(b);}host.append(tools);}
  const list=node('div',undefined,'gov-contact-sites');for(const site of sites){const row=node('article');row.append(node('strong',site.site_name),node('small',site.unread_count?'미확인 '+site.unread_count+'건':'새 대화 없음'),button('소통하기',()=>openContact(site.site_id)));list.append(row);}host.append(list);
 }catch(e){host.replaceChildren(node('p',e.message),button('다시 시도',drawContactHub));}finally{hubBusy=false;}
}
function reconcileContactPage(){
 const paths=context.side==='HQ'?['/hq-safe/communications']:['/site/communications','/site/mobile/communications'];const visible=paths.includes(location.pathname);
 if(!visible){contactHub?.remove();contactHub=null;return;}
 const legacy=document.querySelector('.comm-page,.mobile-wrap');const host=legacy?.parentElement||document.querySelector('.layout-main');if(!host)return;if(legacy)legacy.dataset.govLegacyHidden='true';
 if(!contactHub?.isConnected){contactHub=node('section',undefined,'collection-monitor');contactHub.id='gov-contact-hub';if(legacy)legacy.after(contactHub);else host.append(contactHub);drawContactHub();}
}
function hideLegacyContact(){
 if(!context?.legacy_contact_hidden)return;
 for(const link of document.querySelectorAll('a[href="/hq-safe/communications"],a[href="/site/communications"],a[href="/site/mobile/communications"]'))link.dataset.govLegacyHidden='true';
 if(context.side!=='HQ')for(const card of document.querySelectorAll('.site-comm-card'))card.dataset.govLegacyHidden='true';
 if(!context.allowed&&['/hq-safe/communications','/site/communications','/site/mobile/communications'].includes(location.pathname)){const legacy=document.querySelector('.comm-page,.mobile-wrap');const host=legacy?.parentElement||document.querySelector('.layout-main');if(legacy)legacy.dataset.govLegacyHidden='true';if(host&&!document.querySelector('#gov-contact-hidden')){const note=node('p','관급공사 소통은 안전보건실과 해당 현장 계정으로 이용합니다.');note.id='gov-contact-hidden';if(legacy)legacy.after(note);else host.append(note);}}
}
async function sitePriority(refresh=false){
 const host=document.querySelector('.cm-gov-info');let panel=document.querySelector('#gov-site-priority');if(!host||(panel&&!refresh))return;
 if(!panel){panel=node('section',undefined,'collection-monitor');panel.id='gov-site-priority';host.after(panel);panel.append(node('h2','우선 취합 서류'));}
 try{const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(new Date());const payload=await api('/documents/requirements/status?period=all&site_id='+context.site_id+'&date='+today);if(!panel.isConnected)return;
  const config=await api('/collection-monitor/site-configuration');
  if(!panel.isConnected)return;panel.replaceChildren(node('h2','우선 취합 서류'),node('p',context.read_only?context.site_name+' · 관급 현장 관점 · 조회 전용':'월간·주간 서류를 먼저 확인하고 제출합니다.'));
  for(const group of config.groups.slice().sort((a,b)=>a.order-b.order)){const definitions=config.items.filter(i=>i.priority&&i.group_id===group.id).sort((a,b)=>a.order-b.order);if(!definitions.length)continue;panel.append(node('h3',group.label));for(const definition of definitions){const item=payload.items.find(i=>i.document_type_code===definition.code);if(!item)continue;const row=node('div',undefined,'gov-folder');const status=item.current_cycle_status||item.status;row.append(node('span',definition.title+' · '+({NOT_SUBMITTED:'미제출',SUBMITTED:'제출됨',UNDER_REVIEW:'검토중',IN_REVIEW:'검토중',APPROVED:'승인',REJECTED:'반려',NOT_REQUIRED:'대상 아님'}[status]||status)));if(!context.read_only)row.append(button('업로드',()=>uploadPriority({...item,title:definition.title},today)));panel.append(row);}}
  if(context.read_only){const original=[...document.querySelectorAll('.card-title')].find(e=>e.textContent.includes('현장 문서취합'))?.closest('.card');if(original)original.dataset.govLegacyHidden='true';const forms=await api('/document-explorer/list');if(!panel.isConnected)return;panel.append(node('h3','공개 양식'));for(const item of forms.items.filter(i=>i.relative_path.startsWith('base/관급 공개 양식/')))panel.append(node('p',item.name));if(!forms.items.some(i=>i.relative_path.startsWith('base/관급 공개 양식/')))panel.append(node('p','현재 공개된 양식이 없습니다.'));}
 }catch(e){panel.append(node('p',e.message));}
}
function uploadPriority(item,today){
 const d=modal(item.title);const date=node('input');date.type='date';date.value=today;date.setAttribute('aria-label','제출 기준일');const file=node('input');file.type='file';file.setAttribute('aria-label','제출서류');const note=node('p');d.append(date,file);const b=button('업로드',async()=>{b.disabled=true;try{if(!file.files[0])throw Error('서류를 선택하세요.');const f=new FormData();f.append('site_id',String(context.site_id));f.append('requirement_id',String(item.requirement_id));f.append('document_type_code',item.document_type_code);f.append('work_date',date.value);f.append('file',file.files[0]);await api('/document-submissions/upload',{method:'POST',body:f});d.close();document.querySelector('#gov-site-priority')?.remove();await sitePriority();window.dispatchEvent(new Event('besma-document-refresh'));}catch(e){note.textContent=e.message;b.disabled=false;}});d.append(b,note);
}
async function reconcile(){
 const token=localStorage.getItem('besma_token')||'',key=workspaceKey();
 if(key!==session){session=key;context=null;contactHub?.remove();contactHub=null;hubTesting=false;collectionConfig=null;collectionDirty=false;settingsRoot?.remove();settingsRoot=null;document.querySelectorAll('[data-gov-legacy-hidden]').forEach(n=>delete n.dataset.govLegacyHidden);document.querySelectorAll('.gov-contact-menu,.gov-settings-menu,.gov-contact-page,#gov-site-priority,#gov-contact-hidden').forEach(n=>n.remove());contactDialog?.close();}
 if(!token)return;
 if(!context){if(pending)return;pending=true;try{context=await api('/government-contact/access');}catch{return;}finally{pending=false;}}
 hideLegacyContact();
 const menu=document.querySelector('.layout-menu');
 if(menu&&context.can_manage_forms&&!localStorage.getItem('besma_test_persona')&&!document.querySelector('.gov-settings-menu')){const b=button('관급 양식 공개 설정',()=>location.assign('/hq-safe/settings#gov-settings'));b.className='gov-settings-menu gov-contact-menu';b.style.order='20';menu.append(b);}
 if(context.can_manage_forms&&!localStorage.getItem('besma_test_persona')&&location.pathname==='/hq-safe/settings'){
  const host=document.querySelector('.doc-settings-page');if(host&&!host.querySelector('#gov-settings')){settingsRoot=node('section',undefined,'collection-monitor');settingsRoot.id='gov-settings';host.querySelector('header')?.after(settingsRoot);if(!settingsRoot.isConnected)host.prepend(settingsRoot);loadSettings();}
 }else if(settingsRoot){settingsRoot.remove();settingsRoot=null;}
 if(!context.allowed)return;reconcileContactPage();
 if(menu&&!document.querySelector('.gov-contact-menu:not(.gov-settings-menu)')){const b=button(context.side==='HQ'?'관급공사 현장 소통':'본사 소통',()=>location.assign(context.side==='HQ'?'/hq-safe/communications':'/site/communications'));b.className='gov-contact-menu';b.style.order='6';menu.append(b);}
 if(context.side==='SITE'&&location.pathname==='/site/documents')await sitePriority();
 const visibleHost=context.side==='HQ'?document.querySelector('#collection-monitor,#gov-settings'):document.querySelector('#gov-site-priority');
 if(visibleHost&&!visibleHost.querySelector('.gov-contact-page')){const b=button(context.side==='HQ'?'관급공사 현장 소통':'본사 소통',()=>openContact());b.className='gov-contact-page';visibleHost.prepend(b);}
}
let scheduled=false;function schedule(){if(scheduled)return;scheduled=true;setTimeout(()=>{scheduled=false;reconcile();},250);}
new MutationObserver(schedule).observe(document.documentElement,{subtree:true,childList:true});addEventListener('storage',schedule);addEventListener('popstate',schedule);setInterval(schedule,3000);setInterval(()=>{if(context?.side==='SITE'&&location.pathname==='/site/documents'&&document.visibilityState==='visible')sitePriority(true);},30000);setInterval(()=>{if(document.visibilityState==='visible')loadMessages();},15000);schedule();

addEventListener('besma-government-contact',event=>{if(context?.allowed)openContact(event.detail?.site_id);});
