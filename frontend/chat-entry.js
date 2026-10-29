import {chatHref} from '/assets/chat-context.js';
const roles=new Set(['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','HQ_OTHER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE']);
export function showChatLauncher(context){
 document.getElementById('besma-chat-launcher')?.remove();
 if(!context?.user||!roles.has(context.user.role)||context.site||context.user.site_id!=null)return;
 const a=document.createElement('a');a.id='besma-chat-launcher';a.href='/workspace.html#requests';a.className='besma-chat-launcher';a.setAttribute('aria-label','베스마채팅 열기');a.title='베스마채팅';
 a.innerHTML='<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-3 3V11.5A8.5 8.5 0 0 1 9.5 3h2a8.5 8.5 0 0 1 8.5 8.5Z" transform="translate(1 -1) scale(.95)" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="8" cy="11" r="1" fill="currentColor"/><circle cx="12" cy="11" r="1" fill="currentColor"/><circle cx="16" cy="11" r="1" fill="currentColor"/></svg><span>베스마채팅</span>';
 a.addEventListener('click',()=>{a.href=chatHref(document.querySelector('#selected-site[data-site-code]')?.dataset.siteCode);});
 document.body.append(a);
}
addEventListener('storage',e=>{if(e.key==='besma_token'||e.key===null)document.getElementById('besma-chat-launcher')?.remove();});
