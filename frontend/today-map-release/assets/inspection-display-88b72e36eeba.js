const normal=value=>String(value||'').normalize('NFKC').toLowerCase().replace(/[^가-힣a-z0-9]/g,'');
export function inspectionPeople(row){
 const detail=row.detail_text||'',all=detail.match(/^전체 인원\(\d+명\):\s*(.+)$/m),lead=detail.match(/^대표\/인솔:\s*(.+)$/m);
 let people=all?all[1].split(/[,，]/).map(x=>x.trim()).filter(Boolean):[];
 if(!people.length&&lead)people=[lead[1].trim()];
 if(!people.length){const prefix=(row.title||'').split(' · ')[0];if(/^(?:[가-힣]{3}|대표님)(?: 외 \d+명)?$/.test(prefix))people=[prefix];}
 if(!people.length&&row.assigned_user_name)people=[row.assigned_user_name];
 if(!people.length&&row.source!=='WEEKLY_MEETING'&&row.owner_name)people=[row.owner_name];
 return [...new Set(people)];
}
export function inspectionLabel(row){const prefix=(row.title||'').split(' · ')[0];return (/^(?:[가-힣]{3}|대표님|외 \d+명)(?: 외 \d+명)?$/.test(prefix)?row.title.slice(prefix.length+3):row.title||'').replace(/^\[점검\]\s*/,'');}
export function isInspectionVisit(row){return row.source==='INSPECTION_PLAN'||/점검|검검|현장.*(?:지원|방문)|안전.*교육|TBM/i.test(row.title||'');}
export function resolveInspectionSite(row,sites){
 if(row.site_code){const exact=sites.filter(s=>s.code===row.site_code);if(exact.length===1)return exact[0];}
 const text=normal(inspectionLabel(row)+' '+(row.detail_text||'').split('\n').filter(x=>x.startsWith('현장:')).join(' '));
 const trade=(inspectionLabel(row).match(/[([【]\s*(소방|전기)\s*[)\]】]/)||[])[1];
 const candidates=sites.filter(site=>{
  const name=site.name||'',m=name.match(/^\[(?:\d+\.)?([^\]]+)\]/),company=m?normal(m[1].replace(/건설|대한통운/g,'')):'';
  if(!company||!text.includes(company))return false;
  if(trade==='소방'&&!/소방/.test(name)||trade==='전기'&&/소방/.test(name))return false;
  const body=name.replace(/^\[[^\]]+\]/,'');
  const tokens=body.split(/[\s()[\],/]+/).map(t=>normal(t.replace(/구역|주택|재개발|정비사업|신축|공동|아파트|푸르지오|전기설비|전기공사|소방공사|건설공사/g,''))).filter(t=>t.length>=2&&!/^(?:공사|현장|전기|소방|통신|사업|건설|공구|시설)$/.test(t));
  const source=normal(inspectionLabel(row).replace(/건설/g,''));
  return tokens.some(t=>source.includes(t)||inspectionLabel(row).split(/\s+/).map(normal).some(word=>word.length>=3&&t.startsWith(word)));
 });
 return candidates.length===1?candidates[0]:null;
}
function visitTime(row){const title=inspectionLabel(row),detail=row.detail_text||'';return (title.match(/\b\d{1,2}:\d{2}\b/)||title.match(/오전|오후/)||detail.match(/(?:^|\()\d{1,2}:\d{2}/m)||[''])[0].replace('(','');}
export function groupInspectionRecords(items,sites=[]){
 const groups=new Map();
 for(const row of items){
  const people=inspectionPeople(row),site=isInspectionVisit(row)?resolveInspectionSite(row,sites):null;
  const label=normal(inspectionLabel(row).replace(/반기평가|안전보건|안전|점검|검검|건설|실시|정기|참석/g,''));
  const key=[row.scheduled_date,row.due_date||row.scheduled_date,site?site.code:label,people[0]||'unknown'].join('|');
  if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);
 }
 const result=[];
 for(const rows of groups.values()){
  const clocks=[...new Set(rows.map(visitTime).filter(Boolean))],parts=clocks.length>1?[...new Set(rows.map(visitTime))].map(clock=>rows.filter(row=>visitTime(row)===clock)):[rows];
  for(const part of parts){const selected=[...part].sort((a,b)=>(b.source==='INSPECTION_PLAN')-(a.source==='INSPECTION_PLAN')||String(b.updated_at||'').localeCompare(String(a.updated_at||'')))[0];result.push({...selected,related_records:part,visit_people:[...new Set(part.flatMap(inspectionPeople))],visit_site:resolveInspectionSite(selected,sites)||part.map(r=>resolveInspectionSite(r,sites)).find(Boolean)||null});}
 }
 return result;
}
export function inspectionIsMine(row,user){return row.visit_people?.includes(user?.name)|| (row.source==='WEEKLY_MEETING'?inspectionPeople(row).includes(user?.name):row.owner_user_id===user?.id||row.assigned_user_id===user?.id);}
