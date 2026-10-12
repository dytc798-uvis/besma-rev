const API='https://api.besma.co.kr', root=document.querySelector('#app'),mode=document.body.dataset.mode;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const btn=(text,run)=>{const b=el('button',text);b.type='button';b.onclick=run;return b;};
let session=localStorage.getItem('besma_token')||'',ctx=null,activeThread=0,threadGeneration=0,lastMessage=0,threadBox=null,threadInfo=null,invitationData=null;
const sites=[['24028',74,'강원권 국도터널'],['25037',78,'남양주왕숙 A-24BL'],['25040',76,'강진~광주'],['25059',77,'군포대야미 A-2BL']];
const stateLabel=s=>({DRAFT:'작성 중',SUBMITTED:'제출완료',UNDER_REVIEW:'검토 중',IN_REVIEW:'검토 중',APPROVED:'승인',REJECTED:'반려',RESUBMITTED:'재제출',RECEIVED:'접수',REVIEWING:'검토 중',ACTION_IN_PROGRESS:'조치 중',DONE:'완료',CLOSED:'완료',ACTIVE:'미사용',USED:'가입 완료',EXPIRED:'만료'})[s]||s;
let selectedSite=sites.find(s=>location.hash==='#site-'+s[0])?.[1]||74;
function notice(text){document.querySelector('#status').textContent=text;}
async function api(path,options={},publicCall=false){
 const token=localStorage.getItem('besma_token')||'';
 if(!publicCall&&!token)throw Error('로그인이 필요합니다.');
 const r=await fetch(API+path,{cache:'no-store',...options,headers:{...(!publicCall?{Authorization:'Bearer '+token}:{}),...options.headers}});
 if(!publicCall&&token!==(localStorage.getItem('besma_token')||''))throw Error('로그인 계정이 변경됐습니다.');
 if(!r.ok){let message='요청을 처리하지 못했습니다. ('+r.status+')';try{const p=await r.json();if(typeof p.detail==='string')message=p.detail;}catch{}throw Error(message);}
 return r;
}
const get=async p=>(await api(p)).json();
const post=async(p,data,publicCall=false)=>(await api(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)},publicCall)).json();
function shell(title){root.replaceChildren();const h=el('header');h.append(el('h1',title));root.append(h,el('p','','status'));root.querySelector('.status').id='status';}
function field(form,label,key,value='',type='text'){const wrapper=el('label',label),input=el('input');input.name=key;input.type=type;input.value=value;input.required=true;input.autocomplete=type==='password'?'new-password':'off';wrapper.append(input);form.append(wrapper);return input;}
function loginLink(){const a=el('a','BESMA 로그인');a.href='/login';root.append(el('p','BESMA에 로그인한 뒤 이 페이지를 다시 열어 주세요.'),a);}
function recovery(){const box=el('details'),summary=el('summary','아이디·비밀번호를 잊었거나 링크를 다시 받아야 하나요?');box.append(summary);const f=el('form'),select=el('select');select.name='site_code';for(const [code,,name] of sites){const o=el('option',name);o.value=code;select.append(o);}const label=el('label','현장');label.append(select);f.append(label);field(f,'이름','name');field(f,'이메일주소','email','','email');const send=el('button','관리자에게 재설정 요청');send.type='submit';f.append(send);f.onsubmit=async e=>{e.preventDefault();send.disabled=true;try{const p=await post('/site-invitations/reset-request',Object.fromEntries(new FormData(f)),true);notice(p.message);f.reset();}catch(e){notice(e.message);}finally{send.disabled=false;}};box.append(f);root.append(box);}
async function signup(){
 shell('BESMA 현장 계정 설정');let token=new URLSearchParams(location.hash.slice(1)).get('invite')||'';
 history.replaceState(null,'',location.pathname);recovery();
 try{
  const p=await post('/site-invitations/inspect',{token},true);root.querySelector('h1').textContent=p.purpose==='RESET'?'BESMA 계정 재설정':'BESMA 현장 계정 설정';
  const panel=el('section');panel.append(el('h2',p.site_name),el('p','본인이 사용할 아이디와 비밀번호를 정해 주세요. 현장과 접근 권한은 이 링크에 지정되어 있습니다.'));
  const form=el('form');field(form,'이름','name',p.name);field(form,'직책','job_title',p.job_title);const email=field(form,'이메일주소','email',p.email,'email');
  const id=field(form,'아이디 · 본인이 정하는 값','login_id',p.suggested_login_id);id.minLength=3;id.maxLength=50;
  const suggestion=el('p','추천: '+p.suggested_login_id+' · 추천값을 자유롭게 수정하거나 새 아이디를 입력할 수 있습니다.','hint');form.append(suggestion);
  const aliases={'24028':'gangwon-tunnel','25037':'namyangju-wangsuk','25040':'gangjin-gwangju','25059':'gunpo-daeyami'};
  form.append(btn('추천 아이디 넣기',()=>{const prefix=email.value.trim().split('@')[0].toLowerCase();id.value=/^[a-z0-9][a-z0-9._-]{2,49}$/.test(prefix)?prefix:aliases[p.site_code];suggestion.textContent='추천 아이디도 직접 수정할 수 있습니다. 중복 여부는 저장할 때 확인합니다.';}));
  const password=field(form,'비밀번호 · 4자 이상','password','','password'),confirm=field(form,'비밀번호 확인','password_confirm','','password');password.minLength=4;confirm.minLength=4;password.maxLength=128;confirm.maxLength=128;
  const submit=el('button','계정 설정 완료');submit.type='submit';form.append(submit);panel.append(form);root.insertBefore(panel,root.querySelector('details'));
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;notice('계정 설정을 저장하고 있습니다.');try{const data=Object.fromEntries(new FormData(form));const result=await post('/site-invitations/accept',{token,...data},true);token='';password.value='';confirm.value='';panel.replaceChildren(el('h2','계정 설정 완료'),el('p',result.site_name),el('strong','아이디: '+result.login_id),el('p',result.message));const a=el('a','정한 아이디로 로그인');a.href='/site-workspace.html';panel.append(a);notice('');}catch(e){notice(e.message);}finally{submit.disabled=false;}};
 }catch(e){notice(e.message);}
}
async function signIn(){
 const form=el('form');field(form,'아이디','username');const p=field(form,'비밀번호','password','','password');p.autocomplete='current-password';const go=el('button','로그인');go.type='submit';form.append(go);root.append(form);recovery();
 form.onsubmit=async e=>{e.preventDefault();go.disabled=true;try{const r=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(form)),cache:'no-store'});if(!r.ok)throw Error('아이디 또는 비밀번호를 확인해 주세요.');const data=await r.json();if(data.must_change_password){location.href='/login';return;}localStorage.setItem('besma_token',data.access_token);p.value='';location.reload();}catch(e){notice(e.message);}finally{go.disabled=false;}};
}
async function documents(section){
 try{const p=await get('/site-invitations/documents');section.replaceChildren(el('h2','내 현장문서 게시판'));const list=el('div','', 'rows');section.append(list);
  if(!p.items.length)list.append(el('p','등록된 문서가 없습니다.'));
  for(const d of p.items){const row=el('article');row.append(el('strong',d.title),el('small',[d.date,stateLabel(d.status)].filter(Boolean).join(' · ')));if(d.has_file)row.append(btn('파일 받기',async()=>{try{const r=await api('/site-invitations/documents/'+d.id+'/content');const url=URL.createObjectURL(await r.blob()),a=el('a');a.href=url;a.download=(d.file_name||d.title).replace(/[\\/]/g,'_');a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){notice(e.message);}}));list.append(row);}
 }catch(e){section.append(el('p',e.message));}
}
async function ideas(section){try{const p=await get('/site-invitations/ideas');section.replaceChildren(el('h2','운영아이디어 제안 게시판'));if(!p.items.length)section.append(el('p','등록된 제안이 없습니다.'));for(const i of p.items){const a=el('article');a.append(el('strong',i.category+' · '+stateLabel(i.status)),el('p',i.content),el('small',i.reporter));if(i.action_result)a.append(el('p','조치: '+i.action_result));section.append(a);}}catch(e){section.append(el('p',e.message));}}
let threadList=null,conversation=null,replyInput=null;
async function loadThreads(){if(!threadList)return;try{const q=ctx.owner?'?site_id='+selectedSite:'';const p=await get('/site-invitations/threads'+q);threadList.replaceChildren();if(!p.items.length)threadList.append(el('p','등록된 소통 글이 없습니다.'));for(const t of p.items){const b=btn(t.title+' · '+t.message_count+'개 메시지'+(t.unread_count?' · 새 메시지 '+t.unread_count:''),()=>openThread(t.id));b.className=t.unread_count?'thread unread':'thread';threadList.append(b);}}catch(e){notice(e.message);}}
async function refreshThread(){
 if(!activeThread)return;const id=activeThread,g=threadGeneration;
 try{const p=await get('/site-invitations/threads/'+id);if(g!==threadGeneration||id!==activeThread)return;threadInfo=p;conversation.querySelector('h3').textContent=p.site_name+' · '+p.title;
  if(ctx.owner&&selectedSite!==p.site_id){selectedSite=p.site_id;document.querySelector('#owner-site').value=selectedSite;loadOwner();loadThreads();}
  for(const m of p.items.filter(m=>m.id>lastMessage)){const a=el('article','',m.side===p.side?'message own':'message');a.append(el('strong',m.sender+' · '+(m.side==='HQ'?'본사':'현장')),el('p',m.body),el('small',new Date(m.created_at.endsWith('Z')?m.created_at:m.created_at+'Z').toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})));threadBox.append(a);lastMessage=m.id;}
  if(lastMessage)await post('/site-invitations/threads/'+id+'/read',{through_id:lastMessage});
 }catch(e){notice(e.message);}
}
async function openThread(id){activeThread=id;threadGeneration++;lastMessage=0;location.hash='thread-'+id;conversation.replaceChildren(el('h3','대화를 불러오는 중입니다.'));threadBox=el('div','','messages');conversation.append(threadBox);const f=el('form');replyInput=el('textarea');replyInput.required=true;replyInput.maxLength=4000;replyInput.rows=3;replyInput.setAttribute('aria-label','답글');replyInput.placeholder='이 글에 대한 답글을 입력하세요.';f.append(replyInput);const send=el('button','답글 등록');send.type='submit';f.append(send);f.onsubmit=async e=>{e.preventDefault();send.disabled=true;const current=activeThread;try{await post('/site-invitations/threads/'+current+'/reply',{body:replyInput.value});if(activeThread===current){replyInput.value='';await refreshThread();await loadThreads();}}catch(e){notice(e.message);}finally{send.disabled=false;}};conversation.append(f,btn('대화 새로고침',refreshThread));await refreshThread();conversation.scrollIntoView({behavior:'smooth',block:'start'});}
function communications(section){section.append(el('h2','소통게시판'));threadList=el('div','','threads');conversation=el('div','','conversation');section.append(threadList,btn('목록 새로고침',loadThreads));const details=el('details');details.append(el('summary','새 소통 글 작성'));const f=el('form');field(f,'제목','title');const text=el('textarea');text.required=true;text.name='body';text.rows=3;text.maxLength=4000;text.setAttribute('aria-label','새 글 내용');f.append(text);const submit=el('button','새 글 등록');submit.type='submit';f.append(submit);f.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{const p=Object.fromEntries(new FormData(f));if(ctx.owner)p.site_id=selectedSite;const r=await post('/site-invitations/threads',p);f.reset();details.open=false;await loadThreads();await openThread(r.thread_id);}catch(e){notice(e.message);}finally{submit.disabled=false;}};details.append(f);section.append(details,conversation);loadThreads();}
async function loadOwner(){
 const panel=document.querySelector('#invites');try{const p=await get('/site-invitations/owner');invitationData=p;panel.replaceChildren(el('h2','안전관리자 개인 가입 링크'));
  for(const i of p.invitations.filter(i=>sites.find(s=>s[1]===selectedSite)?.[0]===i.site_code&&i.state!=='REVOKED')){const card=el('article');card.append(el('strong',i.name+' · '+i.job_title),el('p',i.site_name),el('small',(i.email||'이메일은 본인 입력')+' · '+stateLabel(i.state)));
   if(i.url){card.append(btn('개인 가입 링크 복사',async()=>{try{await navigator.clipboard.writeText(i.url);notice(i.name+'님의 개인 링크를 복사했습니다.');}catch{const input=el('input');input.readOnly=true;input.value=i.url;card.append(input);input.select();notice('선택된 개인 링크를 복사해 주세요.');}}),el('small','유효기간: '+new Date(i.expires_at*1000).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})));}
   card.append(btn(i.state==='USED'?'본인 확인 후 재설정 링크 발급':'새 링크 발급',async()=>{if(!confirm(i.name+'님 본인을 확인했습니까? 새 링크를 발급하면 이전 링크는 사용할 수 없습니다.'))return;try{await post('/site-invitations/owner/renew',{id:i.id});await loadOwner();}catch(e){notice(e.message);}}));panel.append(card);
  }
  const r=el('section');r.append(el('h3','계정 재설정 요청'));for(const q of p.reset_requests)r.append(el('p',q.site_code+' · '+q.name+' · '+q.email));if(!p.reset_requests.length)r.append(el('p','접수된 요청이 없습니다.'));panel.append(r);
 }catch(e){notice(e.message);}
}
async function workspace(){
 shell(mode==='owner'?'현장 개인 가입 링크 · 소통':'내 현장 업무');
 if(!localStorage.getItem('besma_token')){if(mode==='owner')loginLink();else await signIn();return;}
 try{ctx=await get('/site-invitations/access');if(mode==='owner'&&!ctx.owner)throw Error('정상익 관리자만 사용할 수 있습니다.');if(mode!=='owner'&&!ctx.restricted){location.replace('/');return;}
  const header=root.querySelector('header');header.append(btn('로그아웃',()=>{localStorage.removeItem('besma_token');location.reload();}));
  if(ctx.owner){const selector=el('select');selector.id='owner-site';selector.setAttribute('aria-label','현장');for(const [,id,name] of sites){const o=el('option',name);o.value=id;selector.append(o);}selector.value=selectedSite;selector.onchange=()=>{selectedSite=Number(selector.value);location.hash='site-'+sites.find(s=>s[1]===selectedSite)[0];activeThread=0;threadGeneration++;conversation.replaceChildren();loadOwner();loadThreads();};header.append(selector);const invites=el('section');invites.id='invites';root.append(invites);await loadOwner();}
  else{header.append(el('p',ctx.site_name+' · '+ctx.name+' '+ctx.job_title));const docs=el('section');root.append(docs);await documents(docs);}
  const comm=el('section');root.append(comm);communications(comm);
  if(!ctx.owner){const opinions=el('section');root.append(opinions);await ideas(opinions);recovery();}
  const thread=location.hash.match(/^#thread-(\d+)$/);if(thread)await openThread(Number(thread[1]));else if(location.hash==='#communication')comm.scrollIntoView();
  setInterval(()=>{if(activeThread)refreshThread();loadThreads();},15000);
 }catch(e){notice(e.message);}
}
window.addEventListener('hashchange',()=>{if(mode==='setup'&&location.hash.startsWith('#invite=')){location.reload();return;}const site=sites.find(s=>location.hash==='#site-'+s[0]);if(ctx?.owner&&site&&site[1]!==selectedSite){selectedSite=site[1];document.querySelector('#owner-site').value=selectedSite;activeThread=0;threadGeneration++;conversation.replaceChildren();loadOwner();loadThreads();return;}const thread=location.hash.match(/^#thread-(\d+)$/);if(mode!=='setup'&&ctx&&thread&&Number(thread[1])!==activeThread)openThread(Number(thread[1]));});
if(mode==='setup')signup();else workspace();
