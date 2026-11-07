import {isPhoneDevice} from '/evaluation-device.js?v=2026.11.07.1';
export function createLinkedNavigation({enabled,host,context,request,blocked,apply,getPosition=()=>null,interval=1500,presenceInterval=5000,onMode=()=>{}}){
 const phone=isPhoneDevice(),kind=phone?'PHONE':'PC',mine=phone?'핸드폰':'PC',other=phone?'PC':'핸드폰';
 const box=document.createElement('div'),modes=document.createElement('div'),deviceLabel=document.createElement('strong'),guide=document.createElement('p'),status=document.createElement('span'),buttons=new Map();const settings=document.createElement('details'),summary=document.createElement('summary');settings.className='hyr-device-settings';settings.append(summary);box.className='hyr-linked-navigation';box.style.cssText='display:flex;align-items:center;gap:8px;flex-wrap:wrap;width:100%';modes.style.cssText='display:flex;gap:6px;flex-wrap:wrap';modes.setAttribute('role','group');modes.setAttribute('aria-label','평가 기기 선택');deviceLabel.textContent='현재 기기: '+mine;guide.style.cssText='flex-basis:100%;margin:0;line-height:1.5';status.setAttribute('role','status');status.style.fontSize='13px';box.append(deviceLabel,modes,status,guide);settings.append(box);if(enabled)host.append(settings);
 const device=crypto.randomUUID();let choice='AUTO',dead=false,current='',version=0,pending=null,local=null,sequence=0,running=false,peers=new Set(),lastPresence=0,lastSuccess=0,connected=false,hasBeenSolo=false;
 const same=(a,b)=>!!a&&!!b&&['form','subject','criterion'].every(k=>a[k]===b[k]),valid=c=>c&&c.key&&c.path;
 const paired=()=>choice!=='SOLO'&&peers.size>0;
 function paint(){const together=choice==='PAIRED'||paired();for(const[key,b]of buttons){const selected=key===(together?'PAIRED':'SOLO');b.setAttribute('aria-pressed',String(selected));b.style.background=selected?'#174e64':'#fff';b.style.color=selected?'#fff':'#263747';b.style.border='1px solid #9eafb9';}box.dataset.device=kind;box.dataset.mode=together?'PAIRED':'SOLO';onMode(paired()?'PAIRED':'SOLO');summary.textContent=mine+(together?' · '+other+' 병행':' 단독')+' · 연결 설정';
  guide.textContent=phone?(together?'PC와 같은 문항을 보며 핸드폰으로 증빙사진을 촬영하세요. 핸드폰에서도 채점과 확인내용을 입력할 수 있습니다.':'핸드폰에서 채점·확인내용 입력과 증빙사진 촬영을 모두 진행하세요.'):(together?'PC에서 채점과 확인내용을 입력하고, 핸드폰에서 증빙사진을 촬영하세요. 어느 기기에서 다음 문항으로 이동해도 함께 바뀝니다.':'PC에서 채점과 확인내용을 입력하세요. 필요한 사진은 파일로 추가할 수 있습니다.');
  status.textContent=choice==='SOLO'?mine+' 단독 작업':paired()?other+' 연결됨':choice==='PAIRED'?other+'에서 같은 계정으로 같은 현장 평가를 열어 주세요.':connected?mine+' 단독 작업 · '+other+' 접속 시 병행으로 전환':other+' 접속 확인 중…';
 }
 for(const[key,label]of [['SOLO',mine+' 단독'],['PAIRED',other+' 병행']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.style.minHeight='44px';b.onclick=()=>{choice=key;pending=local=null;lastPresence=0;paint();void tick();};buttons.set(key,b);modes.append(b);}
 function reset(key){current=key;version=0;pending=local=null;peers.clear();lastPresence=lastSuccess=0;connected=false;hasBeenSolo=false;paint();}
 function receive(value){if(!Number.isSafeInteger(value?.version)||value.version<=version)return;version=value.version;if(value.position?.device!==device&&peers.has(value.position?.device))pending=value.position;else pending=null;}
 async function tick(){
  if(!enabled||dead||running||document.hidden)return;const c=context();if(!valid(c))return;if(current!==c.key)reset(c.key);running=true;
  try{
   if(!lastPresence||Date.now()-lastPresence>=presenceInterval){lastPresence=Date.now();const path=c.path.replace(/(\?|$)/,'/presence$1'),value=await request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device,device_type:kind,mode:choice})});if(dead||context()?.key!==c.key)return;if(!Array.isArray(value.peers))throw Error('presence');const wasPaired=paired(),previousPeers=peers;peers=new Set(value.peers.filter(p=>p.device_type!==kind&&['PHONE','PC'].includes(p.device_type)).map(p=>p.device));lastSuccess=Date.now();connected=true;if(!paired())hasBeenSolo=true;if(paired()&&(!wasPaired||[...peers].some(id=>!previousPeers.has(id)))){if(hasBeenSolo){const position=getPosition();if(position?.subject)local={position,sequence:++sequence,at:Date.now()};}else local=null;}paint();}
   if(!paired()){pending=local=null;return;}
   const remote=await request(c.path);if(dead||context()?.key!==c.key)return;receive(remote);
   if(local&&Date.now()-local.at>10000)local=null;
   if(local){const target=local;local=null;const result=await request(c.path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...target.position,version,device,sequence:target.sequence})});if(dead||context()?.key!==c.key)return;receive(result);}
   if(pending){if(blocked()){status.textContent='입력이나 촬영이 끝나면 '+other+(phone?'와':'과')+' 같은 문항으로 이동합니다.';return;}const target=pending;if(await apply(target)){if(context()?.key!==c.key)return;if(pending===target)pending=null;status.textContent=other+(phone?'와':'과')+' 같은 문항을 보고 있습니다.';}}
  }catch{if(context()?.key===c.key){local=null;if(Date.now()-lastSuccess>45000){peers.clear();connected=false;}paint();status.textContent='인터넷 연결을 기다리고 있습니다. 입력 내용은 유지됩니다.';}}
  finally{running=false;}
 }
 function publish(position){if(!enabled||dead||choice==='SOLO')return;const c=context();if(!valid(c)||!position?.subject)return;if(current!==c.key)reset(c.key);if(same(local?.position,position))return;pending=null;local={position,sequence:++sequence,at:Date.now()};void tick();}
 paint();const timer=enabled?setInterval(()=>void tick(),interval):null,resume=()=>{if(!document.hidden){lastPresence=0;void tick();}};document.addEventListener('visibilitychange',resume);addEventListener('online',resume);
 return{publish,refresh:tick,dispose(){dead=true;clearInterval(timer);document.removeEventListener('visibilitychange',resume);removeEventListener('online',resume);settings.remove();}};
}
