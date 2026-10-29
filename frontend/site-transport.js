const labels=new Set(['차량 우선 검토','출입구 확인']);

// Compare complete project names, allowing only separately recorded trade suffixes.
export function transportProjectName(value){
 return String(value||'').normalize('NFKC')
  .replace(/\[(?:전기|소방|통신)\]/g,'')
  .replace(/\((?:전기|소방|통신|[,·\s])+\)$/g,'')
  .replace(/(?:전기|소방)공사$/,'공사').replace(/\s+/g,'');
}

export function transportFromPlans(sites,items){
 const result=new Map(),conflicts=new Set();
 if(!Array.isArray(items))return result;
 for(const plan of items){
  if(plan.source!=='INSPECTION_PLAN'||plan.archived_at||!['PLANNED','IN_PROGRESS'].includes(plan.status))continue;
  const detail=String(plan.detail_text||''),blocks=detail.match(/^이동 안내: .+$/gm);
  if(blocks?.length!==1)continue;
  const label=blocks[0].slice('이동 안내: '.length);
  if(!labels.has(label))continue;
  const name=detail.match(/^현장: (.+)$/m)?.[1],body=detail.slice(detail.indexOf(blocks[0])+blocks[0].length).trim();
  if(!name||!body||body.length>600)continue;
  const key=transportProjectName(name);
  for(const site of sites){
   if(transportProjectName(site.name)!==key)continue;
   const entry={label,body,date:plan.scheduled_date,plan:plan.public_id};
   if(result.has(site.code)&&result.get(site.code).plan!==entry.plan){result.delete(site.code);conflicts.add(site.code);}
   if(!conflicts.has(site.code))result.set(site.code,entry);
  }
 }
 return result;
}

export function transportDateRange(today){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(today))throw Error('점검 기준일을 확인해 주세요.');
 const end=new Date(today+'T00:00:00Z');if(!Number.isFinite(end.getTime()))throw Error('점검 기준일을 확인해 주세요.');
 end.setUTCDate(end.getUTCDate()+60);
 return new URLSearchParams({from_date:today,to_date:end.toISOString().slice(0,10),inspection_only:'true',include_archived:'false'});
}

export async function loadTransport({sites,request,role,today,isCurrent,apply}){
 if(role!=='HQ_SAFE'||!isCurrent())return;
 try{
  const value=await request('/safety-features/team-schedule/items?'+transportDateRange(today));
  if(!isCurrent())return;
  apply(transportFromPlans(sites,value.items),null);
 }catch{
  if(isCurrent())apply(new Map(),'이동 안내를 불러오지 못했습니다. 현장 메모에서 확인해 주세요.');
 }
}

export function transportCard(value,documentRef=document){
 if(!value||!labels.has(value.label))return null;
 const card=documentRef.createElement('section');card.className='site-transport';card.setAttribute('aria-label','이동 안내');
 card.style.cssText='margin:12px 0;padding:12px;border:2px solid '+(value.label==='차량 우선 검토'?'#a25c00':'#7051ac')+';border-radius:10px;background:#fff;color:#263544;overflow-wrap:anywhere';
 const heading=documentRef.createElement('strong'),body=documentRef.createElement('p');heading.textContent=value.label;body.textContent=value.body;body.style.cssText='margin:6px 0 0;white-space:pre-line;line-height:1.6';card.append(heading,body);return card;
}
