import{mountTeamActivity}from'/evaluation-activity.js?v=2026.11.09.5';
const token=localStorage.getItem('besma_token');let enabled=false,reader=false,entry=null;
const current=()=>token&&localStorage.getItem('besma_token')===token;
function clear(){entry?.remove();entry=null;enabled=false;}
function mount(){const menus=document.getElementById('menus');if(!enabled||!current()||!menus||(!reader&&menus.querySelectorAll('a').length<9)||entry?.isConnected)return;entry=document.createElement('a');entry.href=reader?'/half-year-reader.html':'/inspection-plan.html';entry.id='inspection-plan-entry';const number=document.createElement('b');number.textContent='10';const name=document.createElement('span');name.textContent=reader?'반기평가':'내 점검·반기평가';entry.append(number,name);const before=document.getElementById('document-sign-entry');menus.insertBefore(entry,before?.parentElement===menus?before:null);}
async function start(){
 try{const response=await fetch('https://api.besma.co.kr/safety-features/team-schedule/capabilities?surface=PC_WEB',{cache:'no-store',headers:{Authorization:'Bearer '+token}});if(!current())return;if(response.ok){const value=await response.json();if(value.can_read===true){enabled=true;mount();mountTeamActivity();return;}}
 const result=await fetch('https://api.besma.co.kr/safety-features/half-year-reader/capabilities',{cache:'no-store',headers:{Authorization:'Bearer '+token}});if(!result.ok||!current())return;const value=await result.json();if(value.can_read===true&&value.can_write===false&&value.headquarters_reader===true){reader=true;enabled=true;mount();}
 }catch{clear();}
}
if(token){void start();new MutationObserver(mount).observe(document.body,{childList:true,subtree:true});}
window.addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null)clear();});
