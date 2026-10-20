// Shared pages use the existing BESMA session and HQ_SAFE authorization.
let checked, pending, allowed=false;
async function check(){
 const token=localStorage.getItem('besma_token');
 if(token===checked||token===pending)return;
 allowed=false;checked=undefined;document.querySelectorAll('[data-page-share-nav]').forEach(n=>n.remove());
 if(!token)return;pending=token;
 try{const r=await fetch('https://api.besma.co.kr/page-share/capabilities',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(localStorage.getItem('besma_token')===token){checked=token;allowed=r.ok&&(await r.json()).can_read===true;}}
 catch{}finally{pending=undefined;install();}
}
function install(){
 if(!allowed||checked!==localStorage.getItem('besma_token'))return;
 for(const next of document.querySelectorAll('a[href="/photo-share.html"],a[href="/hq-safe/team-schedule"]')){
  const nav=next.closest('nav')||next.parentElement;
  if(nav.querySelector('[data-page-share-nav]')){
   const existing=nav.querySelector('[data-page-share-nav]');
   if(next.getAttribute('href')==='/photo-share.html'&&next.previousElementSibling!==existing)next.before(existing);
   continue;
  }
  const a=document.createElement('a');a.href='/page-share.html';a.textContent='페이지공유';a.className=next.className.replace(/router-link-(exact-)?active/g,'').trim();a.dataset.pageShareNav='true';
  for(const attr of next.attributes)if(attr.name.startsWith('data-v-'))a.setAttribute(attr.name,attr.value);
  next.before(a);
 }
}
new MutationObserver(()=>{check();install();}).observe(document.documentElement,{childList:true,subtree:true});
window.addEventListener('storage',check);setInterval(check,3000);check();
