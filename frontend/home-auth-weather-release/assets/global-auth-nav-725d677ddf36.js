const tokenKey='besma_token';
const readToken=()=>localStorage.getItem(tokenKey)||'';
let mountedToken=readToken(),pending=false;
const control=document.createElement('button');
control.type='button';control.id='besma-global-logout';control.className='besma-global-logout';
control.dataset.homeAuth='logout';control.textContent='로그아웃';
const fallback=document.createElement('div');fallback.className='besma-global-account';
fallback.setAttribute('aria-label','계정');fallback.append(control);
function place(){
  const token=readToken();control.hidden=!token;
  for(const link of document.querySelectorAll('.home-auth-links a[data-home-auth],.home-auth-links>[aria-hidden]'))link.hidden=!!token;
  const group=document.querySelector('.home-auth-links');
  if(group){if(control.parentElement!==group)group.append(control);fallback.remove();}
  else if(!fallback.isConnected&&token){fallback.append(control);document.body.append(fallback);}
}
async function clearLegacySession(token){
  const script=[...document.querySelectorAll('script[src]')].find(el=>/\/assets\/index-workspace-[^/]+\.js(?:\?|$)/.test(el.src));
  if(!script)return false;
  let timer;
  try{
    const legacy=await Promise.race([import(script.src),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('session-load-timeout')),1500);})]);
    if(readToken()===token&&typeof legacy.B==='function'){
      const session=legacy.B();if(session.token===token){session.logout();return true;}
    }
  }catch{}finally{clearTimeout(timer);}
  return false;
}
async function logout(){
  if(pending)return;pending=true;control.disabled=true;control.textContent='로그아웃 중';
  const token=readToken();
  try{if(token)await fetch('https://api.besma.co.kr/auth/logout',{method:'POST',headers:{Authorization:'Bearer '+token},cache:'no-store',signal:AbortSignal.timeout(4000)});}catch{}
  finally{
    const cleared=await clearLegacySession(token);
    if(readToken()===token||(cleared&&!readToken())){
      for(const key of [tokenKey,'besma_test_persona','besma_test_site_context_id'])localStorage.removeItem(key);
      location.replace('/login?form=1');
    }else location.reload();
  }
}
control.addEventListener('click',()=>void logout());
window.addEventListener('storage',event=>{
  if(event.key!==tokenKey&&event.key!==null)return;
  const token=readToken();place();
  if(mountedToken&&token!==mountedToken){if(token)location.reload();else location.replace('/login?form=1');}
  mountedToken=token;
});
window.addEventListener('pageshow',()=>{if(mountedToken&&!readToken())location.replace('/login?form=1');else place();});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',place,{once:true});else place();
