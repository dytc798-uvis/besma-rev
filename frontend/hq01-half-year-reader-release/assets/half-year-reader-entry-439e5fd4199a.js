const token=localStorage.getItem('besma_token');
if(token){
  fetch('https://api.besma.co.kr/safety-features/half-year-reader/capabilities',{cache:'no-store',headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(8000)})
  .then(async response=>{if(!response.ok)return;const capability=await response.json();if(localStorage.getItem('besma_token')!==token||capability.headquarters_reader!==true||capability.can_write!==false)return;
    const target=url=>'/half-year-reader.html'+url.search;
    if(location.pathname==='/inspection-plan.html'){location.replace(target(new URL(location.href)));return;}
    document.addEventListener('click',event=>{if(localStorage.getItem('besma_token')!==token||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;const link=event.target.closest?.('a[href]');if(!link)return;const url=new URL(link.href,location.href);if(url.origin!==location.origin||url.pathname!=='/inspection-plan.html')return;event.preventDefault();event.stopImmediatePropagation();location.assign(target(url));},true);
  }).catch(()=>{});
}
