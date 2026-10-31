import {inspectionEntry,inspectionMonth,inspectionPlanId} from '/assets/inspection-work-entry.js';
import {workReturn} from '/assets/workspace-return.js';
import {mountHalfYearReview} from '/half-year-editor.js?v=20261031.11';


import {mountInspectionReport} from '/inspection-report-editor.js?v=20261030.1';


let publications=null;


const API='https://api.besma.co.kr', BASE='/safety-features/team-schedule';


const $=id=>document.getElementById(id);


const sessionToken=localStorage.getItem('besma_token');


let user=null,capabilities=null,items=[],selected=null,saving=false,loadGeneration=0,tripGeneration=0,baseline='',reportEditor=null;


const workEntry=inspectionEntry(location.search);let entryOpened=false,viewOwner='',selectedPlan='' ;const VIEW_KEY='besma-inspection-plan-view-v1';
function saveView(plan){if(inspectionPlanId(plan))selectedPlan=plan;if(!viewOwner||localStorage.getItem('besma_token')!==sessionToken)return;try{sessionStorage.setItem(VIEW_KEY,JSON.stringify({owner:viewOwner,at:Date.now(),month:$('month').value,scope:$('scope').value,search:$('search').value.slice(0,100),plan:selectedPlan||null,scroll:scrollY}));}catch{}}
async function restoreView(){const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(sessionToken));viewOwner=[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');session();if(workEntry.requested){if(workEntry.valid){$('month').value=workEntry.month;$('scope').value='mine';}return;}try{const old=JSON.parse(sessionStorage.getItem(VIEW_KEY)||'null');if(old?.owner!==viewOwner||Date.now()-old.at<0||Date.now()-old.at>14400000)return;if(inspectionMonth(old.month))$('month').value=old.month;if(['mine','all'].includes(old.scope))$('scope').value=old.scope;if(typeof old.search==='string')$('search').value=old.search.slice(0,100);if(inspectionPlanId(old.plan))selectedPlan=old.plan;}catch{}}
async function openEntry(){if(entryOpened||!workEntry.requested)return;entryOpened=true;if(!workEntry.valid){$('notice').textContent='점검계획의 현장·기간 조건을 확인해 주세요.';return;}const row=items.find(r=>r.public_id===workEntry.plan);if(!row||row.owner_user_id!==user.id||!reportEditor?.enabled){$('notice').textContent='이 기간의 본인 점검계획을 확인해 주세요.';return;}saveView(row.public_id);await reportEditor.open(row);}
const returnLink=document.querySelector('header a');if(workEntry.requested&&workEntry.valid){returnLink.href=workReturn(workEntry.back);returnLink.textContent='‹ 이전 업무로';}returnLink.addEventListener('click',()=>saveView());addEventListener('pagehide',()=>saveView());
const mobile=/Android|iPhone|iPad|iPod|Windows Phone|Mobile/i.test(navigator.userAgent)||(/Macintosh/i.test(navigator.userAgent)&&navigator.maxTouchPoints>1);


const labels={PLANNED:'예정',IN_PROGRESS:'진행',ON_HOLD:'보류',COMPLETED:'완료'};


function clear(message){reportEditor?.dispose();reportEditor=null;items=[];selected=null;user=null;capabilities=null;++loadGeneration;++tripGeneration;$('rows').replaceChildren();$('workspace').hidden=true;$('editor').close();$('trip').close();$('trip-text').value='';$('detail').value='';$('notice').textContent=message;}


function session(){if(!sessionToken||localStorage.getItem('besma_token')!==sessionToken){clear('BESMA에 로그인한 뒤 점검계획을 다시 열어 주세요.');throw Error('로그인을 확인해 주세요.');}}


function message(code,status){return ({INSPECTION_PLAN_PERIOD_REQUIRED:'이번 점검계획은 11월 2일부터 30일 사이로 정해 주세요.',INSPECTION_PLAN_NOT_FOUND_IN_RANGE:'이 기간에 예정된 본인 점검계획이 없습니다.',INSPECTION_TRIP_RANGE_SPLITS_VISIT:'여러 날 진행하는 점검의 시작일부터 종료일까지 선택해 주세요.',INSPECTION_TRIP_DATE_RANGE_INVALID:'출장 시작일과 종료일을 확인해 주세요. 최대 31일을 선택할 수 있습니다.',TEAM_ASSIGNMENT_COMPLETION_IMMUTABLE:'완료된 점검은 예정 상태로 되돌릴 수 없습니다.',TEAM_SCHEDULE_REVISION_CONFLICT:'다른 곳에서 일정이 수정되었습니다. 입력 내용을 보존했으니 새로고침 후 확인해 주세요.'})[code]||(status===403?'팀 일정 이용 권한을 확인해 주세요.':status===401?'로그인이 만료되었습니다. BESMA에서 다시 로그인해 주세요.':'처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');}


async function api(path,options={}){session();const response=await fetch(API+path,{...options,cache:'no-store',headers:{Authorization:'Bearer '+sessionToken,...(options.body?{'Content-Type':'application/json','X-BESMA-Client-Surface':'PC_WEB'}:{})}});session();const value=await response.json().catch(()=>({}));session();if(!response.ok){const error=Error(message(value.detail,response.status));if(response.status===401||response.status===403)clear(error.message);throw error;}return value;}


function el(tag,text){const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;}


function button(text,action){const n=el('button',text);n.type='button';n.className='secondary';n.onclick=()=>action();return n;}


function canEdit(row){return capabilities?.can_write&&row.can_edit&&row.owner_user_id===user?.id;}


function render(){session();const query=$('search').value.trim().toLowerCase();const visible=items.filter(r=>(r.title+' '+r.owner_name+' '+(r.detail_text||'')).toLowerCase().includes(query));$('rows').replaceChildren();for(const row of visible){const tr=el('tr');tr.dataset.publicId=row.public_id;if(row.public_id===selectedPlan){tr.setAttribute('aria-current','true');tr.style.boxShadow='inset 3px 0 #b27d31';}tr.append(el('td',row.scheduled_date.slice(5)+(row.due_date?' ~ '+row.due_date.slice(5):'')),el('td',row.owner_name||row.assigned_user_name||''));const site=el('td');site.append(el('strong',row.title.replace(/^\[점검\] /,'')));const detail=el('div',row.detail_text||'');detail.className='detail';site.append(detail);tr.append(site,el('td',labels[row.status]||row.status));const actions=el('td');if(reportEditor?.enabled&&row.owner_user_id===user?.id)actions.append(button(reportEditor.mode==='half-year'?'반기평가':'사진·평가표',()=>{saveView(row.public_id);return reportEditor.open(row);}));const published=publications?.get(row.public_id);site.append(el('small',publications===null?'현장 반영 확인 중':!published?'미확정':published.draft_changed?'수정내용 미반영 · 다시 확정 필요':'확정 · 현장 반영'));if(canEdit(row)){actions.append(button('수정',()=>edit(row)));if(['PLANNED','IN_PROGRESS'].includes(row.status)){const confirmButton=button(published&&!published.draft_changed?'확정됨':'확정',()=>confirmPlan(row));confirmButton.disabled=!!published&&!published.draft_changed;actions.append(confirmButton);}}if(row.owner_user_id===user?.id)actions.append(button('출장신청 내용',()=>trip(row)));tr.append(actions);$('rows').append(tr);}$('empty').hidden=visible.length>0;$('summary').textContent=`점검 ${items.length}건 · 표시 ${visible.length}건`;$('read-only').hidden=!!capabilities?.can_write;}


async function reload(){const generation=++loadGeneration;$('notice').textContent='';try{const month=$('month').value;if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))throw Error('조회 월을 선택해 주세요.');const [y,m]=month.split('-').map(Number),last=new Date(y,m,0).getDate();const params=new URLSearchParams({from_date:month+'-01',to_date:month+'-'+String(last).padStart(2,'0'),inspection_only:'true',mine_only:String($('scope').value==='mine')});const response=await api(BASE+'/items?'+params);try{const value=await api('/workspace/inspection-publications');publications=new Map(value.items.map(r=>[r.public_id,r]));}catch{publications=null;}if(generation!==loadGeneration)return;items=response.items||[];render();saveView();await openEntry();}catch(error){if(generation===loadGeneration)$('notice').textContent=error.message;}}


