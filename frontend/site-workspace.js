import {createSiteCorrectionEditor} from '/assets/site-corrections.js';
const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const A=(text,href)=>{const e=N('a',text,'button');e.href=href;return e;};
const B=(text,fn)=>{const e=N('button',text);e.type='button';e.onclick=fn;return e;};

export function mountSiteWorkspace({context,api,host,menus,isCurrent,onEnter,renderDuties,renderRisks,renderForms,renderPolicies}){
 let alive=true,epoch=0,siteCard=null;const token=localStorage.getItem('besma_token'),urls=[];const current=()=>alive&&isCurrent()&&localStorage.getItem('besma_token')===token;
 const entries=context.menus.filter(m=>[1,2,3,4,5,6,7,8,9,14].includes(m.id)).map(m=>m.key==='sites'?{...m,title:'현장 정보'}:m);
 document.querySelector('.nav-caption').textContent='WORKSPACE / 현장';menus.replaceChildren();for(const m of entries){const a=A('','#'+m.key);a.className='';a.append(N('b',String(m.id).padStart(2,'0')),N('span',m.title));menus.append(a);}
 function release(){for(const u of urls)URL.revokeObjectURL(u);urls.length=0;}
 function guardSiteNavigation(event){const link=event.target?.closest?.('a[href]');if(!link||link.getAttribute('href')==='#sites'||/^tel:/i.test(link.getAttribute('href'))||link.hasAttribute('download'))return;if(current()&&siteCard?.page.isConnected&&siteCard.page.querySelector('[data-dirty="true"],[data-busy="true"]')){event.preventDefault();event.stopPropagation();siteCard.notice.textContent='입력한 내용을 저장하거나 취소한 뒤 이동해 주세요.';}}
 document.addEventListener('click',guardSiteNavigation,true);
 async function siteInformation(page){
  if(siteCard){page.replaceWith(siteCard.page);if(!siteCard.ready)await siteCard.load();return;}
  const summary=N('dl',null,'site-info-summary'),slot=N('div'),notice=N('p',null,'site-info-notice'),refresh=B('새로고침',()=>load()),search=A('현장 정보 검색','/site/mobile/site-search');search.classList.add('site-info-search');notice.setAttribute('role','status');const actions=N('div',null,'site-info-secondary-actions');actions.append(refresh,search);page.append(summary,slot,notice,actions);
  const card={page,notice,ready:false,load:null};siteCard=card;let generation=0;
  const valid=()=>current()&&siteCard===card&&page.isConnected;
  const editing=()=>!!slot.querySelector('[data-dirty="true"],[data-busy="true"]');
  async function requestFor(site,path,options={}){
   const base='/workspace/site-corrections/'+encodeURIComponent(site.code),method=options.method||'GET';
   if(!valid()||!(path===base||path.startsWith(base+'/receipts/')&&/^[0-9a-f]{32}$/.test(path.slice((base+'/receipts/').length)))||!['GET','PUT'].includes(method))throw Error('현장 정보 연결을 다시 확인해 주세요.');
   const response=await fetch('https://api.besma.co.kr'+path,{method,body:options.body,signal:options.signal,credentials:'omit',redirect:'error',cache:'no-store',headers:{Authorization:'Bearer '+token,...(options.body?{'Content-Type':'application/json'}:{})}});
   if(!valid())throw new DOMException('화면이 바뀌었습니다.','AbortError');
   if(!response.ok){const messages={401:'로그인 상태를 확인해 주세요. 입력한 내용은 그대로 있습니다.',403:'현장 정보 수정 권한을 확인해 주세요. 입력한 내용은 그대로 있습니다.',404:'현장 정보 수정 연결을 확인해 주세요.',409:'다른 수정이나 원본 변경이 있습니다. 입력한 내용은 그대로 있습니다.',422:'주소·연락처와 직급을 확인해 주세요.'};throw Object.assign(Error(messages[response.status]||'현장 정보를 확인하지 못했습니다. 다시 시도해 주세요.'),{status:response.status});}
   return response.json();
  }
  async function load(message=''){
   if(!valid())return;if(editing()){notice.textContent='입력한 내용을 저장하거나 취소한 뒤 새로고침해 주세요.';return;}
   const id=++generation;refresh.disabled=true;notice.textContent='현장 정보를 확인하고 있습니다.';
   try{const site=await api('/workspace/site/current-site');if(!valid()||id!==generation)return;
    const unavailable=site.correction_status==='UNAVAILABLE';summary.replaceChildren();for(const [label,value]of [['현장',site.name],['주소',site.address],['현장 설명',site.description],['발주처',site.client],['시공사',site.contractor]])summary.append(N('dt',label),N('dd',unavailable&&['주소','현장 설명'].includes(label)?'정보 확인 중':value||'미등록'));
    const contacts=N('dd');summary.append(N('dt','담당자'),contacts);
    if(unavailable||site.contacts===null||site.directory_state==='UNAVAILABLE')contacts.append(N('p','담당자 정보를 확인하지 못했습니다.'));
    else if(!site.contacts?.length)contacts.append(N('p','등록된 담당자가 없습니다.'));
    else for(const contact of site.contacts){const line=N('p'),label=[contact.name,contact.rank?contact.rank+(contact.role&&contact.rank!==contact.role?'('+contact.role+')':''):contact.role].filter(Boolean).join(' ');line.append(N('span',label+' '));const phone=String(contact.phone||'');if(phone){const link=A(phone,'tel:'+phone.replace(/[^+0-9]/g,''));link.className='';line.append(link);}else line.append(N('span','전화번호 미등록'));contacts.append(line);}
    const editor=createSiteCorrectionEditor({site,request:(path,options)=>requestFor(site,path,options),isCurrent:valid,canEdit:true,onNotice:text=>{if(valid())notice.textContent=text;},onSaved:()=>load('현장 정보를 저장했습니다.'),fallback:()=>N('p','현장 정보 수정을 준비하고 있습니다.')});slot.replaceChildren();if(editor)slot.append(editor);card.ready=true;notice.textContent=message||(site.directory_state==='UNAVAILABLE'?'현장 연결을 확인하고 있습니다. 기존 기본정보만 표시합니다.':'');
   }finally{if(valid()&&id===generation)refresh.disabled=false;}
  }
  card.load=load;await load();
 }
 async function render(){let key=location.hash.slice(1).split(/[/?]/)[0]||'functional';if(key!=='sites'&&siteCard?.page.isConnected&&siteCard.page.querySelector('[data-dirty="true"],[data-busy="true"]')){history.replaceState(null,'','#sites');siteCard.notice.textContent='입력한 내용을 저장하거나 취소한 뒤 이동해 주세요.';return;}const seq=++epoch;onEnter();release();const entry=entries.find(m=>m.key===key);host.replaceChildren();document.body.classList.remove('drawer');document.body.dataset.section=entry?key:'site';document.getElementById('mobile-menu')?.setAttribute('aria-expanded','false');for(const a of menus.querySelectorAll('a'))a.setAttribute('aria-current',a.hash==='#'+key?'page':'false');const header=N('header',null,'heading'),title=N('div');title.append(N('p',context.site.name,'eyebrow'),N('h1',entry?.title||'현장 업무'));header.append(title);host.append(header);const page=N('section',null,'site-workspace');host.append(page);const valid=()=>current()&&seq===epoch&&page.isConnected;
  try{if(!entry){page.append(N('p','현장 메뉴에서 이용할 업무를 선택해 주세요.'));return;}
   if(key==='duties'){await renderDuties(page);return;}
   if(key==='risks'){await renderRisks(page);return;}
   if(key==='forms'){await renderForms(page);if(valid())page.append(A('열람 가능한 문서 열기','/site/document-explorer'));return;}
   if(key==='contractors'){await renderPolicies(page);return;}
   if(key==='functional'){page.append(N('p','로그인한 현장의 근로자를 평가하고 기존 평가·서명 이력을 확인합니다.'),A('내 현장 평가 열기',context.functional_eval_path));return;}
   if(key==='sites'){await siteInformation(page);return;}
   if(key==='government'){
    if(context.government_document_collection){page.append(N('p','이 현장의 문서를 제출하고 기존 검토 결과와 회신을 확인합니다.'),A('문서 넣기·제출 현황','/site/documents'),A('위험성평가 DB','#risks'),A('현장·본사 소통','/site/government-contact'));return;}
    page.append(N('p','업무 의견이나 홈페이지 개선사항을 남겨 주세요.'));const form=N('form'),category=N('select'),body=N('textarea'),label=N('label','의견 내용'),status=N('p'),send=N('button','의견 보내기');category.setAttribute('aria-label','의견 종류');for(const value of ['업무 개선','홈페이지 개선']){const o=N('option',value);o.value=value;category.append(o);}body.rows=4;body.required=true;body.maxLength=5000;body.setAttribute('aria-label','의견 내용');label.append(body);send.type='submit';status.setAttribute('role','status');form.append(category,label,send,status);page.append(form);const list=N('div');page.append(list);
    async function load(){const result=await api('/workspace/site/opinions');if(!valid())return;list.replaceChildren(N('h2','이 현장의 의견'));for(const row of result.items){const item=N('article');item.append(N('strong',row.category),N('p',row.content),N('small',opinionTime(row.created_at)));list.append(item);}if(!result.items.length)list.append(N('p','등록된 의견이 없습니다.'));}
    form.onsubmit=async e=>{e.preventDefault();if(!body.value.trim())return;send.disabled=true;try{await api('/workspace/site/opinions',{method:'POST',body:JSON.stringify({category:category.value,content:body.value.trim()})});if(!valid())return;body.value='';body.blur();status.textContent='의견을 등록했습니다.';await load();}catch(e){if(valid())status.textContent=e.message;}finally{if(valid())send.disabled=false;}};await load();return;
   }
   if(key==='voice'){const note=N('p','저장된 근로자 의견을 확인합니다. 최근 수신 시각은 확인되지 않았습니다.'),list=N('div',null,'site-opinions');page.append(note,B('새로고침',load),list);async function load(){try{const data=await api('/worker-feedback/desktop-responses?'+new URLSearchParams({site_code:context.site.code,limit:'100'}));if(!valid())return;if(data.schema!=='besma.google-feedback.desktop.v1'||data.sites.some(s=>s.site_code!==context.site.code))throw Error('현장 범위를 확인하지 못했습니다.');list.replaceChildren();const table=N('table'),head=N('tr');for(const t of ['접수일','이름','의견','처리 상태'])head.append(N('th',t));table.append(head);for(const r of data.items){const row=N('tr');for(const t of [String(r.submitted_at||'접수일 확인 필요').replace('T',' ').slice(0,16),r.worker_name,r.content,({PENDING:'접수 확인 전',RECEIVED:'조치 중',DONE:'조치 기록'})[r.action_status]||'확인 필요'])row.append(N('td',t));table.append(row);}list.append(table);if(!data.items.length)list.append(N('p','저장 원장에 이 현장의 의견이 없습니다.'));if(data.has_more)list.append(A('전체 접수·조치 기록',context.opinion_path));}catch(e){if(valid())list.replaceChildren(N('p','의견을 확인하지 못했습니다. '+e.message,'error'));}}await load();return;}
   if(key==='guide'){for(const m of entries.filter(m=>m.id<10)){const item=N('article');item.append(N('h2',m.id+'. '+m.title),A(m.title+' 열기','#'+m.key));page.append(item);}return;}
   if(key==='settings'){page.append(N('p',context.user.name+' · '+context.site.name),N('p','근로자 의견은 9번 메뉴에서 접수·조치 현황을 확인합니다.'),A('근로자의견청취 보기','#voice'));return;}
  }catch(error){if(valid())page.append(N('p',error.message,'error'));}
 }
 return {render,dispose(){alive=false;++epoch;document.removeEventListener('click',guardSiteNavigation,true);siteCard=null;release();}};
}

function opinionTime(value){
 if(typeof value!=='string'||!value)return '작성 시각 확인 필요';
 // The existing opinion model writes utc_now; its SQLite API values may omit the suffix.
 const text=value.replace(' ','T'),date=new Date(/[zZ]$|[+-]\d{2}:?\d{2}$/.test(text)?text:text+'Z');
 return Number.isFinite(date.valueOf())?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date):'작성 시각 확인 필요';
}
