import {signingBundleButton} from '/signature-bundle.js?v=2026.11.06.11';
import {createReviewDashboard} from '/inspection-review-dashboard.js?v=2026.11.04.5';
import {inspectionEntry,inspectionMonth,inspectionPlanId} from '/assets/inspection-work-entry.js';
import {workReturn} from '/assets/workspace-return.js';
import {mountHalfYearReview} from '/half-year-editor.js?v=20261101.19';


import {mountInspectionReport} from '/inspection-report-editor.js?v=20261030.1';


let publications=null,reviewDashboard=null,mobilePilot=false;


const API='https://api.besma.co.kr', BASE='/safety-features/team-schedule';


const $=id=>document.getElementById(id);


const sessionToken=localStorage.getItem('besma_token');


let user=null,capabilities=null,items=[],selected=null,saving=false,loadGeneration=0,tripGeneration=0,baseline='',reportEditor=null;


const workEntry=inspectionEntry(location.search);let entryOpened=false,viewOwner='',selectedPlan='' ;const VIEW_KEY='besma-inspection-plan-view-v1';
function saveView(plan){if(inspectionPlanId(plan))selectedPlan=plan;if(!viewOwner||localStorage.getItem('besma_token')!==sessionToken)return;try{sessionStorage.setItem(VIEW_KEY,JSON.stringify({owner:viewOwner,at:Date.now(),month:$('month').value,scope:$('scope').value,search:$('search').value.slice(0,100),plan:selectedPlan||null,scroll:scrollY}));}catch{}}
async function restoreView(){const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(sessionToken));viewOwner=[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');session();if(workEntry.requested){if(workEntry.valid){$('month').value=workEntry.month;$('scope').value='mine';}return;}try{const old=JSON.parse(sessionStorage.getItem(VIEW_KEY)||'null');if(old?.owner!==viewOwner||Date.now()-old.at<0||Date.now()-old.at>14400000)return;if(inspectionMonth(old.month))$('month').value=old.month;if(['mine','all'].includes(old.scope))$('scope').value=old.scope;if(typeof old.search==='string')$('search').value=old.search.slice(0,100);if(inspectionPlanId(old.plan))selectedPlan=old.plan;}catch{}}
async function openEntry(){if(entryOpened||!workEntry.requested)return;entryOpened=true;if(!workEntry.valid){$('notice').textContent='점검계획의 현장·기간 조건을 확인해 주세요.';return;}let row=items.find(r=>r.public_id===workEntry.plan);if(!row||row.owner_user_id!==user.id||!reportEditor?.enabled){$('notice').textContent='이 기간의 본인 점검계획을 확인해 주세요.';return;}saveView(row.public_id);await reportEditor.open(row);}
const returnLink=document.querySelector('header a');if(workEntry.requested&&workEntry.valid){returnLink.href=workReturn(workEntry.back);returnLink.textContent='‹ 이전 업무로';}returnLink.addEventListener('click',()=>saveView());addEventListener('pagehide',()=>saveView());
const mobile=/Android|iPhone|iPad|iPod|Windows Phone|Mobile/i.test(navigator.userAgent)||(/Macintosh/i.test(navigator.userAgent)&&navigator.maxTouchPoints>1);


const labels={PLANNED:'예정',IN_PROGRESS:'진행',ON_HOLD:'보류',COMPLETED:'완료'};


function clear(message){reviewDashboard?.dispose();reviewDashboard=null;reportEditor?.dispose();reportEditor=null;items=[];selected=null;user=null;capabilities=null;++loadGeneration;++tripGeneration;$('rows').replaceChildren();$('workspace').hidden=true;$('editor').close();$('trip').close();$('trip-text').value='';$('detail').value='';$('notice').textContent=message;}


function session(){if(!sessionToken||localStorage.getItem('besma_token')!==sessionToken){clear('BESMA에 로그인한 뒤 점검계획을 다시 열어 주세요.');throw Error('로그인을 확인해 주세요.');}}


function message(code,status){return ({INSPECTION_PLAN_PERIOD_REQUIRED:'이번 점검계획은 11월 2일부터 12월 31일 사이로 정해 주세요.',INSPECTION_PLAN_NOT_FOUND_IN_RANGE:'이 기간에 예정된 본인 점검계획이 없습니다.',INSPECTION_TRIP_RANGE_SPLITS_VISIT:'여러 날 진행하는 점검의 시작일부터 종료일까지 선택해 주세요.',INSPECTION_TRIP_DATE_RANGE_INVALID:'출장 시작일과 종료일을 확인해 주세요. 최대 31일을 선택할 수 있습니다.',TEAM_ASSIGNMENT_COMPLETION_IMMUTABLE:'완료된 점검은 예정 상태로 되돌릴 수 없습니다.',TEAM_SCHEDULE_REVISION_CONFLICT:'다른 곳에서 일정이 수정되었습니다. 입력 내용을 보존했으니 새로고침 후 확인해 주세요.'})[code]||(status===403?'팀 일정 이용 권한을 확인해 주세요.':status===401?'로그인이 만료되었습니다. BESMA에서 다시 로그인해 주세요.':'처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');}


async function api(path,options={}){session();const response=await fetch(API+path,{...options,cache:'no-store',headers:{Authorization:'Bearer '+sessionToken,...(options.body?{'Content-Type':'application/json','X-BESMA-Client-Surface':'PC_WEB'}:{})}});session();const value=await response.json().catch(()=>({}));session();if(!response.ok){const error=Error(message(value.detail,response.status));error.status=response.status;if(response.status===401||response.status===403)clear(error.message);throw error;}return value;}


function el(tag,text){const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;}


function button(text,action){const n=el('button',text);n.type='button';n.className='secondary';n.onclick=()=>action();return n;}


function canEdit(row){return capabilities?.can_write&&row.can_edit&&row.owner_user_id===user?.id;}


const visitInfoCache=new Map();
function appendVisitInfo(row,host){
 const box=el('div'),address=(row.detail_text||'').split('\\n').find(line=>line.startsWith('현장주소:'))?.replace(/^현장주소:\\s*/,''),map=el('a','지도'),contacts=el('div');box.className='inspection-visit-info';map.className='inspection-map';map.target='_blank';map.rel='noopener noreferrer';
 const paintAddress=value=>{const query=value||address||row.title.replace(/^\\[점검\\] /,'');map.href='https://map.naver.com/p/search/'+encodeURIComponent(query);map.setAttribute('aria-label',row.title.replace(/^\\[점검\\] /,'')+' 지도');};paintAddress();box.append(map,contacts);host.prepend(box);
 const paint=value=>{if(!box.isConnected)return;contacts.replaceChildren();if(value.address)paintAddress(value.address);const seen=new Set(),people=[];for(const person of value.contacts||[]){const phone=String(person.phone||'').trim(),key=person.name+'|'+phone;if(!phone||seen.has(key))continue;seen.add(key);people.push({...person,phone,key});}
 const used=new Set(),primary=[];for(const role of ['소장','공무','안전']){const matches=people.filter(p=>!used.has(p.key)&&String(p.role||'').includes(role)),person=matches.find(p=>!/[·ㆍ,\/]/.test(p.role))||matches[0];if(person){used.add(person.key);primary.push(person);}}
 const lineFor=person=>{const line=el('div'),label=el('span',[person.role,person.name,person.rank].filter(Boolean).join(' ')),link=el('a',person.phone);line.className='inspection-contact-line';label.title=label.textContent;link.href='tel:'+person.phone.replace(/[^0-9+]/g,'');line.append(label,link);return line;};for(const person of primary)contacts.append(lineFor(person));const rest=people.filter(p=>!used.has(p.key));if(rest.length){const more=el('details'),summary=el('summary','더보기 ('+rest.length+'명)');more.className='inspection-contact-more';more.append(summary);for(const person of rest)more.append(lineFor(person));contacts.append(more);}if(!people.length)contacts.append(el('span','등록된 전화번호 없음'));};
 if(row.owner_user_id!==user?.id){contacts.append(el('span','연락처는 현장검색에서 확인'));const directory=el('a','현장 연락처');directory.href='/site-directory.html';box.append(directory);return;}
 const period=row.scheduled_date.slice(0,4)+'-H'+(Number(row.scheduled_date.slice(5,7))<=6?'1':'2'),key=row.public_id+'|'+period;
 contacts.textContent='전화번호 확인 중…';if(!visitInfoCache.has(key))visitInfoCache.set(key,api('/safety-features/half-year-reviews/plans/'+encodeURIComponent(row.public_id)+'/visit-info?'+new URLSearchParams({period})).catch(error=>{visitInfoCache.delete(key);throw error;}));visitInfoCache.get(key).then(paint).catch(()=>{if(box.isConnected){contacts.textContent='전화번호 조회 실패';contacts.append(button('다시 확인',()=>{box.remove();appendVisitInfo(row,host);}));}});
}
function render(){session();const query=$('search').value.trim().toLowerCase();const visible=items.filter(r=>(r.title+' '+r.owner_name+' '+(r.detail_text||'')).toLowerCase().includes(query)&&(!reviewDashboard||reviewDashboard.matches(r)));$('rows').replaceChildren();for(const row of visible){const tr=el('tr');tr.dataset.publicId=row.public_id;if(row.public_id===selectedPlan){tr.setAttribute('aria-current','true');tr.style.boxShadow='inset 3px 0 #b27d31';}tr.append(el('td',row.scheduled_date.slice(5)+(row.due_date?' ~ '+row.due_date.slice(5):'')),el('td',row.owner_name||row.assigned_user_name||''));const site=el('td');site.append(el('strong',row.title.replace(/^\[점검\] /,'')));const detail=el('div',row.detail_text||'');detail.className='detail';if(reportEditor?.enabled){const info=el('details');info.append(el('summary','현장 정보·연락처'),detail);site.append(info);}else site.append(detail);tr.append(site,el('td',labels[row.status]||row.status));const actions=el('td');if(reportEditor?.enabled&&reportEditor.mode!=='half-year'&&row.owner_user_id===user?.id)actions.append(button('사진·평가표',()=>{saveView(row.public_id);return reportEditor.open(row);}));reviewDashboard?.append(row,site,actions);if(reportEditor?.mode==='half-year'){appendVisitInfo(row,actions);if(row.owner_user_id===user?.id)tr.children[1].append(signingBundleButton({origin:API,token:sessionToken,session,context:()=>({plan:row.public_id,period:row.scheduled_date.slice(0,4)+'-H'+(Number(row.scheduled_date.slice(5,7))<=6?'1':'2')})}));}const published=publications?.get(row.public_id);if(!mobilePilot&&published)site.append(el('small',published.draft_changed?'공유한 일정에 변경사항 있음':'현장에 일정 공유됨'));if(canEdit(row)){if(row.status!=='COMPLETED'&&!reviewDashboard?.isComplete(row))actions.append(button('일정 변경',()=>reschedule(row)));actions.append(button('수정',()=>edit(row)));if(['PLANNED','IN_PROGRESS'].includes(row.status)){const confirmButton=button(published&&!published.draft_changed?'공유됨':'현장에 일정 공유',()=>confirmPlan(row));confirmButton.disabled=!!published&&!published.draft_changed;actions.append(confirmButton);}}if(!mobilePilot&&row.owner_user_id===user?.id)actions.append(button('출장신청 내용',()=>trip(row)));const extra=[...actions.children].filter(b=>['수정','현장에 일정 공유','공유됨','출장신청 내용'].includes(b.textContent));if(extra.length){const more=el('details');more.className='inspection-plan-extras';more.append(el('summary','일정·출장'));for(const b of extra)more.append(b);actions.append(more);}tr.append(actions);$('rows').append(tr);}$('empty').hidden=visible.length>0;$('summary').textContent=`점검 ${items.length}건 · 표시 ${visible.length}건`;$('read-only').hidden=!!capabilities?.can_write;}


async function reload(){const generation=++loadGeneration;$('notice').textContent='';try{const month=$('month').value;if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))throw Error('조회 월을 선택해 주세요.');const [y,m]=month.split('-').map(Number),last=new Date(y,m,0).getDate();const params=new URLSearchParams({from_date:month+'-01',to_date:month+'-'+String(last).padStart(2,'0'),inspection_only:'true',mine_only:String($('scope').value==='mine')});reviewDashboard?.setScope($('scope').value);const response=await api((mobilePilot?'/safety-features/half-year-reviews/mobile-pilot/plans':BASE+'/items')+'?'+params);if(mobilePilot)publications=new Map();else try{const value=await api('/workspace/inspection-publications');publications=new Map(value.items.map(r=>[r.public_id,r]));}catch{publications=null;}if(generation!==loadGeneration)return;items=response.items||[];try{await reviewDashboard?.load(items,params.get('from_date'),params.get('to_date'));}catch{$('notice').textContent='평가현황을 불러오지 못했습니다. 새로고침해 주세요.';}if(generation!==loadGeneration)return;render();saveView();await openEntry();}catch(error){if(generation===loadGeneration)$('notice').textContent=error.message;}}


