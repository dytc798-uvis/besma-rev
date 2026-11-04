// Existing task lists remain the authority; this component does not fetch or sum them.
export function createHomeTaskShortcuts({anchor,token}){
 const n=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const host=n('section'),title=n('h3','확인할 업무'),list=n('div'),urgent=n('div');urgent.hidden=true;urgent.className='home-task-urgent';urgent.style.gridTemplateColumns='repeat(auto-fit,minmax(120px,1fr))';urgent.style.marginTop='8px';host.className='home-task-shortcuts';host.setAttribute('aria-label','확인할 업무');host.append(title,list,urgent);anchor.before(host);
 const styles=n('style');styles.textContent='.home-task-shortcuts{margin:0 0 14px;padding:12px;border:1px solid #91b9c9;border-radius:12px;background:#172f3c;color:#f5f9fb}.home-task-shortcuts h3{font-size:15px;margin:0 0 8px}.home-task-shortcuts>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.home-task-shortcuts button{min-width:0;min-height:64px;padding:7px 3px;background:#244757;color:#fff;border:1px solid #a4c8d6;border-radius:8px;cursor:pointer;font:inherit;font-size:12px;line-height:1.4;white-space:normal;overflow-wrap:anywhere}.home-task-shortcuts button strong{display:block;font-size:15px;margin-top:3px}.home-task-shortcuts button:focus-visible{outline:3px solid #ffd79c;outline-offset:2px}.home-task-shortcuts button:hover{background:#325d70}.home-task-shortcuts [hidden]{display:none!important}';host.prepend(styles);
 const definitions={documents:['관급 문서','today-document-tasks'],inspections:['내 점검','today-inspection-tasks'],opinions:['근로자의견','today-opinion-tasks']},states=new Map();
 const current=()=>!!token&&localStorage.getItem('besma_token')===token;
 function render(){
  list.replaceChildren();urgent.replaceChildren();urgent.hidden=true;if(!current()){host.hidden=true;return;}
  let visible=0;
  for(const[key,[label,id]]of Object.entries(definitions)){
   const value=states.get(key)||{state:'LOADING'};if(value.state==='HIDDEN')continue;visible++;
   const b=n('button',label),count=n('strong');b.type='button';b.dataset.taskShortcut=key;b.setAttribute('aria-controls',id);
   const verified=value.state==='VERIFIED'&&Number.isSafeInteger(value.count)&&value.count>=0;
   count.textContent=verified?(value.partial||value.unknown>0?value.count>0?value.count+'건 · 확인 필요':'확인 필요':value.count+'건'):value.state==='LOADING'?'확인 중':'확인 필요';
   b.append(count);b.title=label+' · '+count.textContent+(verified&&value.scope?' · '+value.scope:'');b.setAttribute('aria-label',b.title);
   function open(filter=null){if(!current())return;const target=document.getElementById(id);if(!target||target.hidden)return;if(filter){const control=target.querySelector(key==='documents'?'#home-document-filter':'#home-inspection-filter');if(!control||!Array.from(control.options).some(x=>x.value===filter))return;control.value=filter;control.dispatchEvent(new Event('change',{bubbles:true}));}target.open=true;target.scrollIntoView({block:'start',behavior:'instant'});const summary=target.querySelector('summary');if(summary){summary.tabIndex=-1;summary.focus({preventScroll:true});}}
   b.onclick=()=>open();
   if(['documents','inspections'].includes(key)&&verified&&Number.isSafeInteger(value.overdue)&&value.overdue>0&&value.overdue<=value.count){const due=n('button'),dueLabel=n('span',label),dueState=n('span',(key==='documents'?'기한 초과 ':'예정일 지남 ')+value.overdue+'건');dueLabel.style.display=dueState.style.display='block';dueState.style.whiteSpace='nowrap';due.append(dueLabel,dueState);due.type='button';due.dataset.taskOverdue=key;due.setAttribute('aria-label',label+' · '+dueState.textContent);due.setAttribute('aria-controls',id);due.title=(value.scope||'')+' · 확인된 기한 기준 · 기존 검색 조건 유지';due.onclick=()=>open('overdue');urgent.append(due);urgent.hidden=false;}
   list.append(b);
  }
  host.hidden=visible===0;
 }
 addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null){states.clear();host.hidden=true;}});
 render();
 return{update(key,value){if(!(key in definitions)||!current())return;states.set(key,value&&typeof value==='object'?value:{state:'UNKNOWN'});render();}};
}
