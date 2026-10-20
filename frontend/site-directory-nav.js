// Keep the established HQ search URL; use a full navigation for the new authenticated view.
const path='/hq-safe/site-search';
document.addEventListener('click',event=>{const a=event.target.closest?.('a[href]');if(!a||event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;const url=new URL(a.href,location.origin);if(url.origin===location.origin&&url.pathname.replace(/\/$/,'')===path){event.preventDefault();event.stopImmediatePropagation();location.assign(url.href);}},true);
function check(){if(location.pathname.replace(/\/$/,'')===path)location.replace(location.href);}
new MutationObserver(check).observe(document.documentElement,{childList:true,subtree:true});check();