function signature(){return JSON.stringify(['start','end','title','detail','status'].map(id=>$(id).value));}


function closeEditor(){if(saving)return;if(signature()!==baseline&&!confirm('저장하지 않은 변경 내용을 버릴까요?'))return;$('editor').close();}


function edit(row){if(!canEdit(row))return;selected=row;$('edit-owner').textContent='점검 담당: '+row.owner_name;$('title').value=row.title;$('start').value=row.scheduled_date;$('end').value=row.due_date||'';$('detail').value=row.detail_text||'';$('status').value=row.status;$('edit-notice').textContent='';for(const id of ['start','end']){const bounded=row.client_item_key?.startsWith('inspection:202611:');$(id).min=bounded?'2026-11-02':'';$(id).max=bounded?'2026-11-30':'';}baseline=signature();$('editor').showModal();}


$('edit-form').onsubmit=async event=>{event.preventDefault();if(saving||!selected||!canEdit(selected))return;saving=true;$('save').disabled=true;$('edit-notice').textContent='';try{const saved=await api(BASE+'/items/'+encodeURIComponent(selected.public_id),{method:'PUT',body:JSON.stringify({revision:selected.revision,scheduled_date:$('start').value,due_date:$('end').value||null,title:$('title').value,detail_text:$('detail').value||null,status:$('status').value,assigned_user_id:selected.assigned_user_id})});items=items.map(r=>r.public_id===saved.public_id?saved:r);$('editor').close();$('notice').textContent='점검계획을 저장했습니다.';await reload();}catch(error){$('edit-notice').textContent=error.message;}finally{saving=false;$('save').disabled=false;}};


