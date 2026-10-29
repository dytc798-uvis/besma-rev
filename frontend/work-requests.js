import {createNasSearchStatus} from '/assets/nas-search-status.js';
const labels={QUEUED:'접수 대기',RUNNING:'처리 중',AWAITING_REVIEW:'자료 확인 대기',AWAITING_RELEASE:'제공 확인 대기',COMPLETED:'답변 완료',DECLINED:'처리 안내',NEEDS_INFO:'추가 확인 필요',FAILED:'처리 오류',INTERRUPTED:'처리 중단',CANCELLED:'취소',ACCESS_REVOKED:'이용 권한 확인 필요'};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};

export async function mountWorkRequests(host,{api,download,isCurrent,initialDraft={},onDraft=()=>{}}){
 let alive=true,timer=null,loading=false,loadingHistory=false,sending=false,forceLatest=true,viewEpoch=0,reloadAgain=false,nasIndex=null,photoPreview=null;
 const viewport=window.visualViewport,fit=()=>host.style.setProperty('--chat-viewport-height',(viewport?.height||innerHeight)+'px');fit();viewport?.addEventListener('resize',fit);
 const current=()=>alive&&host.isConnected&&isCurrent(),cleanup=()=>{alive=false;clearTimeout(timer);nasIndex?.dispose();if(photoPreview)URL.revokeObjectURL(photoPreview);viewport?.removeEventListener('resize',fit);};
 host.classList.add('work-requests');
 const notice=node('p','이용 상태를 확인하고 있습니다.','request-notice');notice.setAttribute('role','status');const returnHome=node('a','← 대시보드','request-return');returnHome.href='/company.html';host.append(returnHome,notice);
 let availability;
 try{availability=await api('/work-requests/availability');}catch(e){if(current())notice.textContent=e.message;return cleanup;}
 if(!current())return cleanup;
 if(!availability.enabled){notice.textContent='베스마채팅 연결을 준비하고 있습니다.';return cleanup;}
 const validId=value=>/^[0-9a-f]{32}$/.test(value||'');
 const target=new URLSearchParams(location.hash.split('?')[1]||'').get('request');
 let conversationId=validId(target)?target:validId(initialDraft.conversationId)?initialDraft.conversationId:null;
 let newConversation=initialDraft.newConversation===true&&!validId(target),items=[],summaryCursor=null,turnCursor=null,rendered='',handledTarget=false;
 let requestKey=/^[a-zA-Z0-9_-]{8,80}$/.test(initialDraft.requestKey||'')?initialDraft.requestKey:crypto.randomUUID(),submittedContent=null;
 let nasSelection=initialDraft.nasSelection&&typeof initialDraft.nasSelection.nas_file_id==='string'?initialDraft.nasSelection:null;
 let inputAttachment=availability.input_images&&validId(initialDraft.inputAttachment?.id)?initialDraft.inputAttachment:null,uploading=false;
 let achievementDecision=null;
 const sourceKinds=['NAS','SOURCE_QUESTION','EDIT'],editable=item=>item&&['.txt','.docx'].includes(item.extension);
 const chat=node('section',null,'request-chat'),heading=node('div',null,'request-chat-heading'),caption=node('h2','베스마채팅'),fresh=node('button','새 대화'),refresh=node('button','새로고침'),headingActions=node('div');
 fresh.type=refresh.type='button';headingActions.append(fresh,refresh);
 const back=node('button','←','request-chat-back');back.type='button';back.setAttribute('aria-label','뒤로가기');back.title='뒤로가기';back.onclick=()=>{
  let destination='/company.html';try{const ref=new URL(document.referrer);if(ref.origin===location.origin&&ref.pathname!==location.pathname&&['/','/company.html','/workspace.html'].includes(ref.pathname))destination=ref.pathname+ref.search+ref.hash;}catch{}
  location.assign(destination);
 };heading.append(back,caption,headingActions);
 const log=node('div',null,'request-conversation'),previous=node('button','앞선 대화 보기'),messages=node('div',null,'request-messages');log.setAttribute('aria-label','현재 대화');previous.type='button';previous.hidden=true;log.append(previous,messages);
 const form=node('form',null,'request-form request-chat-composer'),bodyLabel=node('label','메시지'),body=node('textarea'),submit=node('button','보내기','primary'),status=node('p',null,'request-notice request-send-status');
 body.id='work-request-body';body.rows=3;body.maxLength=6000;body.required=true;bodyLabel.htmlFor=body.id;bodyLabel.className='request-visually-hidden';body.value=typeof initialDraft.body==='string'?initialDraft.body:'';body.placeholder='메시지를 입력하세요. Enter로 보내고 Shift+Enter로 줄을 바꿉니다.';
 const options=node('details',null,'request-options'),optionsTitle=node('summary','자료·요청 종류'),fields=node('div',null,'request-option-fields'),kindLabel=node('label','요청 종류'),kind=node('select');
 kind.id='work-request-kind';kindLabel.htmlFor=kind.id;
 const choices=[['QUESTION','질문'],['FILE','파일 작성 요청'],...(availability.nas_files?[['NAS','NAS 자료 받기'],['SOURCE_QUESTION','자료 내용 질문']]:[]),...(availability.source_edit?[['EDIT','문구 수정 사본']]:[])];
 if(sourceKinds.includes(initialDraft.kind)&&!choices.some(x=>x[0]===initialDraft.kind))choices.push([initialDraft.kind,'자료 요청 · 사용 중지']);
 for(const[value,label]of choices){const option=node('option',label);option.value=value;option.disabled=sourceKinds.includes(value)&&(!availability.nas_files||value==='EDIT'&&!availability.source_edit);kind.append(option);}kind.value=choices.some(x=>x[0]===initialDraft.kind)?initialDraft.kind:'QUESTION';
 const formatLabel=node('label','파일 형식'),format=node('select');format.id='work-request-format';formatLabel.htmlFor=format.id;for(const[value,label]of[['PDF','문서 PDF'],['TXT','텍스트 TXT']]){const option=node('option',label);option.value=value;format.append(option);}format.value=initialDraft.fileFormat==='TXT'?'TXT':'PDF';
 const nasBox=node('section',null,'request-nas'),queryLabel=node('label','NAS 파일명 또는 폴더명'),query=node('input'),find=node('button','자료 찾기'),found=node('div',null,'request-nas-results'),selected=node('p',null,'request-source');
 query.id='work-request-nas-query';query.maxLength=100;queryLabel.htmlFor=query.id;query.placeholder='예: 점검표 /지난자료';find.type='button';nasBox.append(queryLabel,query,find,found,node('small','문구 수정 사본은 TXT·DOCX를 지원합니다.'));
 fields.append(kindLabel,kind,formatLabel,format,nasBox);options.append(optionsTitle,fields);
 const channelLabel=node('label','입력 종류'),channel=node('select'),workDateLabel=node('label','실적 날짜'),workDate=node('input'),shared=node('small','실적은 본사 직원들에게 공유됩니다.');
 channel.id='work-request-channel';channel.setAttribute('aria-label','입력 종류');channelLabel.htmlFor=channel.id;channel.append(new Option('채팅','CHAT'),new Option('실적','WORK'));channel.value=initialDraft.channel==='WORK'?'WORK':'CHAT';
 workDate.type='date';workDate.id='work-request-date';workDateLabel.htmlFor=workDate.id;const today=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'});workDate.max=today;workDate.value=/^\d{4}-\d{2}-\d{2}$/.test(initialDraft.workDate||'')?initialDraft.workDate:today;workDateLabel.append(workDate);
 const channelTools=node('div',null,'request-channel');channelTools.append(channelLabel,channel,workDateLabel,shared);form.append(channelTools);
 const workConfirm=node('section',null,'request-work-confirm'),yes=node('button','예'),no=node('button','아니오');workConfirm.hidden=true;yes.type=no.type='button';workConfirm.setAttribute('aria-label','실적 등록 확인');workConfirm.append(node('strong','실적인가요?'),node('small','실적은 본사 직원들에게 공유됩니다.'),yes,no);form.append(workConfirm);
 yes.onclick=()=>{achievementDecision={text:body.value.trim(),work:true};workConfirm.hidden=true;form.requestSubmit();};no.onclick=()=>{achievementDecision={text:body.value.trim(),work:false};workConfirm.hidden=true;form.requestSubmit();};
 function channelState(){const work=channel.value==='WORK';workDateLabel.hidden=shared.hidden=!work;options.hidden=work;body.maxLength=work?2000:6000;submit.textContent=work?'실적 등록':'보내기';if(work){kind.value='QUESTION';nasSelection=null;selected.hidden=true;body.placeholder='이번 주 한 일을 적어 주세요. 예: 총신대 안전관리계획 지원 - 5팀';}else selectionText();achievementDecision=null;workConfirm.hidden=true;save();photoState();}
 channel.onchange=channelState;workDate.oninput=()=>save();body.addEventListener('input',()=>{achievementDecision=null;workConfirm.hidden=true;});
 status.setAttribute('role','status');submit.type='submit';const inputRow=node('div',null,'request-input-row'),bottom=node('div',null,'request-composer-actions');inputRow.append(body,submit);bottom.append(options);form.append(selected,bodyLabel,inputRow,bottom,status);
 chat.append(heading,log,form);host.append(chat);
 if(availability.nas_files){nasIndex=createNasSearchStatus({api,isCurrent:current});nasIndex.element.hidden=true;form.insertBefore(nasIndex.element,selected);}
 const discoveryChoices=node('section',null,'request-discovery');discoveryChoices.hidden=true;form.insertBefore(discoveryChoices,bodyLabel);
 const historyButton=node('button','이력'),historyPanel=node('section',null,'request-history'),historyList=node('div',null,'request-history-list'),historyMore=node('button','이력 더 보기');historyButton.type=historyMore.type='button';historyPanel.id='request-history';historyPanel.hidden=true;historyButton.setAttribute('aria-controls',historyPanel.id);historyButton.setAttribute('aria-expanded','false');historyMore.hidden=true;historyPanel.append(historyList,historyMore);host.append(historyButton,historyPanel);
 const photoInput=node('input'),photoButton=node('button','사진','request-photo-button'),photoBar=node('div',null,'request-photo-selection');photoInput.type='file';photoInput.accept='image/jpeg,image/png,image/webp';photoInput.hidden=true;photoButton.type='button';photoButton.setAttribute('aria-label','사진 첨부');photoButton.hidden=!availability.input_images;inputRow.prepend(photoButton,photoInput);form.insertBefore(photoBar,inputRow);
 const save=()=>onDraft({channel:channel.value,workDate:workDate.value,title:'',body:body.value,kind:kind.value,fileFormat:format.value,requestKey,nasSelection,inputAttachment,conversationId,newConversation});
 const draftKey=()=>JSON.stringify([channel.value,workDate.value,kind.value,body.value,format.value,nasSelection?.nas_file_id,inputAttachment?.id,conversationId]);
 function photoState(){photoBar.replaceChildren();photoBar.hidden=!inputAttachment;photoButton.disabled=uploading||sending||channel.value==='WORK';if(inputAttachment){const name=node('span',inputAttachment.filename),remove=node('button','첨부 취소');remove.type='button';remove.disabled=sending||uploading;remove.onclick=async()=>{if(sending||uploading||!current())return;try{await api('/work-requests/input-attachments/'+inputAttachment.id+'/remove',{method:'POST'});if(!current())return;inputAttachment=null;if(photoPreview){URL.revokeObjectURL(photoPreview);photoPreview=null;}photoState();selectionText();save();}catch(e){if(current())status.textContent=e.message;}};photoBar.append(name,remove);if(photoPreview){const img=node('img');img.src=photoPreview;img.alt='첨부할 사진';photoBar.append(img);}}body.required=kind.value!=='NAS'&&!inputAttachment;}
 photoButton.onclick=()=>photoInput.click();photoInput.onchange=async()=>{const file=photoInput.files?.[0];if(!file||sending||uploading||!current())return;if(file.size>8*1024*1024){status.textContent='사진은 8MB 이하로 첨부해 주세요.';photoInput.value='';return;}uploading=true;submit.disabled=true;photoButton.disabled=true;status.textContent='사진을 올리고 있습니다.';try{const data=new FormData();data.append('file',file);data.append('request_key','photo_'+crypto.randomUUID());const uploaded=await api('/work-requests/input-attachments',{method:'POST',body:data});if(!current())return;if(inputAttachment)await api('/work-requests/input-attachments/'+inputAttachment.id+'/remove',{method:'POST'});if(!current())return;inputAttachment=uploaded;if(photoPreview)URL.revokeObjectURL(photoPreview);photoPreview=URL.createObjectURL(file);nasSelection=null;kind.value='QUESTION';channel.value='CHAT';selectionText();save();status.textContent='사진을 첨부했습니다. 질문을 적고 보내기를 눌러 주세요.';}catch(e){if(current())status.textContent=e.message;}finally{uploading=false;photoInput.value='';if(current()){submit.disabled=sending;photoState();}}};photoState();
 for(const input of [kind,body,format])input.addEventListener('input',()=>{if(submittedContent!==null&&submittedContent!==draftKey()){requestKey=crypto.randomUUID();submittedContent=null;}save();});
 function selectionText(){if(nasIndex){nasIndex.element.hidden=!sourceKinds.includes(kind.value);if(!nasIndex.element.hidden)void nasIndex.refresh();}if(kind.value==='EDIT'&&!editable(nasSelection))nasSelection=null;nasBox.hidden=!sourceKinds.includes(kind.value);formatLabel.hidden=format.hidden=kind.value!=='FILE';body.required=kind.value!=='NAS'&&!inputAttachment;body.maxLength=kind.value==='FILE'&&format.value==='PDF'?5988:6000;selected.hidden=!sourceKinds.includes(kind.value);selected.textContent=nasSelection?'선택한 자료 · '+nasSelection.relative_path:'자료·요청 종류를 열어 파일을 선택해 주세요.';body.placeholder=kind.value==='EDIT'?'바꿀 문구와 새 문구를 적어 주세요.':kind.value==='NAS'?'파일과 함께 보낼 내용을 적을 수 있습니다.':'메시지를 입력하세요. Enter로 보내고 Shift+Enter로 줄을 바꿉니다.';}
 selectionText();if(sourceKinds.includes(kind.value))options.open=true;kind.onchange=()=>{selectionText();save();};format.onchange=()=>{selectionText();save();};
 async function searchNas(){if(find.disabled||sending||!current())return;find.disabled=true;found.replaceChildren(node('p','자료를 찾고 있습니다.'));
  try{const index=await nasIndex?.refresh();if(!current())return;if(index?.phase==='missing'){found.replaceChildren(node('p',nasIndex.emptyMessage('')));return;}const value=await api('/work-requests/nas/search',{method:'POST',body:JSON.stringify({q:query.value})});if(!current())return;const rows=value.items.filter(item=>kind.value!=='EDIT'||editable(item));found.replaceChildren();if(!rows.length)found.append(node('p',nasIndex?.emptyMessage('조건에 맞는 자료를 찾지 못했습니다. 검색어를 바꿔 확인해 주세요.')||'조건에 맞는 자료를 찾지 못했습니다.'));
   for(const item of rows){const row=node('div',null,'request-nas-result'),choose=node('button','이 자료 선택 · '+item.file_name);choose.type='button';choose.title=item.file_name;choose.onclick=()=>{if(sending||!current())return;nasSelection=item;requestKey=crypto.randomUUID();submittedContent=null;selectionText();save();options.open=false;body.focus();};row.append(choose,node('small',item.relative_path));found.append(row);}
  }catch(e){if(current())found.replaceChildren(node('p',e.message));}finally{if(current())find.disabled=false;}}
 find.onclick=searchNas;query.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();void searchNas();}};
 body.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();form.requestSubmit();}};
 const stamp=value=>new Date(value*1000).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'});
 async function markRead(item){if(!item.unread||!item.completion_token||item.source_access===false)return;
  try{await api('/work-requests/'+item.id+'/read',{method:'POST',body:JSON.stringify({completion_token:item.completion_token})});if(current()){item.unread=false;window.dispatchEvent(new Event('besma-request-read'));}}catch(e){if(current())status.textContent=e.message;}}
 function draw(){const keepBottom=forceLatest||log.scrollHeight-log.clientHeight-log.scrollTop<70;forceLatest=false;const signature=JSON.stringify(items);if(signature===rendered)return;rendered=signature;
  const prior=log.scrollTop;messages.replaceChildren();if(!items.length)messages.append(node('p','질문하거나 필요한 파일을 요청해 주세요.','request-chat-empty'));
  for(const item of items){const turn=node('article',null,'request-turn');turn.dataset.requestId=item.id;const user=node('div',null,'request-message request-message-user'),answer=node('div',null,'request-message request-message-answer');
   user.append(node('strong','나'),node('p',item.body,'request-body'),node('small',stamp(item.created_at),'request-time'));turn.append(user);
   for(const file of item.input_attachments||[]){const show=node('button','첨부 사진 보기 · '+file.filename,'request-file'),image=node('img',null,'request-input-photo');show.type='button';image.hidden=true;image.alt=file.filename;show.onclick=async()=>{show.disabled=true;try{const url=await download(item.id,{...file,input:true,preview:true});if(current()&&image.isConnected&&url){image.src=url;image.hidden=false;}}catch(e){if(current())status.textContent=e.message;}finally{if(current())show.disabled=false;}};user.append(show,image);}
   const state=item.review_phase==='DENIED'?'제공 안 함':labels[item.status]||'상태 확인 중';answer.append(node('strong','답변'),node('span',state,'request-badge'));
   if(item.reply)answer.append(node('p',item.reply,'request-body'));
   else if(item.status==='RUNNING')answer.append(node('p',item.processing_phase==='ERP_RECEIPT_CHECK'?'ERP 수신자료를 확인하고 있습니다.':item.processing_phase==='LARGE'?'자세히 검토하고 있습니다. 잠시 기다려 주세요.':item.processing_phase==='DOCUMENT_BUILDING'?'파일을 만들고 있습니다.':item.processing_phase==='SOURCE_READING'?'자료 내용을 확인하고 있습니다.':'답변을 준비하고 있습니다.','request-progress'));
   if(item.source&&item.source_access!==false)answer.append(node('p','출처 · '+item.source.label+' / '+item.source.relative_path,'request-source'));
   for(const file of item.files||[]){const get=node('button','파일 받기 · '+file.filename,'request-file');get.title=file.filename;get.type='button';get.onclick=async()=>{get.disabled=true;try{await download(item.id,file);if(current())status.textContent='파일을 받았습니다.';}catch(e){if(current())status.textContent=e.message;}finally{if(current())get.disabled=false;}};answer.append(get);}
   if(['QUEUED','RUNNING','INTERRUPTED','AWAITING_REVIEW','AWAITING_RELEASE'].includes(item.status)){const cancel=node('button','요청 취소');cancel.type='button';cancel.onclick=async()=>{cancel.disabled=true;try{await api('/work-requests/'+item.id+'/cancel',{method:'POST'});await reload();}catch(e){if(current())status.textContent=e.message;}finally{if(current())cancel.disabled=false;}};answer.append(cancel);}
   turn.append(answer);messages.append(turn);
  }
  previous.hidden=!turnCursor;requestAnimationFrame(()=>{if(!current())return;if(keepBottom)log.scrollTop=log.scrollHeight;else log.scrollTop=prior;
   const selected=validId(target)?items.find(x=>x.id===target):items.at(-1);if(selected?.status==='COMPLETED'&&(!handledTarget||selected.id===items.at(-1)?.id)){handledTarget=true;void markRead(selected);}
  });
 }
 async function showConversation(id){const epoch=++viewEpoch;const value=await api('/work-requests/conversations/'+id);if(!current()||epoch!==viewEpoch)return;conversationId=value.id;items=value.items;turnCursor=value.next_cursor;newConversation=false;forceLatest=true;caption.textContent=items[0]?.title||'대화';save();draw();}
 async function loadHistory(append=false){if(loadingHistory||!current())return;loadingHistory=true;historyMore.disabled=true;
  try{const value=await api('/work-requests/conversations'+(append&&summaryCursor?'?before='+summaryCursor:''));if(!current())return;if(!append)historyList.replaceChildren();summaryCursor=value.next_cursor;historyMore.hidden=!summaryCursor;
   if(!value.items.length&&!append)historyList.append(node('p','지난 대화가 없습니다.'));
   for(const item of value.items){const choose=node('button',item.title+' · '+stamp(item.latest_at));choose.type='button';choose.dataset.conversationId=item.id;choose.onclick=async()=>{if(sending)return;try{await showConversation(item.id);historyPanel.hidden=true;historyButton.setAttribute('aria-expanded','false');}catch(e){if(current())status.textContent=e.message;}};historyList.append(choose);}
   return value;
  }catch(e){if(current())status.textContent=e.message;}finally{loadingHistory=false;if(current())historyMore.disabled=false;}}
 historyButton.onclick=()=>{historyPanel.hidden=!historyPanel.hidden;historyButton.setAttribute('aria-expanded',String(!historyPanel.hidden));if(!historyPanel.hidden)void loadHistory();};historyMore.onclick=()=>loadHistory(true);
 previous.onclick=async()=>{if(!turnCursor||sending)return;previous.disabled=true;try{const value=await api('/work-requests/conversations/'+conversationId+'?before='+turnCursor);if(!current())return;const height=log.scrollHeight;items=[...value.items,...items];turnCursor=value.next_cursor;draw();requestAnimationFrame(()=>{if(current())log.scrollTop=log.scrollHeight-height;});}catch(e){if(current())status.textContent=e.message;}finally{if(current())previous.disabled=false;}};
 fresh.onclick=()=>{if(sending)return;++viewEpoch;conversationId=null;items=[];turnCursor=null;newConversation=true;rendered='';caption.textContent='새 대화';requestKey=crypto.randomUUID();save();draw();body.focus();};
 const ownerDetails=availability.scope_exempt?node('details',null,'request-owner-details'):null;let ownerRefresh=null;
 if(ownerDetails){ownerDetails.append(node('summary','받은 자료 확인'));const panel=node('section',null,'request-owner');ownerDetails.append(panel);host.append(ownerDetails);ownerRefresh=createOwnerInbox(panel,{api,download,current});ownerDetails.addEventListener('toggle',()=>{if(ownerDetails.open)void ownerRefresh();});}
 async function reload(){if(!current())return;if(loading){reloadAgain=true;return;}const epoch=viewEpoch;loading=true;refresh.disabled=true;clearTimeout(timer);
  try{const state=await api('/work-requests');if(!current()||epoch!==viewEpoch)return;notice.textContent=state.worker_online?'처리 PC가 연결되어 있습니다.':'처리 PC 연결을 기다리고 있습니다. 메시지는 보관됩니다.';
   if(conversationId){const value=await api('/work-requests/conversations/'+conversationId);if(!current()||epoch!==viewEpoch)return;conversationId=value.id;items=value.items;turnCursor=value.next_cursor;caption.textContent=items[0]?.title||'대화';save();draw();}
   else if(!newConversation){const value=await api('/work-requests/conversations');if(!current())return;if(value.items.length)await showConversation(value.items[0].id);else{newConversation=true;draw();}}
   else draw();
  }catch(e){if(current())notice.textContent=e.message;}finally{loading=false;if(current()){refresh.disabled=false;if(ownerDetails?.open)await ownerRefresh();if(reloadAgain){reloadAgain=false;queueMicrotask(reload);}else timer=setTimeout(reload,10000);}}}
 refresh.onclick=()=>reload();
 form.onsubmit=async event=>{event.preventDefault();if(sending||uploading||!current())return;const text=body.value.trim()||(inputAttachment?'첨부한 사진을 확인해 주세요.':kind.value==='NAS'?'선택한 NAS 원본 자료를 보내 주세요.':'');if(!text)return;if(inputAttachment&&(channel.value==='WORK'||kind.value!=='QUESTION')){status.textContent='첨부 사진은 채팅 질문으로 보내 주세요.';return;}
  const isWork=channel.value==='WORK'||achievementDecision?.text===text&&achievementDecision.work===true;
  if(!inputAttachment&&channel.value==='CHAT'&&kind.value==='QUESTION'&&achievementDecision?.text!==text&&!/[?？]|해\s*(?:줘|주세요)|찾아|알려|보내|부탁|가능|어떻게|언제|무엇|무슨|왜|몇|뭐|문의|요청/.test(text)&&/지원|완료|실시|작성|검토|협의|방문|교육|제출|참석|조치|회의|평가|점검|정리/.test(text)&&text.length<=500){workConfirm.hidden=false;status.textContent='실적이면 예, 질문이나 요청이면 아니오를 눌러 주세요.';yes.focus();return;}
  body.blur();sending=true;submit.disabled=true;for(const input of[channel,workDate,kind,body,format])input.disabled=true;submittedContent=draftKey();status.textContent='메시지를 보내고 있습니다.';save();
  try{
   if(isWork){
    if(text.length>2000)throw Error('실적은 2,000자 이내로 적어 주세요.');
    status.textContent='실적을 등록하고 있습니다.';
    const parent=items.at(-1)?.id;const receipt=await api('/weekly-work',{method:'POST',body:JSON.stringify({request_key:requestKey,text,work_date:workDate.value,...(parent?{parent_request_id:parent}:{})})});if(!current())return;
    body.value='';nasSelection=null;kind.value='QUESTION';selectionText();if(channel.value==='WORK'){selected.hidden=true;body.maxLength=2000;body.placeholder='이번 주 한 일을 적어 주세요.';}requestKey=crypto.randomUUID();submittedContent=null;achievementDecision=null;workConfirm.hidden=true;
    if(receipt.chat_id){conversationId=receipt.chat_id;newConversation=false;forceLatest=true;}save();status.textContent='주간회의록에 등록했습니다. '+receipt.copy_text;await reload();return;
   }
   if(kind.value==='QUESTION'&&availability.nas_files&&!inputAttachment){
    const value=await api('/work-requests/nas/discover',{method:'POST',body:JSON.stringify({text})});if(!current())return;
    if(value.handled){
     if(!value.items.length&&!availability.scope_exempt){status.textContent=nasIndex?.emptyMessage('조건에 맞는 자료를 찾지 못했습니다. 파일명이나 고객사명을 조금 바꿔 주세요.')||'조건에 맞는 자료를 찾지 못했습니다.';return;}
     if(!value.items.length){status.textContent='이 PC의 안전업무 자료까지 확인합니다.';}
     else if(value.auto_select&&value.items.length===1){nasSelection=value.items[0];kind.value=value.action==='QUESTION'?'SOURCE_QUESTION':'NAS';selectionText();discoveryChoices.hidden=true;save();}
     else{discoveryChoices.replaceChildren(node('strong','찾은 자료를 선택해 주세요.'));discoveryChoices.hidden=false;
      for(const item of value.items){const choose=node('button',item.file_name),path=node('small',item.relative_path);choose.type='button';choose.title=item.file_name;choose.onclick=()=>{if(sending||!current()||body.value.trim()!==text)return;nasSelection=item;kind.value=value.action==='QUESTION'?'SOURCE_QUESTION':'NAS';selectionText();requestKey=crypto.randomUUID();submittedContent=null;discoveryChoices.hidden=true;save();form.requestSubmit();};discoveryChoices.append(choose,path);}
      status.textContent=value.revision_verified?'찾은 자료를 확인해 주세요.':'자료의 적용 시점과 내용을 확인해 선택해 주세요.';return;
     }
    }
   }
   if(kind.value==='EDIT'&&!availability.source_edit)throw Error('문구 수정 사본은 사용 중지 상태입니다.');if(sourceKinds.includes(kind.value)&&!availability.nas_files)throw Error('NAS 자료 요청은 사용 중지 상태입니다.');if(sourceKinds.includes(kind.value)&&!nasSelection)throw Error('NAS 자료를 먼저 선택해 주세요.');
   const content=(kind.value==='FILE'&&format.value==='PDF'?'파일 형식: PDF\n':'')+text;if(content.length>6000)throw Error('메시지를 조금 줄여 주세요.');
   const title=(items[0]?.title||nasSelection?.file_name||text.split('\n')[0]).slice(0,100),parent=items.at(-1)?.id;
   const created=await api('/work-requests',{method:'POST',body:JSON.stringify({request_key:requestKey,kind:kind.value==='NAS'?'FILE':kind.value==='SOURCE_QUESTION'?'QUESTION':kind.value,title,body:content,...(sourceKinds.includes(kind.value)?{nas_file_id:nasSelection.nas_file_id}:{}),...(inputAttachment?{input_attachment_id:inputAttachment.id}:{}),...(parent?{parent_request_id:parent}:{})})});
   if(!current())return;body.value='';nasSelection=null;inputAttachment=null;if(photoPreview){URL.revokeObjectURL(photoPreview);photoPreview=null;}photoState();kind.value='QUESTION';selectionText();options.open=false;discoveryChoices.hidden=true;requestKey=crypto.randomUUID();submittedContent=null;++viewEpoch;conversationId=created.conversation_id||created.id;newConversation=false;forceLatest=true;save();status.textContent='메시지를 보냈습니다.';await reload();
  }catch(e){if(current())status.textContent=e.message+' 입력 내용은 남아 있습니다.';}finally{sending=false;if(current()){photoState();submit.disabled=false;for(const input of[channel,workDate,kind,body,format])input.disabled=false;if(matchMedia('(max-width:740px)').matches)body.blur();else body.focus();}}};
 channelState();await reload();return cleanup;
}

