const token=localStorage.getItem('besma_token');
let enabled=false,link=null;
function remove(){link?.remove();link=null;enabled=false;}
function place(){const menu=document.getElementById('menus');if(!enabled||!menu||menu.querySelectorAll('a').length<9||link?.isConnected)return;link=document.createElement('a');link.href='/inspection-plan.html';link.id='inspection-plan-entry';const number=document.createElement('b');number.textContent='10';const text=document.createElement('span');text.textContent='내 점검계획';link.append(number,text);menu.insertBefore(link,document.getElementById('document-sign-entry'));}
if(token){fetch('https://api.besma.co.kr/safety-features/team-schedule/capabilities?surface=PC_WEB',{cache:'no-store',headers:{Authorization:'Bearer '+token}}).then(async response=>{if(!response.ok||localStorage.getItem('besma_token')!==token)return;const value=await response.json();if(localStorage.getItem('besma_token')!==token)return;enabled=value.can_read===true;place();}).catch(remove);new MutationObserver(place).observe(document.body,{childList:true,subtree:true});}
window.addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null)remove();});