function signature(){return JSON.stringify(['start','end','title','detail','status'].map(id=>$(id).value));}


let rescheduleRow=null,rescheduleBusy=false,overlapGeneration=0;
function shiftEnd(row,value){if(!row.due_date)return null;const span=(Date.parse(row.due_date+'T00:00:00Z')-Date.parse(row.scheduled_date+'T00:00:00Z'))/86400000;return new Date(Date.parse(value+'T00:00:00Z')+span*86400000).toISOString().slice(0,10);}
async function showOverlap(){const generation=++overlapGeneration,value=$('reschedule-date').value;if(!value||!rescheduleRow)return;$('reschedule-overlap').textContent='';let rows=items;if(value.slice(0,7)!==$('month').value){try{const[y,m]=value.slice(0,7).split('-').map(Number),last=new Date(y,m,0).getDate(),params=new URLSearchParams({from_date:value.slice(0,7)+'-01',to_date:value.slice(0,7)+'-'+String(last).padStart(2,'0'),inspection_only:'true',mine_only:'true'});rows=(await api(BASE+'/items?'+params)).items||[];}catch{if(generation===overlapGeneration)$('reschedule-overlap').textContent='같은 날의 다른 일정을 확인하지 못했습니다.';return;}}if(generation!==overlapGeneration)return;const end=shiftEnd(rescheduleRow,value)||value,overlaps=rows.filter(r=>r.public_id!==rescheduleRow.public_id&&r.status!=='COMPLETED'&&!reviewDashboard?.isComplete(r)&&r.owner_user_id===user.id&&r.scheduled_date<=end&&(r.due_date||r.scheduled_date)>=value);$('reschedule-overlap').textContent=overlaps.length?'같은 날 예정된 현장: '+overlaps.map(r=>r.title.replace(/^\[점검\] /,'')).join(' · '):'';}
function reschedule(row){if(!canEdit(row)||row.status==='COMPLETED'||reviewDashboard?.isComplete(row))return;rescheduleRow=row;$('reschedule-site').textContent=row.title.replace(/^\[점검\] /,'');$('reschedule-before').textContent='현재 점검일: '+row.scheduled_date;$('reschedule-date').value=row.scheduled_date;const bounded=row.client_item_key?.startsWith('inspection:202611:');$('reschedule-date').min=bounded?'2026-11-02':'';$('reschedule-date').max=bounded?'2026-12-31':'';$('reschedule-notice').textContent='';$('reschedule').showModal();void showOverlap();$('reschedule-date').focus();}
$('reschedule-date').oninput=()=>void showOverlap();
$('reschedule-close').onclick=()=>{if(!rescheduleBusy){overlapGeneration++;$('reschedule').close();}};
$('reschedule').addEventListener('cancel',event=>{if(rescheduleBusy)event.preventDefault();});
$('reschedule-form').onsubmit=async event=>{event.preventDefault();if(rescheduleBusy||!rescheduleRow||!canEdit(rescheduleRow))return;const row=rescheduleRow,value=$('reschedule-date').value;if(value===row.scheduled_date){$('reschedule').close();return;}rescheduleBusy=true;$('reschedule-save').disabled=$('reschedule-close').disabled=true;$('reschedule-notice').textContent='저장 중…';try{const saved=await api(BASE+'/items/'+encodeURIComponent(row.public_id),{method:'PUT',body:JSON.stringify({revision:row.revision,scheduled_date:value,due_date:shiftEnd(row,value),title:row.title,detail_text:row.detail_text||null,status:row.status,assigned_user_id:row.assigned_user_id})});selectedPlan=saved.public_id;$('month').value=saved.scheduled_date.slice(0,7);$('reschedule').close();await reload();$('notice').textContent=row.title.replace(/^\[점검\] /,'')+' 점검일을 '+saved.scheduled_date+'로 변경했습니다.';saveView(saved.public_id);}catch(error){$('reschedule-notice').textContent=error.message;if(error.status===409){try{const latest=await api(BASE+'/items/'+encodeURIComponent(row.public_id));rescheduleRow=latest;$('reschedule-before').textContent='현재 점검일: '+latest.scheduled_date;$('reschedule-notice').textContent='다른 곳에서 일정을 변경했습니다. 현재 점검일을 확인한 뒤 다시 저장해 주세요.';}catch{}}}finally{rescheduleBusy=false;$('reschedule-save').disabled=$('reschedule-close').disabled=false;}};
function closeEditor(){if(saving)return;if(signature()!==baseline&&!confirm('저장하지 않은 변경 내용을 버릴까요?'))return;$('editor').close();}


