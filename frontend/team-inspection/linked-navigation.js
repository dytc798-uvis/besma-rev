export function createLinkedNavigation({enabled,host,context,request,blocked,apply,interval=1500}){
 const button=document.createElement('button'),status=document.createElement('span'),box=document.createElement('div');
 button.type='button';button.textContent='기기 연동 켜짐';button.setAttribute('aria-pressed','true');
 box.className='hyr-linked-navigation';box.style.cssText='display:flex;align-items:center;gap:8px;flex-wrap:wrap';status.setAttribute('role','status');box.append(button,status);if(enabled)host.append(box);
 const device=crypto.randomUUID();let active=true,dead=false,current='',version=0,pending=null,local=null,sequence=0,running=false;
 const same=(a,b)=>!!a&&!!b&&['form','subject','criterion'].every(k=>a[k]===b[k]);
 function reset(key){current=key;version=0;pending=local=null;status.textContent='';}
 const valid=c=>c&&c.key&&c.path;
 function receive(value){if(!Number.isSafeInteger(value?.version)||value.version<=version)return;version=value.version;if(value.position?.device!==device&&value.position)pending=value.position;else pending=null;}
 async function tick(){
  if(!enabled||dead||!active||running||document.hidden)return;const c=context();if(!valid(c))return;
  if(current!==c.key)reset(c.key);running=true;
  try{
   const remote=await request(c.path);if(dead||context()?.key!==c.key)return;receive(remote);
   // Never replay a disconnected device's old navigation after reconnecting.
   if(local&&Date.now()-local.at>10000)local=null;
   if(local){const target=local;local=null;const result=await request(c.path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...target.position,version,device,sequence:target.sequence})});if(dead||context()?.key!==c.key)return;receive(result);}
   if(pending){if(blocked()){status.textContent='기기 연동 · 현재 작업 후 이동';return;}const target=pending;if(await apply(target)){if(context()?.key!==c.key)return;if(pending===target)pending=null;status.textContent='기기 연동됨';}}
   else status.textContent='기기 연동 켜짐';
  }catch{if(context()?.key===c.key){local=null;status.textContent='기기 연동 대기 · 연결 확인 중';}}
  finally{running=false;}
 }
 function publish(position){if(!enabled||dead||!active)return;const c=context();if(!valid(c)||!position?.subject)return;if(current!==c.key)reset(c.key);if(same(local?.position,position))return;pending=null;local={position,sequence:++sequence,at:Date.now()};void tick();}
 button.onclick=()=>{active=!active;button.textContent=active?'기기 연동 켜짐':'기기 연동 꺼짐';button.setAttribute('aria-pressed',String(active));pending=local=null;status.textContent='';if(active)void tick();};
 const timer=enabled?setInterval(()=>void tick(),interval):null;
 const resume=()=>{if(!document.hidden)void tick();};document.addEventListener('visibilitychange',resume);addEventListener('online',resume);
 return{publish,refresh:tick,dispose(){dead=true;clearInterval(timer);document.removeEventListener('visibilitychange',resume);removeEventListener('online',resume);box.remove();}};
}
