// A site link carries selection, never permission. Resolve it using the signed-in API.
const validCode=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,32}$/.test(value);
export function chatHref(code){return '/workspace.html#requests'+(validCode(code)?'?'+new URLSearchParams({site:code}):'');}
export function siteChatLink(site){const a=document.createElement('a');a.href=chatHref(site.code);a.textContent='채팅으로 문의';a.dataset.siteChat=site.code;a.setAttribute('aria-label',site.name+' 채팅으로 문의');return a;}
export function requestedSite(params,draft){if(params.has('site'))return params.getAll('site').length===1&&validCode(params.get('site'))?params.get('site'):'!INVALID';return validCode(draft?.siteCode)?draft.siteCode:null;}
export async function resolveChatSite(code,api){
 if(!validCode(code))throw Error('현장 연결을 확인하지 못했습니다.');
 const value=await api('/workspace/sites');if(!Array.isArray(value?.items))throw Error('현장 연결을 확인하지 못했습니다.');
 const rows=value.items.filter(s=>s.code===code&&typeof s.name==='string'&&s.name.trim());
 if(rows.length!==1)throw Error('이 계정에서 현장을 확인하지 못했습니다.');
 return {code,name:rows[0].name.replace(/[\u0000-\u001f\u007f]+/g,' ').trim().slice(0,180)};
}
export function withSiteContext(site,text){return site?'현장: '+site.name+'\n\n'+text:text;}
export function siteLookupText(site,text){return site?text.replace(/(?:이|해당|선택한|지금\s*보는)\s*현장(?:의|에서)?/g,site.name+' '):text;}
export function activeReplyDelay(items,{online=true,visible=true}={}){return !visible?30000:online&&items.some(x=>['QUEUED','RUNNING'].includes(x.status))?2000:10000;}
