import {workReturn} from '/assets/workspace-return.js';
const API='https://api.besma.co.kr';
function start(){
 if(location.pathname!=='/hq-safe/functional-eval')return;
 const q=new URLSearchParams(location.search);if(q.get('from_workspace')!=='1')return;
 const style=document.createElement('style');style.textContent=`
 .fe-site-modal.evaluation-context-dialog{box-sizing:border-box;background:#fff!important;color:#172d3a!important;padding:16px;width:min(1100px,calc(100vw - 24px));}
 .evaluation-context-dialog .fe-site-modal-table{width:100%;min-width:0;overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;}
 .evaluation-context-dialog table{min-width:640px;table-layout:auto!important;}
 .evaluation-context-dialog th,.evaluation-context-dialog td{white-space:nowrap;word-break:normal!important;}
 .evaluation-context-dialog .detail-head-text{min-width:0!important;}
 .evaluation-context-dialog .detail-head-text h2{word-break:keep-all;overflow-wrap:break-word;}
 .evaluation-context-dialog .detail-head-actions button{min-height:44px;}
 @media(max-width:640px){.evaluation-context-dialog .detail-head{display:flex!important;flex-direction:column!important;align-items:stretch!important;gap:12px;}.evaluation-context-dialog .detail-head-text{width:100%;flex:none!important;}.evaluation-context-dialog .detail-head-actions{position:static!important;justify-content:flex-start!important;flex-wrap:wrap;}.evaluation-context-dialog .detail-head-text h2{margin:0 0 8px;font-size:21px;line-height:1.4;}.evaluation-context-dialog .detail-head-text p{white-space:normal;word-break:keep-all;line-height:1.6;}}
 `;document.head.append(style);
 const session=localStorage.getItem('besma_token')||'',period=q.get('period_id'),site=q.get('site')||'',back=workReturn(q.get('return')||'/company.html');
 const valid=!!session&&/^[1-9]\d{0,14}$/.test(period||'')&&Number.isSafeInteger(Number(period))&&site.length>0&&site.length<=100&&!/[\/\\\u0000-\u001f\u007f]/.test(site)&&['period_id','site','return','from_workspace'].every(k=>q.getAll(k).length<=1);
 const origin=new URL(API),prefix=origin.pathname.replace(/\/$/,''),base=origin.origin,paths=/^\/functional-eval\/(?:period\/current|hq\/summary|hq\/grade-stats|hq\/sites\/[^/]+\/(?:evaluations|grade-stats))$/;
 let problem=valid?'':'평가의 현장·기간 조건을 확인해 주세요.',summarySeen=false,readOnly=true,active=false,opened=false,allClicked=false,warning='',started=Date.now(),queued=false;
 const own=()=>localStorage.getItem('besma_token')===session;
 function relative(value){try{const u=new URL(value,location.href);return u.origin===base&&u.pathname.startsWith(prefix+'/')?{u,path:u.pathname.slice(prefix.length)}:null;}catch{return null;}}
 function rewrite(value,method){const r=relative(value);if(!r||!r.path.startsWith('/functional-eval/'))return value;
  if((!valid||!own())&&!r.path.startsWith('/functional-eval/consent/')){problem='평가의 현장·기간 조건을 확인해 주세요.';schedule();throw Error('EVALUATION_CONTEXT_REQUIRED');}
  const write=!['GET','HEAD','OPTIONS'].includes((method||'GET').toUpperCase());
  if(write&&r.path!=='/functional-eval/consent/submit'&&(!valid||!own()||!summarySeen||readOnly)){warning='이전 평가는 조회 화면입니다. 평가·서명·결재를 변경하지 않았습니다.';schedule();throw Error('EVALUATION_HISTORY_READ_ONLY');}
  if(!write&&r.path.startsWith('/functional-eval/hq/export')&&summarySeen&&!active){warning='선택한 이전 평가의 출력 연결을 확인해야 합니다. 현재 평가 자료로 대체하지 않았습니다.';schedule();throw Error('EXACT_PERIOD_EXPORT_REQUIRED');}
  if(!write&&valid&&own()&&paths.test(r.path)){const existing=r.u.searchParams.getAll('period_id');if(existing.length>1||existing.length===1&&existing[0]!==period){problem='화면과 조회 요청의 평가기간이 다릅니다.';schedule();return value;}r.u.searchParams.set('period_id',period);return r.u.href;}
  return value;
 }
 function inspect(value,status,data){const r=relative(value);if(!r||!paths.test(r.path)||!own())return;if(status!==200){if(status>=400&&r.path.endsWith('/hq/summary')){problem='선택한 평가기간을 불러오지 못했습니다.';schedule();}return;}
  const p=r.path.endsWith('/period/current')?data:data?.period;if(p&&p.id!==Number(period)){problem='조회한 평가기간이 선택한 기간과 다릅니다.';schedule();return;}
  if(r.path.endsWith('/hq/summary')){if(!p||typeof p.is_closed!=='boolean'||typeof p.is_active!=='boolean'){problem='평가기간 상태를 확인해야 합니다.';}else{summarySeen=true;active=p.is_active;readOnly=p.is_closed||!p.is_active||p.evaluation_open!==true;}schedule();}
 }
 const originalFetch=window.fetch.bind(window);window.fetch=async function(input,options={}){const value=typeof input==='string'||input instanceof URL?String(input):input.url,method=options.method||(input instanceof Request?input.method:'GET'),target=rewrite(value,method);const response=await originalFetch(target===value?input:input instanceof Request?new Request(target,input):target,options);const r=relative(target);if(r&&paths.test(r.path))response.clone().json().then(data=>inspect(target,response.status,data)).catch(()=>{});return response;};
 const originalOpen=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(method,value,...rest){const target=rewrite(String(value),method),r=relative(target);if(r&&paths.test(r.path))this.addEventListener('load',()=>{try{const data=this.responseType==='json'?this.response:JSON.parse(this.responseText);inspect(target,this.status,data);}catch{}},{once:true});return originalOpen.call(this,method,target,...rest);};
 function nav(host){if(host.querySelector(':scope > .evaluation-work-entry'))return;const n=document.createElement('nav');n.className='document-work-entry evaluation-work-entry';const a=document.createElement('a');a.href=back;a.dataset.workflowReturn='true';a.textContent='← 이전 업무로';const text=document.createElement('p');text.dataset.evaluationContext='true';text.textContent='선택한 평가기간 · 현장 '+site;n.append(a,text);host.prepend(n);}
 function draw(){queued=false;const page=document.querySelector('.fe-hq-page');if(!page)return;nav(page);if(!own())problem='로그인 계정이 변경되었습니다. 이전 업무에서 다시 열어 주세요.';const message=problem||warning||(summarySeen?(readOnly?'이전 평가 조회 · ':'선택한 평가 · ')+'현장 '+site:'선택한 평가기간을 확인하고 있습니다.');for(const note of document.querySelectorAll('[data-evaluation-context]'))if(note.textContent!==message)note.textContent=message;
  if(problem){for(const container of [page,...document.querySelectorAll('.fe-site-modal')]){nav(container);for(const child of container.children)if(!child.classList.contains('evaluation-work-entry'))child.hidden=true;}return;}
  if(!summarySeen||opened)return;
  const dialog=document.querySelector('.fe-site-modal');if(dialog){opened=true;dialog.classList.add('evaluation-context-dialog');nav(dialog);function focus(root){for(const child of root.children){if(child===dialog||child.classList.contains('evaluation-work-entry'))continue;if(child.contains(dialog))focus(child);else child.hidden=true;}}focus(page);return;}
  const all=page.querySelector('.bucket-card--all');if(all&&!allClicked){allClicked=true;all.click();return;}
  const row=[...page.querySelectorAll('.site-list-item')].find(button=>button.querySelector('.site-list-item__meta')?.textContent.split('·')[0].trim()===site);if(row){row.click();return;}
  if(Date.now()-started>15000){problem='선택한 기간의 현장을 찾지 못했습니다. 대상 현장과 원장을 확인해 주세요.';schedule();}
 }
 function schedule(){if(!queued){queued=true;setTimeout(draw,100);}}
 new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true});addEventListener('storage',schedule);setInterval(schedule,1000);schedule();
}
start();
