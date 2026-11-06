const n=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
const digest=async raw=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(x=>x.toString(16).padStart(2,'0')).join('');
export function createSignatureOutput({host,request,bytes,previewPage,session}){
 const requests=new Map();let dialog=null;
 async function open(c){
  session();dialog?.close();const active=n('dialog');dialog=active;active.className='signature-output-dialog';active.setAttribute('aria-label','소장 서명용 PDF');
  const report=c.purpose==='REPORT',signing=!report&&['report','law'].includes(c.form),purpose=report?'REPORT':'SIGNATURE';active.setAttribute('aria-label',report?'대표 보고용 PDF':signing?'소장 서명용 PDF':'평가서 PDF');
  const title=n('h2',c.site+(report?' · 대표 보고용 PDF':signing?' · 소장 서명용 PDF':' · 평가서 PDF')),status=n('p','평가서를 준비하고 있습니다.'),close=n('button','닫기'),refresh=n('button','상태 다시 확인'),files=n('div');for(const b of[close,refresh])b.type='button';close.onclick=()=>active.close();status.setAttribute('role','status');active.append(title,close,status,refresh,files);host.append(active);
  const key=[c.plan,c.period,c.form,c.subject,c.snapshot,purpose].join('|');requests.set(key,crypto.randomUUID());
  const path='/plans/'+encodeURIComponent(c.plan)+'/signature-prints',query='?'+new URLSearchParams({period:c.period});let job=null,timer=null,pdfUrl=null,pageUrl=null,pageSequence=0,downloadStarted=false;
  const guard=()=>{session();if(!active.isConnected||!active.open)throw Error('출력 화면이 닫혔습니다.');};
  active.addEventListener('close',()=>{if(timer)clearTimeout(timer);pageSequence++;if(pdfUrl)URL.revokeObjectURL(pdfUrl);if(pageUrl)URL.revokeObjectURL(pageUrl);active.remove();if(dialog===active)dialog=null;},{once:true});active.showModal();
  async function showPages(value){
   guard();active.querySelector('.signature-pages')?.remove();if(pageUrl){URL.revokeObjectURL(pageUrl);pageUrl=null;}const pass=++pageSequence,section=n('section'),nav=n('nav'),previous=n('button','이전 쪽'),counter=n('span'),next=n('button','다음 쪽'),area=n('div'),image=n('img'),message=n('p','PDF 페이지를 준비하고 있습니다.');section.className='signature-pages';area.className='signature-page-image';nav.setAttribute('aria-label','PDF 페이지 이동');previous.type=next.type='button';previous.disabled=next.disabled=true;nav.append(previous,counter,next);area.append(image);section.append(nav,message,area);active.append(section);let metadata=null,number=1;
   async function page(index){
    guard();const turn=++pageSequence;image.removeAttribute('src');if(pageUrl){URL.revokeObjectURL(pageUrl);pageUrl=null;}number=index;previous.disabled=next.disabled=true;counter.textContent=number+' / '+metadata.pages.length+'쪽';message.textContent=number+'쪽을 불러오고 있습니다.';
    try{const response=await previewPage(path+'/'+value.id+'/preview/'+index+query);guard();if(turn!==pageSequence)return;const raw=await response.arrayBuffer();guard();if(turn!==pageSequence)return;
     const actual=await digest(raw);guard();if(turn!==pageSequence)return;if(response.headers.get('content-type')?.split(';')[0]!=='image/png'||response.headers.get('x-source-sha256')!==value.result.sha256||response.headers.get('x-page-number')!==String(index)||raw.byteLength>6*1024*1024||actual!==response.headers.get('x-preview-sha256'))throw Error('PDF 페이지를 다시 확인해 주세요.');
     if(pageUrl)URL.revokeObjectURL(pageUrl);pageUrl=URL.createObjectURL(new Blob([raw],{type:'image/png'}));image.src=pageUrl;image.alt=value.filename+' '+index+'쪽';area.scrollTop=0;message.textContent='';
    }catch(e){if(active.isConnected&&turn===pageSequence)message.textContent=e.message;}finally{if(active.isConnected&&turn===pageSequence){previous.disabled=number<=1;next.disabled=number>=metadata.pages.length;}}
   }
   previous.onclick=()=>void page(number-1);next.onclick=()=>void page(number+1);
   try{metadata=await request(path+'/'+value.id+'/preview'+query);guard();if(pass!==pageSequence)return;if(metadata.source_sha256!==value.result.sha256||metadata.source_bytes!==value.result.bytes||!Array.isArray(metadata.pages)||!metadata.pages.length||metadata.pages.length>30)throw Error('PDF 원본을 다시 확인해 주세요.');await page(1);}catch(e){if(active.isConnected)message.textContent=e.message;}
  }
  async function paint(value){
   if(!active.isConnected)return;job=value;
   if(value.status==='READY'){
    status.textContent=report?'대표 보고용 평가서를 만들었습니다.':signing?'소장 서명용 평가서를 만들었습니다.':'평가서를 만들었습니다.';files.replaceChildren();const view=n('button','PDF 보기'),download=n('button','다운로드');view.type=download.type='button';
    view.onclick=()=>showPages(value).catch(e=>{if(active.isConnected)status.textContent=e.message;});
    download.onclick=async()=>{try{guard();if(!pdfUrl){const raw=await bytes(path+'/'+value.id+'/file'+query);guard();if(await digest(raw)!==value.result.sha256||raw.byteLength!==value.result.bytes)throw Error('생성된 PDF를 다시 확인해 주세요.');pdfUrl=URL.createObjectURL(new Blob([raw],{type:'application/pdf'}));}const a=n('a');a.href=pdfUrl;a.download=value.filename;a.click();}catch(e){if(active.isConnected)status.textContent=e.message;}};
    files.append(view,download);if(signing)files.append(n('p','공무 전달용입니다. 다운로드한 파일을 웍스에 첨부해 주세요.'));if(c.download&&!downloadStarted){downloadStarted=true;await download.onclick();}return;
   }
   if(value.status==='FAILED'){requests.delete(key);status.textContent='평가서를 만들지 못했습니다. 출력하기를 다시 눌러 주세요.';return;}
   status.textContent=value.status==='RENDERING'?'평가서를 만들고 있습니다.':'평가서 작성을 기다리고 있습니다.';timer=setTimeout(poll,2500);
  }
  async function poll(){if(!active.isConnected)return;if(timer)clearTimeout(timer);try{const result=await request(path+query),value=result.items.find(x=>x.id===job?.id);if(value)await paint(value);else if(!job)await paint(await request(path+query,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:requests.get(key),form:c.form,subject_id:c.subject,snapshot_id:c.snapshot,purpose})}));}catch{if(active.isConnected)status.textContent='출력 상태 확인 실패 · 상태 다시 확인을 눌러 주세요.';}}
  refresh.onclick=poll;try{await paint(await request(path+query,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:requests.get(key),form:c.form,subject_id:c.subject,snapshot_id:c.snapshot,purpose})}));}catch(e){if(active.isConnected)status.textContent=e.message;}
 }
 return{open,dispose(){dialog?.close();requests.clear();}};
}
