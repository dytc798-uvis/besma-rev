const N=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
export async function mountWorkspaceSettings(host,{api,context,isCurrent}){
 let stopped=false;const current=()=>!stopped&&host.isConnected&&isCurrent();
 const root=N('section',null,'workspace-settings'),account=N('section',null,'panel'),status=N('p',null,'settings-status');status.setAttribute('role','status');
 account.append(N('h2','내 계정'));const change=N('a','비밀번호 변경','button');change.href='/change-password?redirect='+encodeURIComponent('/workspace.html#settings');account.append(change);
 const mapLabel=N('label','지도 앱'),map=N('select');map.setAttribute('aria-label','지도 앱');map.disabled=true;map.append(new Option('네이버지도','NAVER'),new Option('티맵','TMAP'));mapLabel.append(map);account.append(mapLabel,status);root.append(account);host.append(root);
 try{const me=await api('/auth/me');if(current()){map.value=me.map_preference==='TMAP'?'TMAP':'NAVER';map.disabled=false;}}catch{if(current())status.textContent='사용자 설정을 확인하지 못했습니다.';}
 map.onchange=async()=>{map.disabled=true;try{const value=await api('/users/me/map-preference',{method:'PATCH',body:JSON.stringify({map_preference:map.value})});if(current()){map.value=value.map_preference;status.textContent='지도 앱 설정을 저장했습니다.';}}catch(e){if(current())status.textContent=e.message;}finally{if(current())map.disabled=false;}};
 const existing=N('section',null,'panel');existing.append(N('h2','기존 설정'));
 const links=[];if(context.user.role==='SITE')links.push(['현장·사용자 정보','/site/info']);
 if(context.permissions?.manage_document_settings)links.push(['문서 항목·주기 설정','/hq-safe/settings'],['고객사별 문서 묶음 설정','/hq-safe/contractor-document-settings']);
 if(context.permissions?.manage_government_forms)links.push(['문서·공개 설정','#settings/documents']);
 if(context.permissions?.worker_voice_ledger)links.push(['이전 의견 관리대장 보기',context.user.role==='SITE'?'/site/worker-voice':'/hq-safe/worker-voice']);
 if(!links.length)existing.append(N('p','추가 설정 권한이 없습니다.'));else for(const[label,href]of links){const a=N('a',label,'button');a.href=href;existing.append(a);}root.append(existing);
 const survey=N('section',null,'panel'),open=N('button','의견 작성 화면보기'),preview=N('section',null,'survey-preview');open.type='button';preview.hidden=true;preview.setAttribute('aria-label','근로자 의견 작성 화면 미리보기');open.setAttribute('aria-expanded','false');survey.append(N('h2','근로자의견청취'),N('p','근로자가 보는 설문을 확인합니다. 미리보기에서는 의견이 제출되지 않습니다.'),open,preview);root.append(survey);
 let loaded=false;
 open.onclick=async()=>{if(!current())return;if(loaded){preview.hidden=!preview.hidden;open.setAttribute('aria-expanded',String(!preview.hidden));return;}open.disabled=true;
  try{const response=await fetch('/workspace-assets/worker-voice-form.json',{cache:'no-store'});if(!response.ok)throw Error();const value=await response.json();if(!current())return;if(!value.title||!Array.isArray(value.questions)||!value.questions.length)throw Error();preview.replaceChildren(N('h3',value.title));if(value.description)preview.append(N('p',value.description));
   const fields=N('fieldset');fields.disabled=true;
   for(const[index,q]of value.questions.entries()){const block=N('div',null,'survey-question');if(q.type===6){block.append(N('p',q.title,'survey-introduction'));fields.append(block);continue;}
    const title=N('label',q.title+(q.required?' *':''));title.htmlFor='survey-preview-'+index;block.append(title);if(q.help)block.append(N('p',q.help,'survey-help'));
    if(q.options?.length){const choices=N('div');choices.id=title.htmlFor;for(const option of q.options){const row=N('label',null,'survey-choice'),input=N('input');input.type='radio';input.name='preview-question-'+index;row.append(input,N('span',option));choices.append(row);}block.append(choices);}
    else{const input=N(q.type===1?'textarea':'input');input.id=title.htmlFor;if(q.type===1)input.rows=4;else input.type='text';input.placeholder='근로자 입력란';block.append(input);}fields.append(block);
   }
   const submit=N('button','제출');submit.type='button';submit.disabled=true;fields.append(submit);preview.append(fields,N('p','Google 설문 편집 계정이 연결되지 않아 여기서는 설문을 수정할 수 없습니다.','survey-edit-status'));
   loaded=true;preview.hidden=false;open.setAttribute('aria-expanded','true');
  }catch{if(current())preview.replaceChildren(N('p','작성 화면을 확인하지 못했습니다. 다시 시도해 주세요.'));preview.hidden=false;}
  finally{if(current())open.disabled=false;}
 };
 return()=>{stopped=true;root.remove();};
}
