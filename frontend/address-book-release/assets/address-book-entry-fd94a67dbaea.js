// Shared address book entry; contact access remains enforced by the server.
let scheduled=false;
function mount(){scheduled=false;if(!localStorage.getItem('besma_token'))return;const nav=document.getElementById('menus')||document.querySelector('aside nav');if(!nav||nav.querySelector('[data-besma-address-book]'))return;const a=document.createElement('a');a.dataset.besmaAddressBook='true';a.href='/address-book.html';a.textContent='주소록';a.setAttribute('aria-label','주소록 · 기관 및 안전관리 연락처');const sample=nav.querySelector('a');if(sample)a.className=sample.className;nav.append(a);}
const observer=new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(mount);}});observer.observe(document.body,{childList:true,subtree:true});mount();
