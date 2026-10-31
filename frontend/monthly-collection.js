import {monthlyIdentity,monthlyQuery,monthlyCandidates,monthlyHandoff} from '/assets/monthly-source-flow.js';
const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
export async function mountMonthlyCollection(host,{api,isCurrent,initialScope={},onScope=()=>{},onRequest=()=>{}}){
 let alive=true,epoch=0,offset=null,rows=[],singleSite=false,requesting=false,restoreSelected=!!initialScope.selected;const current=()=>alive&&host.isConnected&&isCurrent();
 const root=N('section',null,'panel monthly-collection'),tools=N('div',null,'section-links'),month=N('select'),category=N('select'),team=N('select'),query=N('input'),refresh=N('button','새로고침'),summary=N('p'),notice=N('p'),siteNote=N('p'),wrap=N('div'),table=N('table'),head=N('thead'),body=N('tbody'),more=N('button','더 보기');
 month.setAttribute('aria-label','자료월');category.setAttribute('aria-label','자료종류');team.setAttribute('aria-label','팀');query.type='search';query.placeholder='현장명·파일명 검색';query.maxLength=100;query.setAttribute('aria-label','현장명·파일명 검색');refresh.type=more.type='button';notice.setAttribute('role','status');
 for(const[value,label]of[['','전체 자료'],['theme','테마점검'],['safety-cost','산업안전보건관리비'],['risk','위험성평가'],['opinions','근로자 의견청취'],['legal-training','법정교육']]){const o=N('option',label);o.value=value;category.append(o);}
 for(const value of['전체 팀','1팀','2팀','3팀','4팀','5팀','6팀','관급']){const o=N('option',value);o.value=value==='전체 팀'?'':value;team.append(o);}
 const actionNotice=N('p');actionNotice.setAttribute('role','status');
 const header=N('tr');for(const label of['자료월','팀','현장명','자료종류','파일명','최초 확인','저장상태'])header.append(N('th',label));head.append(header);table.append(head,body);wrap.append(table);wrap.style.overflowX='auto';table.style.minWidth='760px';table.style.width='100%';table.style.fontSize='14px';table.style.borderCollapse='collapse';tools.style.display='flex';tools.style.flexWrap='wrap';tools.style.gap='8px';tools.append(month,category,team,query,refresh);root.append(actionNotice);siteNote.className='mc-site-note';wrap.className='mc-table-wrap';root.append(tools,summary,notice,siteNote,wrap,more);host.append(root);
 const css=N('style');css.textContent=`
 .monthly-collection .mc-site-note{font-weight:600;line-height:1.6;overflow-wrap:break-word;}
 .monthly-collection.mc-single-site th:nth-child(3),.monthly-collection.mc-single-site td:nth-child(3){display:none;}
 .monthly-collection tr[aria-current=true]{outline:2px solid #d49a50;outline-offset:-2px;scroll-margin-top:84px;scroll-margin-bottom:16px;}
 @media(max-width:640px){
 .monthly-collection .mc-table-wrap{overflow-x:visible!important;}
 .monthly-collection table{min-width:0!important;display:block;}
 .monthly-collection thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);}
 .monthly-collection tbody{display:block;}
 .monthly-collection tr{display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;padding:16px 4px;border-bottom:1px solid #ffffff40;}
 .monthly-collection td{padding:0!important;border:0!important;line-height:1.6;word-break:keep-all;overflow-wrap:anywhere;}
 .monthly-collection td:nth-child(5){grid-column:1/-1;grid-row:1;font-weight:600;font-size:15px;}
 .monthly-collection td:nth-child(3){grid-column:1/-1;grid-row:2;color:#d6e4ed;font-size:13px;}
 .monthly-collection td:nth-child(1)::before{content:'자료월 ';color:#b4c8d4;}
 .monthly-collection td:nth-child(2)::before{content:'팀 ';color:#b4c8d4;}
 .monthly-collection td:nth-child(4){font-size:13px;}
 .monthly-collection td:nth-child(6){font-size:12px;grid-column:1/-1;color:#b4c8d4;}
 .monthly-collection td:nth-child(6)::before{content:'최초 확인 ';}
 .monthly-collection td:nth-child(7){font-size:13px;}
 .monthly-collection td[colspan]{grid-column:1/-1;}.monthly-collection td[colspan]::before{content:none;}
 }
 `;root.prepend(css);
 const labels={theme:'테마점검','safety-cost':'산업안전보건관리비',risk:'위험성평가',opinions:'의견청취','legal-training':'법정교육'};
 const currentMonth=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}).slice(0,7),validMonth=value=>typeof value==='string'&&/^20\d{2}-(0[1-9]|1[0-2])$/.test(value);
 function monthOptions(values=[],selected=month.value){const options=[...new Set([currentMonth,...values,selected].filter(validMonth))].sort().reverse();month.replaceChildren();const all=N('option','전체 자료월');all.value='';month.append(all);for(const value of options){const option=N('option',value.slice(0,4)+'년 '+Number(value.slice(5))+'월');option.value=value;month.append(option);}month.value=selected;}
 monthOptions([],currentMonth);if(typeof initialScope.month==='string'&&/^$|^20\d{2}-(0[1-9]|1[0-2])$/.test(initialScope.month))monthOptions([],initialScope.month);if([...category.options].some(x=>x.value===initialScope.category))category.value=initialScope.category;if([...team.options].some(x=>x.value===initialScope.team))team.value=initialScope.team;if(typeof initialScope.query==='string')query.value=initialScope.query.slice(0,100);
 function remember(){onScope({month:month.value,category:category.value,team:team.value,query:query.value,selected:initialScope.selected||''});}
 function draw(){root.classList.toggle('mc-single-site',singleSite);siteNote.hidden=!singleSite;siteNote.textContent=singleSite?(rows.find(item=>item.site)?.site||''):'';body.replaceChildren();for(const item of rows){const tr=N('tr');for(const text of[item.month,item.team,item.site||'현장 확인 필요',labels[item.category]||item.category,item.filename,new Date(item.first_seen).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false}),item.state==='SAVED'?'저장 완료':'저장 완료 · 현장 확인 필요']){const td=N('td',text);td.style.padding='10px 8px';td.style.borderBottom='1px solid #ddd';td.style.verticalAlign='top';td.style.overflowWrap='anywhere';tr.append(td);}const cell=tr.children[4],button=N('button','채팅에서 요청');button.type='button';button.style.minHeight='44px';button.dataset.monthlyRequest=item.id;button.disabled=requesting;button.onclick=()=>requestSource(item,button);cell.append(N('br'),button);if(initialScope.selected===item.id)tr.setAttribute('aria-current','true');body.append(tr);}if(!rows.length){const tr=N('tr'),td=N('td','이 조건으로 확인된 수신자료가 없습니다.');td.colSpan=7;td.style.padding='24px';tr.append(td);body.append(tr);}more.hidden=offset===null;more.style.display=offset===null?'none':'';if(restoreSelected){restoreSelected=false;const selected=body.querySelector('tr[aria-current=true]');if(selected)requestAnimationFrame(()=>{if(current()&&selected.isConnected)selected.scrollIntoView({block:'nearest',inline:'nearest'});});}}
 async function requestSource(item,button){
 if(requesting||!current())return;requesting=true;button.disabled=true;actionNotice.replaceChildren(N('span','자료의 원본을 확인하고 있습니다.'));
 try{monthlyIdentity(item);const access=await api('/work-requests/availability');const maximum=Math.min(32*1024*1024,Number.isSafeInteger(access.original_max_bytes)?access.original_max_bytes:16*1024*1024);if(item.size>maximum)throw Error(Math.floor(maximum/1024/1024)+'MB를 넘는 자료는 아직 채팅으로 받을 수 없습니다.');if(!current())return;if(!access.enabled||!access.nas_files)throw Error('이 계정의 채팅 자료 요청 권한을 확인해 주세요.');const found=await api('/work-requests/nas/search',{method:'POST',body:JSON.stringify({q:monthlyQuery(item)})});if(!current())return;const candidates=monthlyCandidates(item,found.items);if(!candidates.length)throw Error('이 자료는 아직 채팅으로 받을 수 없습니다. NAS의 자료는 그대로 보관되어 있습니다.');
 const choose=source=>{if(!current())return;initialScope.selected=item.id;remember();onRequest(monthlyHandoff(item,source));};
 if(candidates.length===1)choose(candidates[0]);else{actionNotice.replaceChildren(N('strong','같은 이름의 원본이 여러 개입니다. 폴더를 확인해 선택해 주세요.'));for(const source of candidates){const pick=N('button',source.relative_path);pick.type='button';pick.style.minHeight='44px';pick.onclick=()=>choose(source);actionNotice.append(pick);}}
 }catch(error){if(current())actionNotice.textContent=error.message||'자료의 원본을 확인하지 못했습니다. 다시 시도해 주세요.';}finally{requesting=false;if(current())button.disabled=false;}
 }
 async function load(append=false){remember();const id=++epoch;refresh.disabled=more.disabled=true;notice.textContent='취합현황을 확인하고 있습니다.';
  try{const data=await api('/monthly-collection/overview?'+new URLSearchParams({month:month.value,category:category.value,team:team.value,q:query.value.trim(),offset:String(append?offset||0:0)}));if(!current()||id!==epoch)return;monthOptions(Array.isArray(data.months)?data.months:[],month.value);rows=append?[...rows,...data.items]:data.items;offset=data.next_offset;singleSite=data.site_count===1&&rows.every(item=>item.site)&&new Set(rows.map(item=>item.site)).size===1;summary.textContent='수신 파일 '+data.count+'개 · 현장 확인 '+data.site_count+'곳 · '+data.schedule;notice.textContent=data.state==='NOT_RECEIVED'?'아직 실제 수신 완료 기록이 없습니다.':('마지막 현황 반영 '+new Date(data.generated_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' · 확인할 항목 '+data.review_count+'건');draw();}
  catch(e){if(current()&&id===epoch){rows=[];offset=null;singleSite=false;siteNote.hidden=true;body.replaceChildren();summary.textContent='취합현황을 확인하지 못했습니다.';notice.textContent=e.message;more.hidden=true;more.style.display='none';}}
  finally{if(current()&&id===epoch)refresh.disabled=more.disabled=false;}
 }
 refresh.onclick=()=>load();more.onclick=()=>load(true);month.onchange=category.onchange=team.onchange=()=>load();let timer;query.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>load(),220);};await load();return()=>{alive=false;epoch++;clearTimeout(timer);root.remove();};
}
