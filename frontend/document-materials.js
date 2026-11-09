import {createNasSearchStatus} from '/assets/nas-search-status.js';
const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const relative=value=>typeof value==='string'&&value.length>0&&value.length<=1600&&!/^[\/]|[\\:\x00-\x1f]/.test(value)&&!value.split('/').some(x=>x==='..'||x==='');
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const keyFor=(tab,item)=>tab==='forms'?item.path:item.logical_root_id+'\n'+item.relative_path;

export async function mountDocumentMaterials(host,{api,isCurrent,initialScope={},onScope=()=>{},canReceive=false,receiveForm,onChoose}){
 host.dataset.documentMaterials='';const style=N('style');style.textContent='[data-document-materials] [hidden]{display:none!important}[data-document-materials] .policy-item{min-width:0;overflow-wrap:anywhere}[data-document-materials] .top-note.error{backdrop-filter:none;-webkit-backdrop-filter:none;color:#fff0d7;background:#573827;border:1px solid #d6a374;border-radius:7px;padding:10px 12px;font-size:14px;line-height:1.6}[data-document-materials] .tools input{min-width:0;width:100%}';host.append(style);
 let composing=false;
 let alive=true,sequence=0,timer,controller=null,selectionController=null,loading=false,choosing=false,items=[],page=null;
 const current=()=>alive&&host.isConnected&&isCurrent();
 let query=typeof initialScope.q==='string'?initialScope.q.slice(0,100):'',tab=initialScope.tab==='nas'?'nas':'forms',sort=['relevance','newest','name'].includes(initialScope.sort)?initialScope.sort:'relevance',selected=typeof initialScope.selected==='string'?initialScope.selected.slice(0,1800):'';
 let selectedPage=tab==='nas'&&selected&&integer(initialScope.page?.offset)&&initialScope.page.offset<=1000000&&hex(initialScope.page?.snapshot)?{offset:initialScope.page.offset,snapshot:initialScope.page.snapshot}:null,startOffset=0,restoreSelection=!!selected;
 function cleanTab(value,kind){
  value=value&&typeof value==='object'&&!Array.isArray(value)?value:{};
  const q=typeof value.q==='string'?value.q.slice(0,100):'',order=['relevance','newest','name'].includes(value.sort)?value.sort:'relevance',key=typeof value.selected==='string'?value.selected.slice(0,1800):'';
  const page=kind==='nas'&&key&&integer(value.page?.offset)&&value.page.offset<=1000000&&hex(value.page?.snapshot)?{offset:value.page.offset,snapshot:value.page.snapshot}:null;
  return{q,sort:order,selected:key,page};
 }
 const tabScopes={forms:cleanTab(initialScope.tabs?.forms,'forms'),nas:cleanTab(initialScope.tabs?.nas,'nas')};
 const saveTab=()=>{tabScopes[tab]=cleanTab({q:query,sort,selected,page:selectedPage},tab);};
 const origins=new Map(),remember=()=>{saveTab();onScope({q:query,tab,sort,selected,page:selectedPage,tabs:{forms:tabScopes.forms,nas:tabScopes.nas}});};
 const controls=N('div',null,'tools'),input=N('input'),tabs=N('div',null,'tools'),formsTab=N('button','등록 양식'),nasTab=N('button','NAS 자료'),order=N('select'),find=N('button','찾기'),note=N('p',null,'top-note'),list=N('div'),more=N('button','자료 더 보기');
 input.type='search';input.maxLength=100;input.value=query;input.placeholder='파일명 · 폴더명 검색';input.setAttribute('aria-label','자료 검색');input.style.background='#fff';input.style.color='#203744';input.style.border='2px solid #bc965f';
 for(const[value,label]of[['relevance','관련도순'],['newest','최근 수정순'],['name','파일명순']])order.append(new Option(label,value));order.value=sort;order.setAttribute('aria-label','NAS 자료 정렬');
 const first=N('button','첫 자료부터 보기');first.type='button';first.hidden=true;
 const stop=N('button','조회 중단');stop.type='button';stop.hidden=true;stop.onclick=()=>{(selectionController||controller)?.abort();};function busyState(){stop.hidden=!loading&&!choosing;stop.textContent=choosing?'선택 중단':'조회 중단';}
 for(const b of[formsTab,nasTab,find,more])b.type='button';tabs.setAttribute('aria-label','자료 위치');tabs.append(formsTab,nasTab);controls.append(input,order,find);note.setAttribute('role','status');note.setAttribute('aria-live','polite');more.hidden=true;host.append(tabs,controls,note,stop,first,list,more);
 let availabilityPhase=canReceive?'loading':'off',availabilityRequest=0,availabilityController=null,availabilityTimer=null,nasEnabled=false,formsChat=false,status=null,chatAdds=[];
 const capabilityNote=N('p',null,'top-note'),capabilityRetry=N('button','연결 다시 확인');capabilityNote.setAttribute('role','status');capabilityNote.setAttribute('aria-live','polite');capabilityRetry.type='button';capabilityRetry.hidden=true;capabilityRetry.onclick=()=>void checkAvailability();controls.after(capabilityNote,capabilityRetry);
 if(!canReceive)tab='forms';
 function capabilityState(){
  nasTab.hidden=!canReceive||availabilityPhase==='ready'&&!nasEnabled&&tab!=='nas';nasTab.disabled=!nasEnabled;capabilityRetry.hidden=!canReceive||availabilityPhase==='loading'||availabilityPhase==='ready'&&nasEnabled&&formsChat;capabilityNote.hidden=!canReceive||availabilityPhase==='ready'&&nasEnabled&&formsChat;
  refreshActions();
  capabilityNote.textContent=availabilityPhase==='loading'?'채팅·NAS 연결 확인 중 · 등록 양식은 계속 이용할 수 있습니다.':availabilityPhase==='failed'?'채팅·NAS 연결을 확인하지 못했습니다. 등록 양식은 계속 이용할 수 있습니다.':!nasEnabled?'지금은 NAS 자료 연결을 사용할 수 없습니다.':'지금은 등록 양식의 채팅 연결을 사용할 수 없습니다.';
 }
 function refreshActions(){for(const button of list.querySelectorAll('[data-material-capability]'))button.disabled=choosing||button.dataset.materialUnusable==='true'||(button.dataset.materialCapability==='nas'?!nasEnabled:!formsChat);}
 async function checkAvailability(){
  if(!current()||!canReceive||availabilityController)return;const attempt=++availabilityRequest,active=new AbortController();availabilityController=active;availabilityPhase='loading';capabilityState();
  const wait=setTimeout(()=>active.abort(),15000);availabilityTimer=wait;
  try{
   const value=await api('/work-requests/availability',{signal:active.signal});if(!current()||attempt!==availabilityRequest)return;
   if(!value||typeof value.enabled!=='boolean'||value.enabled&&(typeof value.nas_files!=='boolean'||typeof value.registered_forms!=='boolean'))throw Error('자료 연결 확인 필요');
   availabilityPhase='ready';nasEnabled=value.enabled===true&&value.nas_files===true;formsChat=value.enabled===true&&value.registered_forms===true;
   if(nasEnabled&&!status){status=createNasSearchStatus({api,isCurrent:current});controls.after(status.element);}
   capabilityState();
   if(tab==='nas'&&!nasEnabled){state();message('지금은 NAS 자료 연결을 사용할 수 없습니다. 등록 양식은 해당 탭에서 확인할 수 있습니다.',true);}
   else{state();if(tab==='nas')void load();else if(formsChat)for(const add of chatAdds)add();}
  }catch{if(current()&&attempt===availabilityRequest){availabilityPhase='failed';capabilityState();if(tab==='nas')message('NAS 연결을 확인한 뒤 같은 조건으로 다시 찾을 수 있습니다.',true);}}
  finally{clearTimeout(wait);if(availabilityTimer===wait)availabilityTimer=null;if(availabilityController===active)availabilityController=null;}
 }
 function state(){formsTab.setAttribute('aria-pressed',String(tab==='forms'));nasTab.setAttribute('aria-pressed',String(tab==='nas'));order.hidden=tab!=='nas';if(status)status.element.hidden=tab!=='nas';remember();}
 function invalidate(){clearTimeout(timer);++sequence;controller?.abort();controller=null;loading=false;busyState();more.hidden=true;first.hidden=true;items=[];page=null;origins.clear();chatAdds=[];list.replaceChildren();list.setAttribute('aria-busy','false');}
 function resetReturn(){selectedPage=null;startOffset=0;selected='';restoreSelection=false;remember();}
 function message(text,error=false){note.textContent=text;note.classList.toggle('error',error);}
 function validNas(item){return item?.scope==='TEAM_SAFETY_NAS'&&item.logical_root_id==='team-safety-nas-z4'&&relative(item.relative_path)&&typeof item.file_name==='string'&&item.file_name.length>0&&item.file_name.length<=255&&!/[\/\\\x00-\x1f]/.test(item.file_name)&&hex(item.nas_file_id)&&integer(item.size)&&item.size>0&&item.size<=32*1024*1024&&item.is_directory===false;}
 async function choose(item,kind,button){
  if(!current()||loading||choosing||composing)return;if(tab==='nas'&&!nasEnabled||tab==='forms'&&!formsChat){message('자료 연결을 다시 확인해 주세요.',true);return;}const epoch=sequence,sourceTab=tab;choosing=true;button.disabled=true;const active=new AbortController();selectionController=active;let timedOut=false;const wait=setTimeout(()=>{timedOut=true;active.abort();},15000);busyState();
  try{
   let source=item;
   if(sourceTab==='forms'){
    source=await api('/work-requests/form-selections',{method:'POST',body:JSON.stringify({relative_path:item.path}),signal:active.signal});if(!current()||epoch!==sequence)return;if(active.signal.aborted)throw new DOMException('Selection stopped','AbortError');
    if(source.scope!=='BESMA_REGISTERED_FORM'||source.relative_path!==item.path||source.file_name!==item.name||!hex(source.form_file_id)||!hex(source.approved_content_sha256)||!integer(source.size)||source.size<1||source.size>32*1024*1024)throw Error('선택한 양식의 원본을 확인하지 못했습니다.');
   }else if(!validNas(source))throw Error('자료를 다시 찾아 선택해 주세요.');
   if(!current()||epoch!==sequence)return;if(active.signal.aborted)throw new DOMException('Selection stopped','AbortError');clearTimeout(wait);selected=keyFor(sourceTab,item);selectedPage=sourceTab==='nas'?origins.get(selected)||null:null;remember();await onChoose(source,kind);
  }catch(e){if(current()&&epoch===sequence)message(timedOut?'자료 선택 확인에 시간이 걸려 중단했습니다. 같은 자료를 다시 선택해 주세요.':e.name==='AbortError'?'자료 선택 확인을 중단했습니다.':e.message,true);}finally{clearTimeout(wait);if(selectionController===active)selectionController=null;choosing=false;button.disabled=false;busyState();refreshActions();}
 }
 function action(label,fn){const b=N('button',label);b.type='button';b.onclick=()=>Promise.resolve().then(()=>fn(b)).catch(e=>{if(current())message(e.message,true);});return b;}
 function draw(append=false){
  if(!append)list.replaceChildren();
  const existing=append?new Set([...list.children].map(row=>row.dataset.materialKey)):null;
  for(const item of items){
   if(existing?.has(keyFor(tab,item)))continue;
   const key=keyFor(tab,item),row=N('article',null,'policy-item'+(key===selected?' selected':'')),name=tab==='forms'?item.name:item.file_name,source=tab==='forms'?item.path:item.relative_path;
   row.dataset.materialKey=key;row.append(N('strong',name));const origin=N('details'),summary=N('summary','출처 보기');summary.style.minHeight='44px';origin.append(summary,N('p',(tab==='forms'?'BESMA 등록 양식 · ':'안전보건실 NAS · ')+source,'small muted'));row.append(origin);
   if(tab==='nas'){
    const date=Date.parse(item.modified_at);row.append(N('p',(integer(item.size)?(item.size/1024).toLocaleString('ko-KR',{maximumFractionDigits:1})+'KB':'크기 확인 필요')+' · '+(Number.isFinite(date)?new Date(date).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}):'수정시각 확인 필요'),'small muted'));
    const receive=action('파일 받기',b=>choose(item,'NAS',b)),question=action('내용 질문',b=>choose(item,'SOURCE_QUESTION',b));for(const button of[receive,question]){button.dataset.materialCapability='nas';button.disabled=!nasEnabled;}row.append(receive,question);
   }else if(canReceive){
    row.append(action('받기',async b=>{if(!current()||loading||choosing)return;selected=key;remember();for(const old of list.children)old.classList.toggle('selected',old===row);await receiveForm(item,b);}));
    const add=()=>{if(!current()||row.dataset.formChat==='1')return;row.dataset.formChat='1';const b=action('채팅에서 사용',b=>choose(item,'SOURCE_QUESTION',b));b.dataset.materialCapability='forms';b.disabled=integer(item.size_bytes)&&(item.size_bytes===0||item.size_bytes>32*1024*1024);b.dataset.materialUnusable=String(b.disabled);if(b.disabled)b.title=item.size_bytes===0?'내용이 없는 파일입니다.':'채팅에서는32MB 이하 파일을 사용할 수 있습니다.';row.append(b);};chatAdds.push(add);if(formsChat)add();
   }
   list.append(row);
  }
  if(restoreSelection){const row=[...list.children].find(x=>x.dataset.materialKey===selected);if(row){restoreSelection=false;row.tabIndex=-1;row.focus({preventScroll:true});row.scrollIntoView({block:'center',behavior:'instant'});}}
 }
 async function load(append=false){
  if(!current()||loading||choosing||composing)return;if(tab==='nas'&&!nasEnabled){message(availabilityPhase==='loading'?'NAS 연결을 확인하고 있습니다.':'NAS 연결을 확인한 뒤 같은 조건으로 다시 찾을 수 있습니다.',availabilityPhase==='failed');return;}if(append&&(!page||!integer(page.next_offset)||page.next_offset<1))return;
  if(!append){invalidate();if(tab==='nas'&&!query.trim()&&sort!=='newest'){message('파일명·폴더명을 입력하거나 최근 수정순을 선택해 주세요.');return;}}
  const previousItems=append?items.slice():null,previousPage=append?page:null;
  const epoch=++sequence,sourceTab=tab,queryAtStart=query,orderAtStart=sort;let indexCheck=null,refreshed=false,offset=append?page.next_offset:sourceTab==='nas'&&selectedPage?selectedPage.offset:0,request={q:queryAtStart.trim(),sort:orderAtStart,offset,...(append?{snapshot:page.snapshot}:sourceTab==='nas'&&selectedPage?{snapshot:selectedPage.snapshot}:{})};
  loading=true;controller=new AbortController();const active=controller;let timedOut=false;const wait=setTimeout(()=>{timedOut=true;active.abort();},15000);busyState();list.setAttribute('aria-busy','true');more.disabled=true;message('자료를 찾고 있습니다.');
  try{
   let data;
   if(sourceTab==='forms')data=await api('/workspace/forms?q='+encodeURIComponent(queryAtStart),{signal:active.signal});
   else{
    indexCheck=status.refresh();
    try{data=await api('/work-requests/nas/search',{method:'POST',body:JSON.stringify(request),signal:active.signal});}
    catch(error){
     if(error.status!==409||!request.snapshot||active.signal.aborted||!current()||epoch!==sequence)throw error;
     append=false;offset=0;request={q:queryAtStart.trim(),sort:orderAtStart,offset:0};refreshed=true;
     selectedPage=null;startOffset=0;restoreSelection=!!selected;items=[];page=null;origins.clear();list.replaceChildren();more.hidden=true;first.hidden=true;remember();
     message('검색목록이 갱신되어 같은 조건으로 다시 찾고 있습니다.');
     data=await api('/work-requests/nas/search',{method:'POST',body:JSON.stringify(request),signal:active.signal});
    }
   }
   if(!current()||epoch!==sequence)return;if(active.signal.aborted)throw new DOMException('Query stopped','AbortError');
   if(!Array.isArray(data.items))throw Error('자료 목록을 확인하지 못했습니다. 다시 찾아 주세요.');
   if(sourceTab==='nas'&&!data.items.length){await indexCheck;if(!current()||epoch!==sequence)return;}
   if(sourceTab==='forms'){
    if(typeof data.source!=='string'||data.items.some(x=>!relative(x.path)||!x.path.startsWith('base/')||typeof x.name!=='string'||!x.name||x.name.length>255))throw Error('등록 양식의 출처를 확인하지 못했습니다.');
    items=data.items;message(items.length+'개 자료 · '+data.source);
   }else{
    if(data.items.length>20||data.items.some(x=>!validNas(x))||!integer(data.total_count)||!integer(data.scanned_count)||data.scanned_count>data.total_count||data.scanned_count<offset||!hex(data.snapshot)||data.sort!==orderAtStart||data.offset!==offset||typeof data.complete!=='boolean'||!integer(data.unavailable_count)||!integer(data.excluded_count)||data.next_offset!==null&&(!integer(data.next_offset)||data.next_offset<=offset||data.next_offset!==data.scanned_count||data.next_offset>=data.total_count)||data.complete!==(data.next_offset===null))throw Error('NAS 검색 범위를 확인하지 못했습니다. 처음부터 다시 찾아 주세요.');
    if(!append)startOffset=offset;
    const merged=new Map((append?items:[]).map(x=>[keyFor('nas',x),x]));for(const item of data.items){const key=keyFor('nas',item);merged.set(key,item);origins.set(key,{offset,snapshot:data.snapshot});}items=[...merged.values()];
    page={...data,unavailable_count:data.unavailable_count+(append?page.unavailable_count:0),excluded_count:data.excluded_count+(append?page.excluded_count:0)};
    message((refreshed?'검색목록이 갱신되어 같은 조건으로 다시 찾았습니다. ':'')+'검색 일치 '+data.total_count.toLocaleString()+'건 중 '+(startOffset?(startOffset+1).toLocaleString()+'–':'')+data.scanned_count.toLocaleString()+'건 확인 · 선택 가능 '+items.length+'개'+(page.unavailable_count?' · 32MB 초과 '+page.unavailable_count+'개':'')+(page.excluded_count?' · 이용 제한 '+page.excluded_count+'개':''));more.hidden=data.next_offset===null;first.hidden=startOffset===0;
   }
   if(sourceTab==='nas'&&restoreSelection&&selected&&!items.some(item=>keyFor('nas',item)===selected))note.textContent+=page.next_offset!==null?' · 이전 선택자료는 현재 범위에 없습니다. 자료 더 보기로 확인해 주세요.':' · 이전 선택자료를 새 목록에서 확인하지 못했습니다.';
   draw(append);if(!items.length)list.append(N('p',sourceTab==='forms'?'검색 결과가 없습니다.':page.next_offset!==null?'현재 범위에 선택할 자료가 없습니다. 자료 더 보기로 확인해 주세요.':page.unavailable_count?'자료는 검색됐지만32MB를 넘어 채팅으로 받을 수 없습니다. NAS 원본은 그대로 보관되어 있습니다.':page.excluded_count?'검색된 자료는 현재 계정에서 이용할 수 없습니다. 자료가 없다는 뜻은 아닙니다.':status.emptyMessage('조건에 맞는 자료를 찾지 못했습니다.'),'empty'));
  }catch(e){if(sourceTab==='nas'&&indexCheck&&!active.signal.aborted)await indexCheck;if(current()&&epoch===sequence){if(append&&previousItems?.length&&previousPage&&![401,403,404,409,410].includes(e.status)){items=previousItems;page=previousPage;more.hidden=false;message(e.name==='AbortError'?'추가 자료 조회를 중단했습니다. 앞서 확인한 자료는 유지됩니다.':'추가 자료를 불러오지 못했습니다. 앞서 확인한 자료는 유지됩니다. 자료 더 보기로 다시 확인해 주세요.',true);return;}items=[];page=null;more.hidden=true;first.hidden=true;if(e.status===409)resetReturn();list.replaceChildren(action('다시 찾기',()=>load()));message(timedOut?'자료 조회에 시간이 걸려 중단했습니다. 같은 조건으로 다시 찾아 주세요.':e.name==='AbortError'?'자료 조회를 중단했습니다. 다시 찾아 주세요.':sourceTab==='nas'&&status.getState().phase==='missing'?status.emptyMessage(''):e.status===429?'검색 요청이 많습니다. 잠시 후 다시 찾아 주세요.':e.status===409?'검색 자료가 갱신됐습니다. 처음부터 다시 찾아 주세요.':e.message,true);}}
  finally{clearTimeout(wait);if(controller===active)controller=null;if(current()&&epoch===sequence){loading=false;busyState();list.setAttribute('aria-busy','false');more.disabled=false;}}
 }
 function switchTab(next){if(choosing||composing||next===tab||next==='nas'&&!nasEnabled)return;saveTab();invalidate();tab=next;const saved=tabScopes[tab];query=saved.q;sort=saved.sort;selected=saved.selected;selectedPage=saved.page;startOffset=0;restoreSelection=!!selected;input.value=query;order.value=sort;state();void load();}
 formsTab.onclick=()=>switchTab('forms');nasTab.onclick=()=>switchTab('nas');find.onclick=first.onclick=()=>{if(loading||choosing||composing)return;resetReturn();void load();};more.onclick=()=>void load(true);
 function searchInput(event){if(!current()||choosing)return;if(composing||event?.isComposing){clearTimeout(timer);return;}invalidate();query=input.value.slice(0,100);resetReturn();message('자료를 찾고 있습니다.');timer=setTimeout(()=>void load(),180);}
 input.oncompositionstart=()=>{if(!current()||choosing)return;composing=true;invalidate();message('검색어를 입력하고 있습니다.');};
 input.oncompositionend=()=>{composing=false;searchInput();};
 input.oninput=searchInput;
 input.onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing&&!composing){e.preventDefault();clearTimeout(timer);void load();}};
 order.onchange=()=>{if(choosing)return;invalidate();sort=order.value;resetReturn();void load();};
 function cleanup(){if(!alive)return;alive=false;availabilityRequest++;availabilityController?.abort();selectionController?.abort();clearTimeout(availabilityTimer);invalidate();status?.dispose();removeEventListener('pagehide',cleanup);removeEventListener('storage',accountChanged);}
 function accountChanged(event){if(event.key==='besma_token'||event.key===null)cleanup();}
 addEventListener('pagehide',cleanup);addEventListener('storage',accountChanged);capabilityState();state();void load();if(canReceive)void checkAvailability();return cleanup;
}
