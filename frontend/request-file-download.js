export async function receiveVerifiedFile(response,file,{maxBytes=32*1024*1024,onProgress=()=>{},guard=()=>{}}={}){
 if(!Number.isSafeInteger(file.bytes)||file.bytes<1||file.bytes>maxBytes||!/^[a-f0-9]{64}$/.test(file.sha256||''))throw Error('파일 정보를 확인해 주세요.');
 const length=response.headers.get('content-length');
 if(length!==null&&(!/^\d+$/.test(length)||Number(length)!==file.bytes))throw Error('파일 크기를 확인하지 못했습니다. 다시 받아 주세요.');
 guard();onProgress({phase:'RECEIVING',loaded:0,total:file.bytes});
 const chunks=[];let loaded=0,complete=false;
 const reader=response.body?.getReader();
 try{
  if(reader){while(true){const next=await reader.read();guard();if(next.done){complete=true;break;}if(!(next.value instanceof Uint8Array)||loaded+next.value.byteLength>file.bytes)throw Error('파일 크기가 달라 받기를 중단했습니다.');chunks.push(next.value);loaded+=next.value.byteLength;onProgress({phase:'RECEIVING',loaded,total:file.bytes});}}
  else{const value=new Uint8Array(await response.arrayBuffer());if(value.byteLength>file.bytes)throw Error('파일 크기가 달라 받기를 중단했습니다.');chunks.push(value);loaded=value.byteLength;complete=true;}
 }finally{if(reader){if(!complete)await reader.cancel().catch(()=>{});reader.releaseLock();}}
 guard();if(loaded!==file.bytes)throw Error('파일 연결이 끊겼습니다. 다시 받아 주세요.');
 onProgress({phase:'VERIFYING',loaded,total:file.bytes});
 const bytes=new Uint8Array(loaded);let offset=0;for(const value of chunks){bytes.set(value,offset);offset+=value.byteLength;}
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
 guard();if(hash!==file.sha256)throw Error('파일 내용을 확인하지 못했습니다. 다시 받아 주세요.');
 return bytes;
}