function edit(row){if(!canEdit(row))return;selected=row;$('edit-owner').textContent='점검 담당: '+row.owner_name;$('title').value=row.title;$('start').value=row.scheduled_date;$('end').value=row.due_date||'';$('detail').value=row.detail_text||'';$('status').value=row.status;$('edit-notice').textContent='';for(const id of ['start','end']){const bounded=row.client_item_key?.startsWith('inspection:202611:');$(id).min=bounded?'2026-11-02':'';$(id).max=bounded?'2026-12-31':'';}baseline=signature();$('editor').showModal();}


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


async function start(){try{session();user=await api('/auth/me');mobilePilot=mobile&&[95,523].includes(user.id);capabilities=await api(mobilePilot?'/safety-features/half-year-reviews/mobile-pilot/capabilities':BASE+'/capabilities?surface='+(mobile?'MOBILE_WEB':'PC_WEB'));if(!capabilities.can_read)throw Error('팀 일정 이용 권한을 확인해 주세요.');const halfYear=await mountHalfYearReview({origin:API,token:sessionToken,session,user,workspace:$('workspace'),panel:$('half-year-review-panel'),onReturn:async action=>{await reload();render();if(action==='next'){const next=items.filter(r=>r.owner_user_id===user.id&&r.public_id!==selectedPlan&&!reviewDashboard?.isComplete(r)).sort((a,b)=>a.scheduled_date.localeCompare(b.scheduled_date)||a.title.localeCompare(b.title))[0];if(next){saveView(next.public_id);await reportEditor.open(next);return;}$('notice').textContent='다음 평가할 현장이 없습니다.';}requestAnimationFrame(()=>{const row=[...$('rows').children].find(r=>r.dataset.publicId===selectedPlan);row?.scrollIntoView({block:'center'});row?.querySelector('button')?.focus({preventScroll:true});});}});if(halfYear.enabled){const features=await api('/safety-features/half-year-reviews/capabilities');reviewDashboard=createReviewDashboard({api,origin:API,token:sessionToken,session,user,host:$('review-dashboard'),onFilter:render,catalog:features.catalog,onOpenForm:async(row,form)=>{saveView(row.public_id);await reportEditor.open(row,{form});}});}reportEditor=halfYear.enabled?halfYear:await mountInspectionReport({origin:API,token:sessionToken,session,user,workspace:$('workspace'),panel:$('inspection-report-panel')});if(reportEditor.enabled)$('read-only').textContent='일정 수정은 PC에서 해 주세요. 반기평가는 여기서 입력·저장할 수 있습니다.';$('identity').textContent=user.name+' · 내 현장 평가계획';$('workspace').hidden=false;await restoreView();if(mobilePilot){$('scope').value='mine';$('scope').closest('label').hidden=true;$('read-only').textContent='휴대폰에서 문항 평가와 사진 촬영을 진행할 수 있습니다.';}await reload();}catch(error){clear(error.message);$('identity').textContent='';}}


void start();





async function confirmPlan(row){if(!canEdit(row)||saving)return;saving=true;try{await api('/workspace/inspection-publications/'+encodeURIComponent(row.public_id)+'/confirm',{method:'POST',body:JSON.stringify({revision:row.revision})});await reload();$('notice').textContent='현장에 일정을 공유했습니다.';}catch(error){$('notice').textContent=error.message+' 새로고침하여 반영 여부를 확인해 주세요.';}finally{saving=false;}}


