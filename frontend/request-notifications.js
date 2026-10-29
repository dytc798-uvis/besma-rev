const el=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};

export async function mountRequestNotifications(host,{api,isCurrent=()=>true,interval=60000,compact=false}){
 let alive=true,timer=null,pending=false,authorized=false;
 const current=()=>alive&&host.isConnected&&isCurrent();
 host.hidden=true;host.classList.add('request-notifications');host.setAttribute('aria-label','업무 요청 답변 알림');
 function schedule(){clearTimeout(timer);if(current()&&!document.hidden)timer=setTimeout(refresh,interval);}
 async function refresh(){
  if(!current()||pending||document.hidden)return;pending=true;
  try{
   if(!authorized){const value=await api('/work-requests/availability');if(!current())return;if(!value.enabled){host.hidden=true;return;}authorized=true;}
   const value=await api('/work-requests/notifications');if(!current())return;
   if(!Number.isSafeInteger(value.unread_count)||value.unread_count<0||!Array.isArray(value.items))throw Error('답변 알림을 확인하지 못했습니다.');
   host.replaceChildren();host.hidden=value.unread_count===0;
   if(host.hidden)return;
   const title=el('strong','답변 완료 '+value.unread_count+'건'),list=el('ul');title.setAttribute('role','status');host.append(title);
   if(compact){const link=el('a','답변 보기');link.href='/workspace.html#requests';host.append(link);return;}host.append(list);
   for(const item of value.items){if(!/^[0-9a-f]{32}$/.test(item.id))throw Error('답변 알림을 확인하지 못했습니다.');const li=el('li'),link=el('a',item.title+(item.has_files?' · 파일 준비됨':''));link.href='/workspace.html#requests?request='+encodeURIComponent(item.id);li.append(link);list.append(li);}
   if(value.unread_count>value.items.length){const all=el('a','내 요청 전체 보기');all.href='/workspace.html#requests';host.append(all);}
  }catch{
   if(!current())return;host.hidden=false;host.replaceChildren(el('span','답변 알림을 확인하지 못했습니다.'));
   const retry=el('button','다시 확인');retry.type='button';retry.onclick=refresh;host.append(retry);
  }finally{pending=false;if(authorized)schedule();}
 }
 function resume(){if(!document.hidden)void refresh();else clearTimeout(timer);}
 document.addEventListener('visibilitychange',resume);window.addEventListener('focus',resume);window.addEventListener('pageshow',resume);window.addEventListener('besma-request-read',resume);
 const cleanup=()=>{alive=false;clearTimeout(timer);document.removeEventListener('visibilitychange',resume);window.removeEventListener('focus',resume);window.removeEventListener('pageshow',resume);window.removeEventListener('besma-request-read',resume);host.replaceChildren();host.hidden=true;};
 await refresh();return cleanup;
}