function createOwnerInbox(panel,{api,download,current}){
 const head=node('div',null,'request-tools'),refresh=node('button','받은 요청 새로고침'),notice=node('p','받은 자료 요청을 확인하고 있습니다.','request-notice'),list=node('div',null,'request-list');refresh.type='button';head.append(node('h2','받은 자료 요청'),refresh);panel.append(head,notice,list);
 const reasons=new Map();let loading=false,busy=false;
 async function reload(force=false){
  if(!current()||loading||busy||!force&&panel.contains(document.activeElement))return;loading=true;refresh.disabled=true;
  try{const value=await api('/work-requests/owner/inbox');if(!current())return;
   if(!value.enabled){notice.textContent='NAS 자료 제공 확인을 준비하고 있습니다.';list.replaceChildren();return;}
   notice.textContent='파일을 확인한 뒤 자료 제공 여부를 선택해 주세요.';list.replaceChildren();if(!value.items.length)list.append(node('p','받은 자료 요청이 없습니다.'));
   for(const item of value.items){const card=node('article',null,'request-card owner-request'),header=node('header'),phase=item.review_phase==='RELEASED'?'제공 완료':item.review_phase==='DENIED'?'제공 안 함':item.review_phase==='LEGACY_READY'?'이전 자료 확인 필요':labels[item.status]||'확인 필요';card.dataset.requestId=item.id;
    header.append(node('h3',item.title),node('span',phase,'request-badge'));card.append(header,node('p','요청자 · '+item.requester_name),node('p',item.body,'request-body'));if(item.source)card.append(node('p','출처 · '+item.source.relative_path,'request-source'));
    if(!item.source_available)card.append(node('p','원본 자료와 요청자의 이용 권한을 확인해 주세요.','request-notice'));
    const fields={review_version:item.review_version,source_sha256:item.source_sha256};
    async function action(kind,extra={},button){
     if(busy||!current())return;busy=true;button.disabled=true;const message=kind==='prepare'?'자료 확인을 요청했습니다.':kind==='release'?'자료를 제공했습니다.':'제공 안 함으로 처리했습니다.';
     try{await api('/work-requests/owner/'+encodeURIComponent(item.id)+'/'+kind,{method:'POST',body:JSON.stringify({...fields,...extra})});if(current())notice.textContent=message;}
     catch(error){
      try{const observed=await api('/work-requests/'+encodeURIComponent(item.id));const same=observed.source_sha256===item.source_sha256;
       const confirmed=same&&(kind==='release'&&observed.review_phase==='RELEASED'&&observed.files.some(f=>f.id===extra.file_id&&f.sha256===extra.file_sha256)||kind==='prepare'&&['PREVIEW_QUEUED','PREVIEW_RUNNING','READY','RELEASED'].includes(observed.review_phase)||kind==='deny'&&observed.review_phase==='DENIED'&&observed.reply===extra.reason);
       if(!confirmed)throw error;if(current())notice.textContent=message;
      }catch{if(current())notice.textContent=error.message;}
     }finally{busy=false;if(current()){button.disabled=false;await reload(true);}}
    }
    if(['QUESTION','EDIT'].includes(item.kind)&&item.reply&&['READY','RELEASED'].includes(item.review_phase)){const answer=node('div',null,'request-reply');answer.append(node('strong','답변 확인'),node('p',item.reply));card.append(answer);}
    if(item.can_prepare){const prepare=node('button','자료 확인');prepare.type='button';prepare.onclick=()=>action('prepare',{},prepare);card.append(prepare);}
    const file=item.files?.[0];if(file){const preview=node('button',item.review_phase==='RELEASED'?'제공한 파일 확인':'파일 확인');preview.type='button';preview.title=file.filename;preview.onclick=async()=>{preview.disabled=true;try{await download(item.id,file);}catch(e){if(current())notice.textContent=e.message;}finally{if(current())preview.disabled=false;}};card.append(preview);}
    if(item.can_release&&file){const release=node('button','자료 제공','primary');release.type='button';release.onclick=()=>action('release',{file_id:file.id,file_sha256:file.sha256},release);card.append(release);}
    if(item.can_deny){const label=node('label','제공하지 않는 이유'),reason=node('input'),deny=node('button','제공 안 함');reason.id='release-reason-'+item.id;label.htmlFor=reason.id;reason.maxLength=500;reason.value=reasons.get(item.id)||'';reason.placeholder='예: 수정 중인 자료입니다. 확인 후 다시 요청해 주세요.';reason.oninput=()=>reasons.set(item.id,reason.value);deny.type='button';deny.onclick=()=>{if(!reason.value.trim()){reason.focus();notice.textContent='제공하지 않는 이유를 적어 주세요.';return;}action('deny',{reason:reason.value.trim()},deny);};card.append(label,reason,deny);}
    list.append(card);
   }
  }catch(e){if(current())notice.textContent=e.message;}
  finally{loading=false;if(current())refresh.disabled=false;}
 }
 refresh.onclick=()=>reload(true);return reload;
}
