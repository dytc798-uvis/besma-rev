// Existing task lists remain the authority; this component does not fetch or sum them.
export function createHomeTaskShortcuts({anchor,token}){
 const n=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const host=n('section'),title=n('h3','확인할 업무'),list=n('div');host.className='home-task-shortcuts';host.setAttribute('aria-label','확인할 업무');host.append(title,list);anchor.before(host);
 const styles=n('style');styles.textContent='.home-task-shortcuts{margin:0 0 14px;padding:12px;border:1px solid #91b9c9;border-radius:12px;background:#172f3c;color:#f5f9fb}.home-task-shortcuts h3{font-size:15px;margin:0 0 8px}.home-task-shortcuts>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.home-task-shortcuts button{min-width:0;min-height:64px;padding:7px 3px;background:#244757;color:#fff;border:1px solid #a4c8d6;border-radius:8px;cursor:pointer;font:inherit;font-size:12px;line-height:1.4;white-space:normal;overflow-wrap:anywhere}.home-task-shortcuts button strong{display:block;font-size:15px;margin-top:3px}.home-task-shortcuts button:focus-visible{outline:3px solid #ffd79c;outline-offset:2px}.home-task-shortcuts button:hover{background:#325d70}.home-task-shortcuts [hidden]{display:none!important}';host.prepend(styles);
 const definitions={documents:['관급 문서','today-document-tasks'],inspections:['내 점검','today-inspection-tasks'],opinions:['근로자의견','today-opinion-tasks']},states=new Map();
 const current=()=>!!token&&localStorage.getItem('besma_token')===token;
 function render(){
  list.replaceChildren();if(!current()){host.hidden=true;return;}
  let visible=0;
  for(const[key,[label,id]]of Object.entries(definitions)){
   const value=states.get(key)||{state:'LOADING'};if(value.state==='HIDDEN')continue;visible++;
   const b=n('button',label),count=n('strong');b.type='button';b.dataset.taskShortcut=key;b.setAttribute('aria-controls',id);
   const verified=value.state==='VERIFIED'&&Number.isSafeInteger(value.count)&&value.count>=0;
   count.textContent=verified?(value.partial||value.unknown>0?value.count>0?value.count+'건 · 확인 필요':'확인 필요':value.count+'건'):value.state==='LOADING'?'확인 중':'확인 필요';
   b.append(count);b.title=label+' · '+count.textContent+(verified&&value.scope?' · '+value.scope:'');b.setAttribute('aria-label',b.title);
   b.onclick=()=>{if(!current())return;const target=document.getElementById(id);if(!target||target.hidden)return;target.open=true;target.scrollIntoView({block:'start',behavior:'instant'});const summary=target.querySelector('summary');if(summary){summary.tabIndex=-1;summary.focus({preventScroll:true});}};
   list.append(b);
  }
  host.hidden=visible===0;
 }
 addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null){states.clear();host.hidden=true;}});
 render();
 return{update(key,value){if(!(key in definitions)||!current())return;states.set(key,value&&typeof value==='object'?value:{state:'UNKNOWN'});render();}};
}
