// Deep-link into the existing account lookup dialog; keep its validation and API.
if(location.pathname==='/login'&&new URLSearchParams(location.search).get('lookup')==='1'){
  let finished=false;
  const observer=new MutationObserver(openLookup);
  const timeout=setTimeout(()=>{finished=true;observer.disconnect();},15000);
  function openLookup(){
    if(finished)return;
    const button=document.querySelector('.login-card .login-issue-btn');
    if(!button)return;
    finished=true;observer.disconnect();clearTimeout(timeout);button.click();
  }
  observer.observe(document.documentElement,{childList:true,subtree:true});
  openLookup();
}
