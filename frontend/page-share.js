
const API='https://api.besma.co.kr';
const initialToken=localStorage.getItem('besma_token');
let CONTACTS=[], CONTACT_SOURCE='';
function clearAccess(message){CONTACTS=[];document.getElementById('list').replaceChildren();document.getElementById('contacts').hidden=true;document.getElementById('manual-number').value='';document.getElementById('toast').textContent='';document.getElementById('access-status').hidden=false;document.getElementById('access-status').textContent=message;}
function advance(button){const next=button.closest('tr')?.nextElementSibling;if(!next)return;let target=next.querySelector('.copy');if(!target){next.tabIndex=-1;target=next;}target.focus({preventScroll:true});next.scrollIntoView({block:'nearest'});}
async function load(){
 if(!initialToken||initialToken!==localStorage.getItem('besma_token')){clearAccess('BESMA에 로그인한 뒤 페이지공유를 열어 주세요.');return;}
 try{const response=await fetch(API+'/page-share/site-manager-contacts',{headers:{Authorization:'Bearer '+initialToken},cache:'no-store'});
 if(initialToken!==localStorage.getItem('besma_token'))return clearAccess('로그인이 변경되었습니다. 페이지를 다시 열어 주세요.');
 if(!response.ok){clearAccess(response.status===403?'안전보건실에서 이용할 수 있습니다.':response.status===401?'로그인이 만료되었습니다. BESMA에서 다시 로그인해 주세요.':'공유 페이지를 불러오지 못했습니다. 새로고침해 주세요.');return;}
 const data=await response.json();if(initialToken!==localStorage.getItem('besma_token'))return clearAccess('로그인이 변경되었습니다. 페이지를 다시 열어 주세요.');
 CONTACTS=data.contacts;CONTACT_SOURCE=data.source;render();document.getElementById('source').textContent=CONTACT_SOURCE;document.getElementById('access-status').hidden=true;document.getElementById('contacts').hidden=false;
 }catch{clearAccess('공유 페이지를 불러오지 못했습니다. 새로고침해 주세요.');}
}
window.addEventListener('storage',e=>{if(e.key==='besma_token')clearAccess('로그인이 변경되었습니다. 페이지를 다시 열어 주세요.');});
setInterval(()=>{if(localStorage.getItem('besma_token')!==initialToken)clearAccess('로그인이 변경되었습니다. 페이지를 다시 열어 주세요.');},1000);
window.addEventListener('pageshow',event=>{if(event.persisted)load();});

'use strict';
const search=document.getElementById('search'),list=document.getElementById('list'),count=document.getElementById('count'),toast=document.getElementById('toast');
let toastTimer;
function compact(value){return String(value).normalize('NFC').toLowerCase().replace(/[\s\-(),.]/g,'');}
function render(){
 const query=compact(search.value);
 const rows=CONTACTS.filter(row=>compact(row.site+' '+row.company+' '+(row.phone||'')).includes(query));
 count.replaceChildren();const strong=document.createElement('strong');strong.textContent=rows.length+'개 현장';count.append(strong,document.createTextNode(' / 전체 '+CONTACTS.length+'개'));
 list.replaceChildren();
 if(!rows.length){const row=list.insertRow();const cell=row.insertCell();cell.colSpan=3;cell.className='empty';cell.textContent='검색 결과가 없습니다.';return;}
 for(const row of rows){const tr=list.insertRow();tr.insertCell().textContent=row.id;const name=tr.insertCell();name.className='site-name';name.append(document.createTextNode(row.site));if(row.company){const sub=document.createElement('span');sub.className='company';sub.textContent=row.company;name.append(sub);}const cell=tr.insertCell();if(row.phone){const button=document.createElement('button');button.type='button';button.className='copy';button.setAttribute('aria-label',row.site+' 전화번호 '+row.phone+' 복사');const number=document.createElement('span');number.textContent=row.phone;const label=document.createElement('small');label.textContent='복사';button.append(number,label);button.addEventListener('click',()=>copyNumber(row,button,label));cell.append(button);}else{const missing=document.createElement('span');missing.className='missing';missing.textContent='전화번호 확인 필요';cell.append(missing);}}
}
async function copyNumber(row,button,label){
 let copied=false;
 try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(row.phone);copied=true;}}catch(_){}
 if(!copied){const field=document.createElement('textarea');field.value=row.phone;field.style.cssText='position:fixed;left:-9999px;top:0';document.body.append(field);field.select();try{copied=document.execCommand('copy');}catch(_){}field.remove();}
 if(copied){advance(button);button.classList.add('copied');label.textContent='복사됨';clearTimeout(toastTimer);toast.textContent=row.phone+' 복사했습니다';toastTimer=setTimeout(()=>toast.textContent='',2400);setTimeout(()=>{button.classList.remove('copied');label.textContent='복사';},1800);}
 else{document.getElementById('manual').hidden=false;const field=document.getElementById('manual-number');field.value=row.phone;field.focus();field.select();toast.textContent='자동 복사를 완료하지 못했습니다.';}
}

search.addEventListener('input',render);
document.getElementById('clear').addEventListener('click',()=>{search.value='';render();search.focus();});
load();
