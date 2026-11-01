import {createSiteCorrectionEditor} from '/assets/site-corrections.js';

// The server authorizes the exact site and each field. This adapter keeps a
// failed edit inside its current screen instead of treating 403 as logout.
export function createHQSiteCorrectionEditor({site,role,token,onSaved,onNotice,isCurrent,open=false}){
 if(role!=='HQ_SAFE'||!token||!site?.code)return null;
 const valid=()=>isCurrent()&&localStorage.getItem('besma_token')===token;
 const base='/workspace/site-corrections/'+encodeURIComponent(site.code);
 async function request(path,options={}){
  const method=options.method||'GET',receipt=path.startsWith(base+'/receipts/')&&/^[0-9a-f]{32}$/.test(path.slice((base+'/receipts/').length));
  if(!valid()||!(path===base||receipt)||!['GET','PUT'].includes(method)||receipt&&method!=='GET')throw Error('현장 정보 연결을 다시 확인해 주세요.');
  const response=await fetch('https://api.besma.co.kr'+path,{method,body:options.body,signal:options.signal,credentials:'omit',redirect:'error',cache:'no-store',headers:{Authorization:'Bearer '+token,...(options.body?{'Content-Type':'application/json'}:{})}});
  if(!valid())throw new DOMException('화면이 바뀌었습니다.','AbortError');
  if(!response.ok){const messages={401:'로그인 상태를 확인해 주세요. 입력한 내용은 그대로 있습니다.',403:'이 현장의 수정 권한을 확인해 주세요. 입력한 내용은 그대로 있습니다.',404:'현장 정보 수정 연결을 확인해 주세요.',409:'다른 수정이나 원본 변경이 있습니다. 입력한 내용은 그대로 있습니다.',422:'주소·연락처와 직급을 확인해 주세요.'};throw Object.assign(Error(messages[response.status]||'현장 정보를 확인하지 못했습니다. 다시 시도해 주세요.'),{status:response.status});}
  return response.json();
 }
 return createSiteCorrectionEditor({site,request,onSaved,onNotice,isCurrent:valid,canEdit:true,open,fallback:()=>{const p=document.createElement('p');p.textContent='현장 정보 수정을 준비하고 있습니다. 새로고침 후 확인해 주세요.';return p;}});
}
