const folders={theme:['1. 안전 점검','테마점검'],'legal-training':['2. 법적교육(특별,정기 등)'],risk:['3. 위험성평가'],opinions:['4. 근로자 의견 청취'],'safety-cost':['6. 산업안전보건관리비']};
const labels={theme:'테마점검','legal-training':'법정교육',risk:'위험성평가',opinions:'근로자 의견청취','safety-cost':'산업안전보건관리비'},same=(a,b)=>a.normalize('NFC')===b.normalize('NFC');
export function monthlyIdentity(item){
 if(!item||!/^[a-f0-9]{64}$/.test(item.id||'')||!/^20\d{2}-(0[1-9]|1[0-2])$/.test(item.month||'')||!folders[item.category]||!/^([1-6]팀|관급|미분류)$/.test(item.team||'')||typeof item.filename!=='string'||!item.filename||item.filename.length>600||/[\\/\u0000-\u001f\u007f]/.test(item.filename)||!Number.isSafeInteger(item.size)||item.size<1)throw Error('선택한 자료 정보를 다시 확인해 주세요.');
 const value={id:item.id,month:item.month,category:item.category,team:item.team,filename:item.filename,size:item.size,site:typeof item.site==='string'?item.site.slice(0,500):''};
 if(Object.hasOwn(item,'storage_filename')){const name=item.storage_filename;if(typeof name!=='string'||!name||name.length>600||/[\\/\u0000-\u001f\u007f]/.test(name)||name.split('.').at(-1).toLowerCase()!==item.filename.split('.').at(-1).toLowerCase())throw Error('선택한 자료의 저장명을 다시 확인해 주세요.');value.storage_filename=name;}
 return value;
}
export function monthlyQuery(item){const v=monthlyIdentity(item),folder={theme:'테마점검',risk:'위험성평가',opinions:'의견','safety-cost':'산업안전보건관리비','legal-training':'법적교육'}[v.category],scope=['월간',v.month.slice(2).replace('-','.')+'월',v.team,folder].join(' '),name=(v.storage_filename||v.filename).normalize('NFC').replace(/\.[^.]+$/,'').trim().split(/\s+/).slice(0,3).join(' '),prefix=Array.from(name).slice(0,100-Array.from(scope).length-1).join('');return(prefix+' '+scope).trim();}
export function monthlyCandidates(item,items){const v=monthlyIdentity(item),prefix=['★월간 자료 취합',...folders[v.category],v.month.slice(2).replace('-','.')+'월',v.team];if(!Array.isArray(items))throw Error('검색 결과를 확인하지 못했습니다.');const unique=new Map();for(const x of items){if(!x||typeof x.nas_file_id!=='string'||x.nas_file_id.length<8||x.nas_file_id.length>8192||typeof x.file_name!=='string'||!same(x.file_name,v.storage_filename||v.filename)||x.size!==v.size||typeof x.relative_path!=='string'||/[\u0000-\u001f\u007f]/.test(x.relative_path))continue;const parts=x.relative_path.replaceAll('\\','/').split('/');if(parts.some(p=>!p||p==='.'||p==='..')||parts.length<=prefix.length||!prefix.every((p,i)=>same(p,parts[i]))||!same(parts.at(-1),v.storage_filename||v.filename))continue;const key=parts.map(p=>p.normalize('NFC')).join('/');if(!unique.has(key))unique.set(key,x);}return [...unique.values()];}
export function monthlyHandoff(item,source){const v=monthlyIdentity(item);if(monthlyCandidates(v,[source]).length!==1)throw Error('선택한 자료의 월·종류·팀·원본이 다릅니다.');return {version:1,at:Date.now(),requestKey:crypto.randomUUID(),item:v,source};}
export function checkedMonthlyHandoff(value){if(!value||value.version!==1||!Number.isFinite(value.at)||Date.now()-value.at<0||Date.now()-value.at>600000||!/^[a-zA-Z0-9_-]{8,80}$/.test(value.requestKey||'')||Object.hasOwn(value,'parentRequestId')&&value.parentRequestId!==null&&!/^[a-f0-9]{32}$/.test(value.parentRequestId))return null;try{const item=monthlyIdentity(value.item);if(monthlyCandidates(item,[value.source]).length!==1)return null;return {...value,item};}catch{return null;}}
export function monthlyRequestBody(value){const v=checkedMonthlyHandoff(value);if(!v)throw Error('취합현황에서 자료를 다시 선택해 주세요.');return [v.item.site||'현장 확인 필요',v.item.month+' · '+labels[v.item.category]+' · '+v.item.team,v.item.filename,'이 자료를 보내 주세요.'].join('\n');}

export async function findMonthlyCandidates(item,api,{current=()=>true,onProgress=()=>{}}={}){
 const q=monthlyQuery(item),all=[];let offset=0,snapshot=null,total=null;
 for(let page=0;page<50;page++){
  if(!current())throw Error('현재 자료 화면이 변경되었습니다.');
  const body={q};if(offset){body.offset=offset;body.snapshot=snapshot;}
  const found=await api('/work-requests/nas/search',{method:'POST',body:JSON.stringify(body)});
  if(!current())throw Error('현재 자료 화면이 변경되었습니다.');
  if(!found||!Array.isArray(found.items)||found.items.length>20||typeof found.complete!=='boolean'||!Number.isSafeInteger(found.total_count)||found.total_count<0||found.total_count>1000000||found.offset!==offset||!Number.isSafeInteger(found.scanned_count)||found.scanned_count<offset||found.scanned_count>found.total_count||!/^[a-f0-9]{64}$/.test(found.snapshot||'')||snapshot!==null&&found.snapshot!==snapshot||total!==null&&found.total_count!==total)throw Error('원본 검색 범위를 확인하지 못했습니다. 다시 시도해 주세요.');
  snapshot=found.snapshot;total=found.total_count;all.push(...found.items);
  onProgress({scanned:found.scanned_count,total});
  if(found.complete){if(found.next_offset!==null||found.scanned_count!==total)throw Error('원본 검색 완료를 확인하지 못했습니다.');return monthlyCandidates(item,all);}
  if(!Number.isSafeInteger(found.next_offset)||found.next_offset<=offset||found.next_offset!==found.scanned_count||found.next_offset>=total)throw Error('원본 검색의 다음 범위를 확인하지 못했습니다.');
  offset=found.next_offset;
 }
 throw Error('원본 검색 범위가 많아 확인이 필요합니다. 현재 자료와 입력은 유지됩니다.');
}
