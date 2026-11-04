export function createSummaryAutosave({owner,context,canSave,save,notify,delay=1000}){
 const prefix='besma-review-summary-v1:'+encodeURIComponent(owner)+':',states=new Map();let timer=null,working=null,dead=false;
 const state=key=>{if(!states.has(key))states.set(key,{});return states.get(key);};
 const storageKey=key=>prefix+encodeURIComponent(key);
 const savedKey=key=>prefix+'saved:'+encodeURIComponent(key);
 function archive(key,text){if(!text?.trim())return;try{localStorage.setItem(savedKey(key),JSON.stringify({key,text,base:text,at:Date.now(),kind:'saved'}));}catch{}}
 function savedBackup(key){try{const r=JSON.parse(localStorage.getItem(savedKey(key))||'null');return r&&r.key===key&&typeof r.text==='string'&&r.text.trim()&&Number.isFinite(r.at)&&Date.now()-r.at>=0&&Date.now()-r.at<30*86400000?r:null;}catch{return null;}}
 function read(key){try{const r=JSON.parse(localStorage.getItem(storageKey(key))||'null');return r&&r.key===key&&typeof r.text==='string'&&typeof r.base==='string'&&Number.isFinite(r.at)&&Date.now()-r.at>=0&&Date.now()-r.at<30*86400000?r:null;}catch{return null;}}
 function preserve(key,text,base){const s=state(key);try{localStorage.setItem(storageKey(key),JSON.stringify({key,text,base,at:Date.now()}));s.local=true;}catch{s.local=false;}return s;}
 function schedule(){clearTimeout(timer);if(!dead)timer=setTimeout(()=>void flush(),delay);}
 function recover(key,server){const r=read(key);if(!r){const backup=!server.trim()&&savedBackup(key);if(backup){const s=state(key);s.candidate=backup;s.local=true;}return null;}if(r.text.trim()===server){archive(key,r.text);try{localStorage.removeItem(storageKey(key));}catch{}return null;}const s=state(key);s.candidate=r;s.local=true;if(r.base===server){s.dirty=true;s.candidate=null;schedule();return r.text;}return null;}
 function input(text){const c=context();if(!c)return;const s=preserve(c.key,text,c.serverSummary);s.dirty=true;s.error='';s.candidate=null;notify();schedule();}
 function confirmed(key,text,at){const s=state(key),c=context();s.at=at;s.error='';archive(key,text);const local=c?.key===key?c.summary:read(key)?.text;
  if(local?.trim()===text){s.dirty=false;s.candidate=null;try{localStorage.removeItem(storageKey(key));}catch{}}
  else if(local!=null){preserve(key,local,text);s.dirty=true;schedule();}
 }
 async function flush(){
  if(dead)return false;if(working)return working;const c=context();if(!c||!state(c.key).dirty)return true;
  if(!canSave()){schedule();return false;}const s=state(c.key);s.saving=true;notify();
  working=(async()=>{try{const result=await save({...c});if(!result)throw Error('총평 저장을 확인하지 못했습니다.');confirmed(c.key,result.summary,result.at);return true;}
   catch(e){s.error=e.message||'서버 연결을 확인해 주세요.';s.dirty=true;return false;}
   finally{s.saving=false;working=null;notify();}})();return working;
 }
 function status(){const c=context();if(!c)return{};const s=state(c.key);return{...s,dirty:s.dirty===true||c.summary.trim()!==c.serverSummary,at:s.at||c.serverAt};}
 function restore(){const c=context(),r=c&&state(c.key).candidate;if(!r)return null;state(c.key).candidate=null;return r.text;}
 const online=()=>{if(!dead)void flush();};addEventListener('online',online);
 return{recover,input,confirmed,flush,status,restore,pending:()=>!!working,settled:()=>working||Promise.resolve(),refresh:notify,dispose(){dead=true;clearTimeout(timer);removeEventListener('online',online);}};
}
