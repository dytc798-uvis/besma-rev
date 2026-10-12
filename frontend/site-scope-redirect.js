let last='',busy=false;
async function check(){const token=localStorage.getItem('besma_token')||'';if(!token){last='';return;}if(token===last||busy)return;busy=true;try{const r=await fetch('https://api.besma.co.kr/site-invitations/access',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)return;const p=await r.json();if(token!==localStorage.getItem('besma_token'))return;last=token;if(p.restricted)location.replace('/site-workspace.html');}catch{}finally{busy=false;}}
check();setInterval(check,750);
