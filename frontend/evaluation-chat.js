import {mountWorkRequests} from '/assets/work-requests.js';
import {receiveVerifiedFile} from '/assets/request-file-download.js';

// Navigation context is not a grant: both original file access and the existing
// evaluation upload are authorized independently by their original server APIs.
export function createEvaluationChat({panel,origin,token,session,isCurrent,api,attach,maxBytes,notify}){
 const N=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
 const limit=Number.isSafeInteger(maxBytes)&&maxBytes>0?Math.min(maxBytes,15*1024*1024):15*1024*1024;
 const drafts=new Map(),urls=new Set(),dialog=N('dialog'),bar=N('div'),label=N('strong'),dismiss=N('button','‹ 평가'),progress=N('p'),host=N('div');
 dialog.className='hyr-source-chat';dialog.setAttribute('aria-label','평가자료 찾기');bar.className='hyr-source-chat-context';dismiss.type='button';progress.setAttribute('role','status');bar.append(label,dismiss);dialog.append(bar,progress,host);panel.append(dialog);
 const style=N('style');style.textContent='.hyr-source-chat{padding:0;border:1px solid #8195a2;border-radius:8px;width:min(1100px,calc(100vw - 32px));height:min(900px,calc(100dvh - 32px));max-width:none;max-height:none;background:#173440;color:#edf5f8;overflow:hidden}.hyr-source-chat[open]{display:flex;flex-direction:column}.hyr-source-chat::backdrop{background:#102731b8}.hyr-source-chat-context{display:flex;align-items:center;gap:8px;flex-shrink:0;padding:6px 12px;border-bottom:1px solid #617d8a;font-size:13px;min-width:0}.hyr-source-chat-context strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hyr-source-chat button{min-height:44px;color:#edf5f8;background:#284b5a;border:1px solid #8199a6;border-radius:5px;padding:8px 12px;font:inherit}.hyr-source-chat>p{margin:0;padding:4px 12px;flex-shrink:0;min-height:0;font-size:13px;white-space:pre-wrap}.hyr-source-chat>p:empty{display:none}.hyr-source-chat>.work-requests{display:flex;flex-direction:column;flex:1;min-height:0;max-width:none;overflow:hidden}.hyr-source-chat .request-chat{min-height:0}.hyr-source-chat .request-result-use{min-height:44px;margin-top:6px;max-width:100%;white-space:normal}@media(max-width:740px){.hyr-source-chat{position:fixed;inset:0;width:100vw;height:100dvh;margin:0;border:0;border-radius:0}.hyr-source-chat>.work-requests{max-height:var(--chat-viewport-height,100dvh)}}';panel.append(style);
 let alive=true,opened=null,cleanup=null,busy=false,controller=null,opening=0;
 const current=()=>alive&&opened!==null&&dialog.open&&isCurrent(opened);
 function guard(){session();if(!current())throw Error('평가 화면이 바뀌어 자료 연결을 중단했습니다.');}
 function close(force=false){if(busy&&!force){progress.textContent='자료 연결이 끝날 때까지 잠시 기다려 주세요.';return;}opening++;controller?.abort();controller=null;cleanup?.();cleanup=null;const previous=opened;opened=null;host.replaceChildren();if(dialog.open)dialog.close();progress.textContent='';if(previous){const target=[...panel.querySelectorAll('.hyr-chat-find')].find(b=>b.dataset.evidence===previous.evidence);target?.focus({preventScroll:true});}}
 dismiss.onclick=()=>close();dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
 async function stylesheet(){
  const href='/assets/work-requests.css';let link=[...document.querySelectorAll('link[rel=stylesheet]')].find(e=>/^\/assets\/work-requests(?:-[a-f0-9]+)?\.css$/.test(new URL(e.href,location.href).pathname));
  if(link?.sheet)return;
  if(!link){link=N('link');link.rel='stylesheet';link.href=href;document.head.append(link);}
  await new Promise((resolve,reject)=>{let timer;const finish=(error)=>{clearTimeout(timer);link.removeEventListener('load',loaded);link.removeEventListener('error',failed);error?reject(Error('채팅 화면을 불러오지 못했습니다. 다시 눌러 주세요.')):resolve();},loaded=()=>finish(),failed=()=>finish(true);link.addEventListener('load',loaded,{once:true});link.addEventListener('error',failed,{once:true});timer=setTimeout(failed,10000);if(link.sheet)finish();});
 }
 async function bytes(item,file,{input=false}={}){
  guard();if(!/^[a-f0-9]{32}$/.test(item.id||'')||!/^[a-f0-9]{32}$/.test(file.id||''))throw Error('파일 정보를 다시 확인해 주세요.');
  const abort=new AbortController();controller=abort;const timer=setTimeout(()=>abort.abort(),60000);
  try{const response=await fetch(origin+'/work-requests/'+item.id+(input?'/inputs/':'/files/')+file.id,{headers:{Authorization:'Bearer '+token},credentials:'omit',redirect:'error',cache:'no-store',signal:abort.signal});guard();if(!response.ok)throw Error('자료 이용 권한이나 파일 상태를 확인해 주세요.');return await receiveVerifiedFile(response,file,{maxBytes:input?16*1024*1024:32*1024*1024,guard,onProgress:value=>{if(current())progress.textContent=value.phase==='VERIFYING'?'파일 내용을 확인하고 있습니다.':'파일 받는 중 '+Math.floor(value.loaded/value.total*100)+'%';}});}finally{clearTimeout(timer);if(controller===abort)controller=null;}
 }
 async function useFile(item,file){
  if(busy)return;guard();const context=opened;
  if(file.input||typeof file.filename!=='string'||file.filename.length>180||/[\\/\x00-\x1f]/.test(file.filename)||!/^.+\.(pdf|xlsx|docx|pptx|hwp|hwpx)$/i.test(file.filename)||!Number.isSafeInteger(file.bytes)||file.bytes<1||file.bytes>limit)throw Error('평가자료에 연결할 수 있는 파일인지 확인해 주세요.');
  busy=true;dismiss.disabled=true;progress.textContent='자료를 확인하고 있습니다.';
  try{const raw=await bytes(item,file);guard();if(opened!==context||raw.byteLength!==file.bytes)throw Error('평가자료의 연결 대상을 다시 확인해 주세요.');const stored=await attach(context,new File([raw],file.filename,{type:'application/octet-stream'}));guard();if(!stored||stored.sha256!==file.sha256||stored.bytes!==file.bytes)throw Error('평가자료 저장 결과를 확인해 주세요. 다시 연결해도 같은 내용은 중복 보관하지 않습니다.');busy=false;close();notify(context.label+' 자료를 추가했습니다. 확인한 뒤 체크해 주세요.');}finally{busy=false;dismiss.disabled=false;}
 }
 const control={
  async open(context){
   session();if(!alive||busy||!context||!/^[a-f0-9-]{36}$/.test(context.plan||'')||!/^20\d{2}-H[12]$/.test(context.period||'')||typeof context.evidence!=='string'||typeof context.label!=='string'||!isCurrent(context))return;
   if(opened)close();const id=++opening;opened={...context};const captured=opened,key=context.plan+'|'+context.period+'|'+context.evidence;
   const seed=(context.site+' '+context.label+' 자료를 찾아줘').trim().slice(0,6000);label.textContent=context.site+' · '+context.period.replace('-H1','년 상반기').replace('-H2','년 하반기')+' · '+context.label;host.replaceChildren();dismiss.hidden=false;progress.textContent='베스마채팅을 불러오고 있습니다.';dialog.showModal();
   try{await stylesheet();if(!current()||id!==opening)return;const saved=drafts.get(key);const dispose=await mountWorkRequests(host,{api,onRetry:()=>control.open(captured),initialDraft:saved?.draft||{newConversation:true,channel:'CHAT',kind:'QUESTION',body:seed},onDraft:draft=>{if(!alive)return;drafts.delete(key);drafts.set(key,{draft,seed});if(drafts.size>12)drafts.delete(drafts.keys().next().value);},isCurrent:()=>current()&&opened===captured&&id===opening,onBack:()=>close(),onUseFile:useFile,useFileMaxBytes:limit,download:async(rid,file)=>{const raw=await bytes({id:rid},file,{input:file.input===true});guard();const url=URL.createObjectURL(new Blob([raw],{type:file.input?file.media_type:'application/octet-stream'}));urls.add(url);if(file.input&&file.preview)return url;const a=N('a');a.href=url;a.download=file.filename;a.click();}});if(!current()||id!==opening){dispose?.();return;}cleanup=dispose;dismiss.hidden=true;progress.textContent='';}catch(error){if(current()&&id===opening)progress.textContent=error.message;}
  },
  hasUnsaved:()=>busy||[...drafts.values()].some(x=>x.draft.pendingSubmission||x.draft.inputAttachment||typeof x.draft.body==='string'&&x.draft.body.trim()&&x.draft.body.trim()!==x.seed.trim()),
  dispose(){alive=false;close(true);drafts.clear();for(const url of urls)URL.revokeObjectURL(url);urls.clear();dialog.remove();style.remove();}
 };
 return control;
}
