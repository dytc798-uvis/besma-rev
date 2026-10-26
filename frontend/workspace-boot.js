/* Parser-time route gate. HQ landing pages do not download or mount the legacy app. */
(()=>{
 const scripts=__BESMA_LEGACY_SCRIPTS__,nav=__BESMA_NAV_SCRIPT__;
 const root=document.documentElement,path=location.pathname;
 const hq=/^\/hq-(?:safe|other)(?:\/|$)/.test(path);
 const preserved=/^\/hq-safe\/(functional-eval(?:-monitoring|-rewards-sanctions|\/grade-report)?|documents(?:\/.*)?|document-explorer|document-instances\/.*|government-contact|communications|safety-policy-goals|user-guide)\/?$/;
 const ready=document.readyState==='loading'?new Promise(r=>document.addEventListener('DOMContentLoaded',r,{once:true})):Promise.resolve();
 function release(){root.classList.remove('besma-route-gate','besma-login-preparing');document.getElementById('besma-route-status')?.remove();}
 if(hq)root.classList.add('besma-route-gate');else if(path.startsWith('/login'))root.classList.add('besma-login-preparing');
 ready.then(()=>{if(root.classList.contains('besma-route-gate')||root.classList.contains('besma-login-preparing')){const status=document.createElement('div');status.id='besma-route-status';status.setAttribute('role','status');status.textContent='BESMA 업무공간을 열고 있습니다.';document.body.append(status);}});
 let loaded=false;
 const add=src=>new Promise((resolve,reject)=>{const s=document.createElement('script');s.type='module';s.async=false;s.src=src;s.onload=resolve;s.onerror=reject;document.head.append(s);});
 async function legacy(){if(loaded)return;loaded=true;await ready;await add(nav);for(const src of scripts)await add(src);}
 async function route(){
  const token=localStorage.getItem('besma_token')||'';
  if(!hq||!token){if(hq)release();return legacy();}
  try{
   const response=await fetch('https://api.besma.co.kr/workspace/bootstrap',{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:AbortSignal.timeout(8000)});
   if(token!==localStorage.getItem('besma_token'))return location.replace('/login');
   if(!response.ok){release();return legacy();}
   const data=await response.json();
   window.__BESMA_READ_BOOTSTRAP__=()=>localStorage.getItem('besma_token')===token?data:null;
   if(!preserved.test(path)){location.replace('/workspace.html');return;}
   await legacy();
  }catch{
   await ready;const status=document.getElementById('besma-route-status');if(status){status.textContent='연결을 확인한 뒤 다시 시도해 주세요. ';const button=document.createElement('button');button.textContent='다시 시도';button.onclick=()=>location.reload();status.append(button);}
  }
 }
 route();
})();
