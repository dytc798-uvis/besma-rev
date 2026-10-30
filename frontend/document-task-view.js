const FILTERS=['all','overdue','missing','review','rejected','unknown'];
export function restoreDocumentTaskView(value){return {filter:FILTERS.includes(value?.filter)?value.filter:'all',query:typeof value?.query==='string'?value.query.slice(0,100):'',selected:typeof value?.selected==='string'&&value.selected.length<=600?value.selected:''};}
export function documentTaskKey(row,month,unknown=false){return JSON.stringify([month,row.siteCode,row.documentCode||'',row.period||'',row.instanceId||null,unknown]);}
export function mountDocumentTaskView(container,{tasks,unknown,month,sites,state,buildHref,onChange,onNavigate,current}){
 const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
 const rows=[...tasks.map(item=>({item,unknown:false})),...unknown.map(item=>({item,unknown:true}))];
 const name=row=>row.siteName||sites.find(site=>site.code===row.siteCode)?.name||'현장 확인';
 const criteria=[['all','전체',()=>true],['overdue','기한 초과',r=>!r.unknown&&r.item.overdue===true],['missing','미제출',r=>!r.unknown&&r.item.status==='NOT_SUBMITTED'],['review','검토',r=>!r.unknown&&['SUBMITTED','IN_REVIEW','UNDER_REVIEW','RESUBMITTED'].includes(r.item.status)],['rejected','반려',r=>!r.unknown&&r.item.status==='REJECTED'],['unknown','확인 필요',r=>r.unknown]];
 if(!rows.some(r=>documentTaskKey(r.item,month,r.unknown)===state.selected))state.selected='';
 const controls=node('div',null,'document-task-controls'),searchGroup=node('div'),searchLabel=node('label','현장·문서 검색'),input=node('input');input.id='home-document-query';input.type='search';input.maxLength=100;input.placeholder='현장명·문서명';input.autocomplete='off';input.value=state.query;searchLabel.htmlFor=input.id;searchGroup.append(searchLabel,input);
 const filterGroup=node('div'),filterLabel=node('label','상태'),select=node('select');select.id='home-document-filter';filterLabel.htmlFor=select.id;
 for(const[key,label,predicate]of criteria){const option=node('option',label+' ('+rows.filter(predicate).length+')');option.value=key;select.append(option);}select.value=state.filter;filterGroup.append(filterLabel,select);controls.append(searchGroup,filterGroup);
 const result=node('p',null,'document-task-result');result.id='home-document-result';result.setAttribute('role','status');result.setAttribute('aria-live','polite');const list=node('ul',null,'document-task-list');container.append(controls,result,list);
 function render(){
  if(!current())return;const predicate=criteria.find(c=>c[0]===state.filter)[2],terms=state.query.normalize('NFC').trim().toLocaleLowerCase('ko-KR').split(/\s+/).filter(Boolean);
  const filtered=rows.filter(r=>predicate(r)&&terms.every(term=>[name(r.item),r.item.title,r.item.period||'',r.unknown?'확인 필요':r.item.label].join(' ').normalize('NFC').toLocaleLowerCase('ko-KR').includes(term)));
  filtered.sort((a,b)=>Number(b.item.overdue===true)-Number(a.item.overdue===true)||Number(a.unknown)-Number(b.unknown));list.replaceChildren();result.textContent='표시 '+filtered.length+'건 / 확인할 문서 '+rows.length+'건';
  for(const r of filtered){const row=r.item,key=documentTaskKey(row,month,r.unknown),li=node('li'),link=node('a',name(row)+' · '+row.title+' · '+(r.unknown?'확인 필요':row.label));link.href=buildHref(row,month,'/');link.dataset.documentSite=row.siteCode;if(row.documentCode)link.dataset.documentCode=row.documentCode;if(row.period)link.dataset.documentPeriod=row.period;link.dataset.documentTask=key;if(r.unknown)link.dataset.documentUnknown='true';if(state.selected===key){li.classList.add('selected');link.setAttribute('aria-current','true');}
   link.onclick=()=>{if(!current())return;state.selected=key;onChange();onNavigate();};li.append(link);if(row.period)li.append(node('small',row.period==='once'?'1회':row.period));if(!r.unknown)li.append(node('small',row.dueDate?(row.overdue?'기한 지남 · ':'기한 ')+row.dueDate:'제출기한 확인 필요'));list.append(li);
  }
  if(!filtered.length)list.append(node('li',rows.length?'현재 검색·상태 조건에 맞는 문서가 없습니다.':'현재 취합월의 확인된 대상에서 미제출·검토·반려 문서가 없습니다.'));
 }
 input.oninput=()=>{if(!current())return;state.query=input.value.slice(0,100);render();onChange();};select.onchange=()=>{if(!current())return;state.filter=FILTERS.includes(select.value)?select.value:'all';render();onChange();};render();
}
