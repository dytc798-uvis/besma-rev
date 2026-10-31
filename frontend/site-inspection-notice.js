// Site identity and scope are derived by the existing API, never a URL parameter.
const token=localStorage.getItem('besma_token');let content=null,notice=null,valid=true;
const current=()=>valid&&localStorage.getItem('besma_token')===token;
function attach(){
  if(!current()||!content||!/^\/site(?:\/|$)/.test(location.pathname)){notice?.remove();return;}
  const host=document.querySelector('.layout-content');
  if(!host||notice?.isConnected)return;
  const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(new Date());
  const rows=content.error?[]:content.items.filter(r=>!r.archived&&['PLANNED','IN_PROGRESS'].includes(r.status)&&(r.due_date||r.scheduled_date)>=today);
  // A verified empty schedule does not need a banner on every work screen.
  if(!content.error&&!rows.length)return;
  notice=document.createElement('section');notice.className='site-inspection-notice';
  notice.style.cssText='margin:8px 12px;padding:10px 12px;border:1px solid #d7af59;border-radius:10px;background:#fff4d8;color:#40351d';
  notice.setAttribute('aria-label','안전보건실 점검예정');
  if(content.error){
    notice.setAttribute('role','status');notice.textContent='점검예정을 확인하지 못했습니다.';
  }else{
    const title=document.createElement('strong');title.textContent='안전보건실 점검예정';notice.append(title);
    for(const row of rows){
      const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('p');
      s.textContent=row.scheduled_date+(row.due_date?' ~ '+row.due_date:'')+' · '+row.owner_name;
      s.style.cssText='min-height:44px;display:list-item;align-content:center;cursor:pointer;overflow-wrap:anywhere';
      p.textContent=row.detail_text||row.title;p.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0 8px';
      d.append(s,p);notice.append(d);
    }
  }
  const heading=host.querySelector('.layout-header');if(heading)heading.after(notice);else host.prepend(notice);
}
if(token){fetch('https://api.besma.co.kr/workspace/my-site-inspections',{cache:'no-store',credentials:'omit',headers:{Authorization:'Bearer '+token}}).then(async r=>{if(!current())return;if(r.status===403)return;if(!r.ok)throw Error();content=await r.json();if(content.available!==true||!Array.isArray(content.items))throw Error();attach();}).catch(()=>{if(current()){content={error:true};attach();}});new MutationObserver(attach).observe(document.documentElement,{childList:true,subtree:true});}
addEventListener('storage',e=>{if(e.key==='besma_token'||e.key===null){valid=false;content=null;notice?.remove();}});
