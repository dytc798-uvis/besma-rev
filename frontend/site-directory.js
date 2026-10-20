const API='https://api.besma.co.kr';
const token=localStorage.getItem('besma_token');
const $=id=>document.getElementById(id);
let sites=[],favorites=new Set(),view='favorites',source={},noticeTimer;
const pending=new Set();
function session(){if(!token||localStorage.getItem('besma_token')!==token){const message=!token?'BESMA에 로그인한 뒤 현장검색을 열어 주세요.':'로그인이 변경되었습니다. 현장검색을 다시 열어 주세요.';clearAccess(message);throw Error(message);}}
function clearAccess(message){sites=[];favorites.clear();$('sites').replaceChildren();$('directory').hidden=true;$('access-status').hidden=false;$('access-status').textContent=message;$('notice').textContent='';}
async function api(path,options={}){
 session();const response=await fetch(API+'/site-directory'+path,{...options,cache:'no-store',headers:{Authorization:'Bearer '+token,...(options.body?{'Content-Type':'application/json'}:{})}});session();
 if(!response.ok){const message=response.status===403?'안전보건실에서 이용할 수 있습니다.':response.status===401?'로그인이 만료되었습니다. BESMA에서 다시 로그인해 주세요.':'현장 정보를 처리하지 못했습니다. 다시 시도해 주세요.';if(response.status===401||response.status===403)clearAccess(message);throw Error(message);}
 const value=await response.json();session();return value;
}
function node(tag,text,cls){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
function button(text,action,cls){const n=node('button',text,cls);n.type='button';n.addEventListener('click',event=>{try{const result=action(event);if(result?.catch)result.catch(error=>tell(error.message));}catch(error){tell(error.message);}});return n;}
function tell(message){clearTimeout(noticeTimer);$('notice').textContent=message;noticeTimer=setTimeout(()=>$('notice').textContent='',2200);}
function normalized(value){return String(value||'').normalize('NFKC').toLowerCase().replace(/[\[\](){}.,/\\:_-]+/g,' ').replace(/\s+/g,' ').trim();}
function compact(value){return normalized(value).replace(/\s/g,'');}
function bigrams(value){const c=value.replace(/\s/g,'');return new Set(c.length<2?(c?[c]:[]):Array.from({length:c.length-1},(_,i)=>c.slice(i,i+2)));}
function similarity(a,b){const x=bigrams(a),y=bigrams(b);if(!x.size||!y.size)return 0;let common=0;for(const p of x)if(y.has(p))common++;return 2*common/(x.size+y.size);}
function match(site,raw){
 const q=normalized(raw),name=normalized(site.name),address=normalized(site.address),code=normalized(site.code);if(!q)return 0;
 const people=normalized(site.contacts.map(x=>x.name+' '+x.label+' '+x.phone).join(' '));
 const digits=raw.replace(/\D/g,'');if(digits&&/^[-\d\s()+]+$/.test(raw)&&site.contacts.some(x=>x.phone.replace(/\D/g,'').includes(digits)))return 990;
 if(name===q)return 1000;if(code===q)return 980;if(name.startsWith(q))return 920;if(name.includes(q))return 880;if(address.includes(q))return 840;if(code.includes(q))return 820;if(people.includes(q))return 810;
 const words=q.split(' ').filter(Boolean);const coverage=text=>words.filter(w=>text.includes(w)).length/words.length;
 if(coverage(name)===1)return 780;if(coverage(address)===1)return 740;if(coverage(people)===1)return 720;
 return Math.round(Math.max(similarity(q,name)*600,similarity(q,address)*520,coverage(name)*560,coverage(address)*480));
}
function baseAddress(value){return String(value||'').replace(/[,，]?\s*(?:제?\s*)?\d{1,4}\s*동(?:\s*(?:제?\s*)?\d{1,5}\s*호)?(?:\s.*)?$/u,'').replace(/[,，]?\s*(?:제?\s*)?\d{1,5}\s*호(?:\s.*)?$/u,'').replace(/[,，]?\s*(?:지하|지상)?\s*\d{1,3}\s*층(?:\s.*)?$/u,'').trim();}
async function copy(value,trigger,advance=false){
 session();let done=false;
 try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);done=true;}}catch{}
 if(!done){const t=node('textarea');t.value=value;t.style.cssText='position:fixed;left:-9999px;top:0';document.body.append(t);t.select();try{done=document.execCommand('copy');}catch{}t.remove();}
 if(!done){trigger.focus();tell('자동 복사를 완료하지 못했습니다.');return;}
 session();trigger.textContent='복사됨';trigger.classList.add('copied');tell('복사했습니다.');
 if(advance){const next=trigger.closest('.site-card')?.nextElementSibling;if(next){let target=next.querySelector('.copy-phone');if(!target){next.tabIndex=-1;target=next;}target.focus({preventScroll:true});next.scrollIntoView({block:'nearest'});}}
 setTimeout(()=>{trigger.textContent=advance?'복사':'주소 복사';trigger.classList.remove('copied');},1600);
}
function directions(site){
 if(Number.isFinite(site.latitude)&&Number.isFinite(site.longitude)){
  const p=new URLSearchParams({dlat:String(site.latitude),dlng:String(site.longitude),dname:site.address||site.name,appname:location.origin});
  const uri='nmap://route/car?'+p.toString();if(/Android|iPhone|iPad|iPod/i.test(navigator.userAgent))location.href=uri;else window.open(uri,'_blank','noopener');
 }else window.open('https://map.naver.com/v5/search/'+encodeURIComponent(site.address||site.name),'_blank','noopener');
}
async function toggle(site,star){
 if(pending.has(site.code))return;pending.add(site.code);star.disabled=true;
 try{const data=await api('/favorites/'+encodeURIComponent(site.code),{method:'PUT',body:JSON.stringify({favorite:!favorites.has(site.code)})});favorites=new Set(data.favorite_codes);tell(favorites.has(site.code)?'즐겨찾기에 저장했습니다.':'즐겨찾기에서 해제했습니다.');render();}
 catch(error){tell(error.message);star.disabled=false;}finally{pending.delete(site.code);}
}
function addDetail(dl,key,label,value){const row=node('div');row.dataset.detailKey=key;row.append(node('dt',label),node('dd',value));dl.append(row);}
function siteCard(site){
 const card=node('article',null,'site-card');card.dataset.code=site.code;
 const heading=node('div',null,'site-heading');const h=node('h2',site.name);const star=button(favorites.has(site.code)?'★':'☆',()=>toggle(site,star),'star');star.setAttribute('aria-label',site.name+' 즐겨찾기 '+(favorites.has(site.code)?'해제':'추가'));star.setAttribute('aria-pressed',String(favorites.has(site.code)));heading.append(h,star);card.append(heading,node('span',site.code,'code'),node('p',baseAddress(site.address)||'주소 미등록','address'));
 const contacts=node('div',null,'contacts');
 for(const person of site.contacts){const row=node('div',null,'contact'),label=node('div',person.label,'person');if(!person.rank_confirmed)label.append(node('span','직급 미등록','unknown'));const actions=node('div',null,'phone-actions'),phone=node('a',person.phone,'phone');phone.href='tel:'+person.phone.replace(/\D/g,'');phone.setAttribute('aria-label',person.label+' '+person.phone+' 전화 걸기');const cp=button('복사',()=>copy(person.phone,cp,true),'copy copy-phone');cp.setAttribute('aria-label',person.label+' 전화번호 복사');actions.append(phone,cp);row.append(label,actions);contacts.append(row);}
 if(!site.contacts.length)contacts.append(node('p','등록된 담당자 연락처가 없습니다.','no-contact'));card.append(contacts);
 const actions=node('div',null,'site-actions');const map=button('네이버지도',()=>directions(site));map.disabled=!site.address&&!(Number.isFinite(site.latitude)&&Number.isFinite(site.longitude));const address=button('주소 복사',()=>copy(baseAddress(site.address),address));address.disabled=!baseAddress(site.address);actions.append(map,address);card.append(actions);
 const details=node('details'),summary=node('summary','상세'),dl=node('dl');details.append(summary,dl);
 addDetail(dl,'code','현장코드',site.code);addDetail(dl,'address','전체 주소',site.address||'미등록');
 const fields=[...site.details];for(const [key,label]of [['amount','공사금액'],['period','공사기간']])if(!fields.some(x=>x.key===key))fields.unshift({key,label,value:'미등록'});
 for(const field of fields){let text=field.value;if(field.key==='amount'&&text!=='미등록'&&Number.isFinite(Number(text)))text=Number(text).toLocaleString('ko-KR');addDetail(dl,field.key,field.label,text+(field.unit?' '+field.unit:''));}
 card.append(details);return card;
}
function render(){
 const q=$('search').value.trim();let visible;
 if(view==='search')visible=q?sites.map(s=>({site:s,score:match(s,q)})).filter(x=>x.score>=180).sort((a,b)=>b.score-a.score||a.site.name.localeCompare(b.site.name,'ko')).map(x=>x.site):[];
 else if(view==='all')visible=[...sites].sort((a,b)=>a.name.localeCompare(b.name,'ko'));
 else visible=sites.filter(s=>favorites.has(s.code)).sort((a,b)=>a.name.localeCompare(b.name,'ko'));
 $('favorites-view').setAttribute('aria-pressed',String(view==='favorites'));$('all-view').setAttribute('aria-pressed',String(view==='all'));
 $('count').textContent=(view==='favorites'?'즐겨찾기 ':view==='search'?'검색 ':'전체 ')+visible.length+'개 / 전체 '+sites.length+'개';
 $('sites').replaceChildren(...visible.map(siteCard));$('empty').hidden=visible.length>0;
 $('empty').textContent=view==='favorites'?'검색 후 별표를 누르면 즐겨찾는 현장이 여기에 표시됩니다.':view==='search'&&!q?'현장 이름 한 글자부터 검색할 수 있습니다.':'일치하는 현장이 없습니다.';
}
function show(viewName){view=viewName;$('search').value='';render();}
$('search').addEventListener('focus',()=>{view='search';$('search').value='';render();});
$('search').addEventListener('input',()=>{view='search';render();});
$('search').addEventListener('keydown',e=>{if(e.key==='Escape'){show('favorites');$('search').blur();}});
$('clear').addEventListener('click',()=>{view='search';$('search').value='';$('search').focus();render();});
$('favorites-view').addEventListener('click',()=>show('favorites'));$('all-view').addEventListener('click',()=>show('all'));
async function load(){try{const data=await api('');sites=data.sites;favorites=new Set(data.favorite_codes);source=data.source||{};$('source').textContent='현장·연락처 '+(source.contacts_as_of||'')+' 기준 · 공사 상세 '+(source.details_as_of||'')+' 자료 및 BESMA 등록정보';$('access-status').hidden=true;$('directory').hidden=false;render();}catch(error){if(sites.length===0)clearAccess(error.message);}}
window.addEventListener('storage',e=>{if(e.key==='besma_token')clearAccess('로그인이 변경되었습니다. 현장검색을 다시 열어 주세요.');});
setInterval(()=>{if(localStorage.getItem('besma_token')!==token)clearAccess('로그인이 변경되었습니다. 현장검색을 다시 열어 주세요.');},1000);
window.addEventListener('pageshow',e=>{if(e.persisted)load();});load();
