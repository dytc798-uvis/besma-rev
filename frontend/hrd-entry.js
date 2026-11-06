const API='https://api.besma.co.kr';
const HRD='https://hrd-boohyun.kr';
const allowedRoles=new Set(['HQ_SAFE','HQ_SAFE_ADMIN','HQ_OTHER','SUPER_ADMIN','ACCIDENT_ADMIN','FUNCTIONAL_EVAL_VIEWER']);
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
const launch=(label,path,cls='hrd-action')=>{const a=el('a',label,cls);a.href=HRD+path;a.referrerPolicy='no-referrer';return a;};
const links=[];
let generation=0;
function clear(){generation++;for(const n of links.splice(0))n.remove();const host=document.getElementById('hrd-content');if(host){host.replaceChildren(el('p','로그인과 본사 이용 권한을 확인해 주세요.'));host.dataset.state='AUTH_REQUIRED';}}
function quickLinks(host){
 const nav=el('nav',null,'hrd-quick-links');nav.setAttribute('aria-label','현장 출퇴근·연장근무');
 const heading=el('strong','출퇴근·연장근무');
 const guide=el('a','사용 안내','hrd-guide-link');guide.href='/hrd.html';
 nav.append(heading,launch('현장 근무 신청','/hr/overtime'),launch('출근·퇴근 기록','/me/site-punch'),guide);
 host.append(nav);links.push(nav);
}
function instructions(host){
 host.replaceChildren();host.dataset.state='READY';
 const intro=el('p','본사 직원이 현장에서 근무하는 날 이용합니다.');
 const actions=el('nav',null,'hrd-main-actions');actions.setAttribute('aria-label','HRD 업무 열기');
 actions.append(launch('현장 근무 신청','/hr/overtime'),launch('출근·퇴근 기록','/me/site-punch'));
 host.append(intro,actions,el('p','HRD 개인 계정으로 로그인합니다. 이미 로그인한 브라우저에서는 기존 HRD 세션을 이용합니다.','hrd-session-note'));
 const steps=el('ol',null,'hrd-steps');
 for(const [title,text] of [
  ['현장 근무 신청','연장이 없으면 ‘현장 근무(연장 없음)’, 연장·야간·휴일 근무가 있으면 해당 구분과 ‘현장 출장’을 선택합니다. 주소 검색으로 현장 도로명 주소를 고릅니다.'],
  ['처음 한 번 위치정보 동의','HRD의 ‘내 업무 → 현장 출퇴근’에서 동의 내용을 확인합니다. 동의하지 않으면 담당자가 기존 방식으로 확인·입력합니다.'],
  ['현장에서 출근·퇴근 기록','버튼을 누를 때 위치 사용을 허용합니다. 출근은 근무 시작 4시간 전부터 종료 시각까지, 퇴근은 출근 기록 후부터 근무 종료 8시간 뒤까지 가능합니다.'],
  ['확인 필요 시 사진 첨부','현장 주소 300m 밖이거나 위치 확인이 안 되면 ‘사진 촬영·첨부’로 현장에서 바로 찍어 올립니다. 15분 이내 촬영한 사진을 기록당 한 번 첨부할 수 있습니다. 최종 승인자가 확인합니다.']
 ]){const li=el('li');li.append(el('h2',title),el('p',text));steps.append(li);}
 host.append(steps,el('p','위치는 출근·퇴근 버튼을 누르는 순간에만 확인합니다. 정상 또는 인정된 기록은 근무시간·시간외수당에 반영됩니다.','hrd-note'));
 const faq=el('details'),summary=el('summary','기록이 없거나 버튼을 누르지 못했나요?');
 faq.append(summary,el('p','신청이 임시저장 상태이거나 근무 장소가 본사이면 현장이 표시되지 않습니다. 제출 여부와 근무 장소를 확인하세요. 기록 오류나 누락은 날짜와 현장명을 적어 김명식 차장에게 문의하세요.'));
 host.append(faq);
}
async function start(){
 const mine=++generation,token=localStorage.getItem('besma_token'),host=document.getElementById('hrd-content');
 if(!token){clear();return;}
 try{
  const response=await fetch(API+'/auth/me',{headers:{Authorization:'Bearer '+token},cache:'no-store',credentials:'omit',redirect:'error'});
  if(!response.ok)throw Error('AUTH');
  const user=await response.json();
  if(mine!==generation||localStorage.getItem('besma_token')!==token)return;
  if(!allowedRoles.has(user.role)||user.ui_type==='SITE')throw Error('ROLE');
  if(host)instructions(host);
  else{
   const company=document.querySelector('.attendance-block');
   const workspace=document.querySelector('.topbar');
   if(company){const container=el('div',null,'hrd-dashboard-entry');company.after(container);links.push(container);quickLinks(container);}
   else if(workspace){const link=el('a','출퇴근·연장근무','hrd-workspace-link');link.href='/hrd.html';workspace.append(link);links.push(link);}
  }
 }catch{if(mine===generation)clear();}
}
addEventListener('storage',e=>{if(e.key==='besma_token'||e.key===null)clear();});
void start();
