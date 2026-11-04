import {createNasSearchStatus} from '/assets/nas-search-status.js';
const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const relative=value=>typeof value==='string'&&value.length>0&&value.length<=1600&&!/^[\/]|[\\:\x00-\x1f]/.test(value)&&!value.split('/').some(x=>x==='..'||x==='');
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const keyFor=(tab,item)=>tab==='forms'?item.path:item.logical_root_id+'\n'+item.relative_path;

export async function mountDocumentMaterials(host,{api,isCurrent,initialScope={},onScope=()=>{},canReceive=false,receiveForm,onChoose}){
 host.dataset.documentMaterials='';const style=N('style');style.textContent='[data-document-materials] [hidden]{display:none!important}[data-document-materials] .policy-item{min-width:0;overflow-wrap:anywhere}[data-document-materials] .tools input{min-width:0;width:100%}';host.append(style);
 let alive=true,sequence=0,timer,controller=null,loading=false,choosing=false,items=[],page=null;
 const current=()=>alive&&host.isConnected&&isCurrent();
 let query=typeof initialScope.q==='string'?initialScope.q.slice(0,100):'',tab=initialScope.tab==='nas'?'nas':'forms',sort=['relevance','newest','name'].includes(initialScope.sort)?initialScope.sort:'relevance',selected=typeof initialScope.selected==='string'?initialScope.selected.slice(0,1800):'';
 let selectedPage=tab==='nas'&&selected&&integer(initialScope.page?.offset)&&initialScope.page.offset<=1000000&&hex(initialScope.page?.snapshot)?{offset:initialScope.page.offset,snapshot:initialScope.page.snapshot}:null,startOffset=0,restoreSelection=!!selected;
 const origins=new Map(),remember=()=>onScope({q:query,tab,sort,selected,page:selectedPage});
 const controls=N('div',null,'tools'),input=N('input'),tabs=N('div',null,'tools'),formsTab=N('button','등록 양식'),nasTab=N('button','NAS 자료'),order=N('select'),find=N('button','찾기'),note=N('p',null,'top-note'),list=N('div'),more=N('button','자료 더 보기');
 input.type='search';input.maxLength=100;input.value=query;input.placeholder='파일명 · 폴더명 검색';input.setAttribute('aria-label','자료 검색');input.style.background='#fff';input.style.color='#203744';input.style.border='2px solid #bc965f';
 for(const[value,label]of[['relevance','관련도순'],['newest','최근 수정순'],['name','파일명순']])order.append(new Option(label,value));order.value=sort;order.setAttribute('aria-label','NAS 자료 정렬');
 const first=N('button','첫 자료부터 보기');first.type='button';first.hidden=true;
 for(const b of[formsTab,nasTab,find,more])b.type='button';tabs.setAttribute('aria-label','자료 위치');tabs.append(formsTab,nasTab);controls.append(input,order,find);note.setAttribute('role','status');note.setAttribute('aria-live','polite');more.hidden=true;host.append(tabs,controls,note,first,list,more);
 let availability=null;
 try{availability=canReceive?await api('/work-requests/availability'):null;}catch{}
 if(!current())return()=>{alive=false;};
 const nasEnabled=canReceive&&availability?.enabled===true&&availability.nas_files===true,formsChat=canReceive&&availability?.enabled===true&&availability.registered_forms===true;
 const status=nasEnabled?createNasSearchStatus({api,isCurrent:current}):null;
 if(status)controls.after(status.element);
 if(tab==='nas'&&!nasEnabled)tab='forms';nasTab.hidden=!nasEnabled;
 function state(){formsTab.setAttribute('aria-pressed',String(tab==='forms'));nasTab.setAttribute('aria-pressed',String(tab==='nas'));order.hidden=tab!=='nas';if(status)status.element.hidden=tab!=='nas';remember();}
 function invalidate(){clearTimeout(timer);++sequence;controller?.abort();controller=null;loading=false;more.hidden=true;first.hidden=true;items=[];page=null;origins.clear();list.replaceChildren();list.setAttribute('aria-busy','false');}
 function resetReturn(){selectedPage=null;startOffset=0;selected='';restoreSelection=false;remember();}
 function message(text,error=false){note.textContent=text;note.classList.toggle('error',error);}
 function validNas(item){return item?.scope==='TEAM_SAFETY_NAS'&&item.logical_root_id==='team-safety-nas-z4'&&relative(item.relative_path)&&typeof item.file_name==='string'&&item.file_name.length>0&&item.file_name.length<=255&&!/[\/\\\x00-\x1f]/.test(item.file_name)&&hex(item.nas_file_id)&&integer(item.size)&&item.size>0&&item.size<=32*1024*1024&&item.is_directory===false;}
 async function choose(item,kind,button){
  if(!current()||loading||choosing)return;const epoch=sequence,sourceTab=tab;choosing=true;button.disabled=true;
  try{
   let source=item;
   if(sourceTab==='forms'){
    source=await api('/work-requests/form-selections',{method:'POST',body:JSON.stringify({relative_path:item.path})});if(!current()||epoch!==sequence)return;
    if(source.scope!=='BESMA_REGISTERED_FORM'||source.relative_path!==item.path||source.file_name!==item.name||!hex(source.form_file_id)||!hex(source.approved_content_sha256)||!integer(source.size)||source.size<1||source.size>32*1024*1024)throw Error('선택한 양식의 원본을 확인하지 못했습니다.');
   }else if(!validNas(source))throw Error('자료를 다시 찾아 선택해 주세요.');
   if(!current()||epoch!==sequence)return;selected=keyFor(sourceTab,item);selectedPage=sourceTab==='nas'?origins.get(selected)||null:null;remember();await onChoose(source,kind);
  }catch(e){if(current()&&epoch===sequence)message(e.message,true);}finally{choosing=false;button.disabled=false;}
 }
 function action(label,fn){const b=N('button',label);b.type='button';b.onclick=()=>Promise.resolve().then(()=>fn(b)).catch(e=>{if(current())message(e.message,true);});return b;}
 function draw(){
  list.replaceChildren();
  for(const item of items){
   const key=keyFor(tab,item),row=N('article',null,'policy-item'+(key===selected?' selected':'')),name=tab==='forms'?item.name:item.file_name,source=tab==='forms'?item.path:item.relative_path;
   row.dataset.materialKey=key;row.append(N('strong',name));const origin=N('details'),summary=N('summary','출처 보기');summary.style.minHeight='44px';origin.append(summary,N('p',(tab==='forms'?'BESMA 등록 양식 · ':'안전보건실 NAS · ')+source,'small muted'));row.append(origin);
   if(tab==='nas'){
    const date=Date.parse(item.modified_at);row.append(N('p',(integer(item.size)?(item.size/1024).toLocaleString('ko-KR',{maximumFractionDigits:1})+'KB':'크기 확인 필요')+' · '+(Number.isFinite(date)?new Date(date).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}):'수정시각 확인 필요'),'small muted'));
    row.append(action('파일 받기',b=>choose(item,'NAS',b)),action('내용 질문',b=>choose(item,'SOURCE_QUESTION',b)));
   }else if(canReceive){
    row.append(action('받기',async b=>{if(!current()||loading||choosing)return;selected=key;remember();for(const old of list.children)old.classList.toggle('selected',old===row);await receiveForm(item,b);}));
    if(formsChat){const b=action('채팅에서 사용',b=>choose(item,'SOURCE_QUESTION',b));b.disabled=integer(item.size_bytes)&&(item.size_bytes===0||item.size_bytes>32*1024*1024);if(b.disabled)b.title=item.size_bytes===0?'내용이 없는 파일입니다.':'채팅에서는32MB 이하 파일을 사용할 수 있습니다.';row.append(b);}
   }
   list.append(row);
  }
  if(restoreSelection){const row=[...list.children].find(x=>x.dataset.materialKey===selected);if(row){restoreSelection=false;row.tabIndex=-1;row.focus({preventScroll:true});row.scrollIntoView({block:'center',behavior:'instant'});}}
 }
 async function load(append=false){
  if(!current()||loading||choosing)return;if(append&&(!page||!integer(page.next_offset)||page.next_offset<1))return;
  if(!append){invalidate();if(tab==='nas'&&!query.trim()&&sort!=='newest'){message('파일명·폴더명을 입력하거나 최근 수정순을 선택해 주세요.');return;}}
  const epoch=++sequence,sourceTab=tab,queryAtStart=query,orderAtStart=sort;let indexCheck=null,refreshed=false,offset=append?page.next_offset:sourceTab==='nas'&&selectedPage?selectedPage.offset:0,request={q:queryAtStart.trim(),sort:orderAtStart,offset,...(append?{snapshot:page.snapshot}:sourceTab==='nas'&&selectedPage?{snapshot:selectedPage.snapshot}:{})};
  loading=true;controller=new AbortController();const active=controller;list.setAttribute('aria-busy','true');more.disabled=true;message('자료를 찾고 있습니다.');
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
   if(!current()||epoch!==sequence)return;
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
   draw();if(!items.length)list.append(N('p',sourceTab==='forms'?'검색 결과가 없습니다.':page.next_offset!==null?'현재 범위에 선택할 자료가 없습니다. 자료 더 보기로 확인해 주세요.':page.unavailable_count?'자료는 검색됐지만32MB를 넘어 채팅으로 받을 수 없습니다. NAS 원본은 그대로 보관되어 있습니다.':status.emptyMessage('조건에 맞는 자료를 찾지 못했습니다.'),'empty'));
  }catch(e){if(sourceTab==='nas'&&indexCheck)await indexCheck;if(current()&&epoch===sequence){items=[];page=null;more.hidden=true;first.hidden=true;if(e.status===409)resetReturn();list.replaceChildren(action('다시 찾기',()=>load()));message(e.name==='AbortError'?'자료 조회를 중단했습니다. 다시 찾아 주세요.':sourceTab==='nas'&&status.getState().phase==='missing'?status.emptyMessage(''):e.status===429?'검색 요청이 많습니다. 잠시 후 다시 찾아 주세요.':e.status===409?'검색 자료가 갱신됐습니다. 처음부터 다시 찾아 주세요.':e.message,true);}}
  finally{if(controller===active)controller=null;if(current()&&epoch===sequence){loading=false;list.setAttribute('aria-busy','false');more.disabled=false;}}
 }
 function switchTab(next){if(choosing||next===tab||next==='nas'&&!nasEnabled)return;invalidate();tab=next;resetReturn();state();void load();}
 formsTab.onclick=()=>switchTab('forms');nasTab.onclick=()=>switchTab('nas');find.onclick=first.onclick=()=>{if(loading||choosing)return;resetReturn();void load();};more.onclick=()=>void load(true);
 input.oninput=()=>{if(!current()||choosing)return;invalidate();query=input.value.slice(0,100);resetReturn();message('자료를 찾고 있습니다.');timer=setTimeout(()=>void load(),180);};
 input.onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();clearTimeout(timer);void load();}};
 order.onchange=()=>{if(choosing)return;invalidate();sort=order.value;resetReturn();void load();};
 state();await load();return()=>{alive=false;invalidate();status?.dispose();};
}