function trip(row){++tripGeneration;$('trip-start').value=row.scheduled_date;$('trip-end').value=row.due_date||row.scheduled_date;clearTrip();$('trip').showModal();}


function clearTrip(){++tripGeneration;$('trip-text').value='';$('trip-copy').disabled=true;$('trip-notice').textContent='';}


$('trip-load').onclick=async()=>{clearTrip();const generation=tripGeneration;$('trip-load').disabled=true;try{const value=await api(BASE+'/inspection-trip-draft?'+new URLSearchParams({from_date:$('trip-start').value,to_date:$('trip-end').value}));if(generation!==tripGeneration||!$('trip').open)return;$('trip-text').value=value.application_text;$('trip-copy').disabled=false;}catch(error){if(generation===tripGeneration)$('trip-notice').textContent=error.message;}finally{$('trip-load').disabled=false;}};


$('trip-copy').onclick=async()=>{try{session();await navigator.clipboard.writeText($('trip-text').value);$('trip-notice').textContent='출장신청 내용을 복사했습니다.';}catch{$('trip-notice').textContent='내용을 선택하여 복사해 주세요.';}};


for(const id of ['trip-start','trip-end'])$(id).onchange=clearTrip;


$('edit-close').onclick=closeEditor;$('editor').addEventListener('cancel',e=>{e.preventDefault();closeEditor();});$('trip-close').onclick=()=>{$('trip').close();clearTrip();};$('trip').addEventListener('close',clearTrip);


$('search').oninput=render;$('refresh').onclick=reload;$('month').onchange=reload;$('scope').onchange=reload;


window.addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null)clear('로그인이 변경되었습니다. 점검계획을 다시 열어 주세요.');});


window.addEventListener('beforeunload',event=>{if(saving||reportEditor?.hasUnsaved()||($('editor').open&&signature()!==baseline)){event.preventDefault();event.returnValue='';}});


async function start(){try{session();[user,capabilities]=await Promise.all([api('/auth/me'),api(BASE+'/capabilities?surface='+(mobile?'MOBILE_WEB':'PC_WEB'))]);if(!capabilities.can_read)throw Error('팀 일정 이용 권한을 확인해 주세요.');const halfYear=await mountHalfYearReview({origin:API,token:sessionToken,session,user,workspace:$('workspace'),panel:$('half-year-review-panel'),onReturn:()=>{render();requestAnimationFrame(()=>{const row=[...$('rows').children].find(r=>r.dataset.publicId===selectedPlan);row?.scrollIntoView({block:'center'});row?.querySelector('button')?.focus({preventScroll:true});});}});reportEditor=halfYear.enabled?halfYear:await mountInspectionReport({origin:API,token:sessionToken,session,user,workspace:$('workspace'),panel:$('inspection-report-panel')});if(reportEditor.enabled)$('read-only').textContent='일정 수정은 PC에서 해 주세요. 반기평가는 여기서 입력·저장할 수 있습니다.';$('identity').textContent=user.name+' · 현장소장과 협의하여 점검일정을 확정합니다.';$('workspace').hidden=false;await restoreView();await reload();}catch(error){clear(error.message);$('identity').textContent='';}}


void start();





async function confirmPlan(row){if(!canEdit(row)||saving)return;saving=true;try{await api('/workspace/inspection-publications/'+encodeURIComponent(row.public_id)+'/confirm',{method:'POST',body:JSON.stringify({revision:row.revision})});await reload();$('notice').textContent='확정하여 현장에 반영했습니다.';}catch(error){$('notice').textContent=error.message+' 새로고침하여 반영 여부를 확인해 주세요.';}finally{saving=false;}}


