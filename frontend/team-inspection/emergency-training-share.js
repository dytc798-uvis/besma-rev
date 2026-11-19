import {mountTrainingMonitor} from './training-monitor.js';
const status=document.getElementById('share-status'),host=document.getElementById('share-host');
const token=new URLSearchParams(location.hash.slice(1)).get('share')||'';
if(!/^[A-Za-z0-9_-]{32,128}$/.test(token)){status.textContent='엑셀에 있는 바로가기를 다시 눌러 주세요.';}
else{
 const base='/safety-features/half-year-reviews/emergency-training';
 const api=async path=>{
  let target;
  if(path===base)target=base+'/shared';
  else if(path.startsWith(base+'/files/'))target=base+'/shared/files/'+path.slice((base+'/files/').length);
  else throw Error('조회 화면에서 제공하지 않는 기능입니다.');
  const response=await fetch('https://api.besma.co.kr'+target,{method:'GET',cache:'no-store',referrerPolicy:'no-referrer',headers:{Authorization:'TrainingShare '+token}});
  const value=await response.json();if(!response.ok)throw Error(value.detail||'조회 링크를 확인해 주세요.');return value;
 };
 status.textContent='비상훈련 현황과 수집자료를 조회할 수 있습니다.';
 const monitor=mountTrainingMonitor({api,session(){},host});
 if(new URLSearchParams(location.search).get('view')!=='emergency-training')document.getElementById('training-monitor-open')?.click();
 addEventListener('pagehide',()=>monitor.dispose(),{once:true});
}
