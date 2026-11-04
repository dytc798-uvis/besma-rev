// Summarize only the authorized, persisted completion snapshots already loaded.
export function evaluationStatus(items,catalog){
 const groups=new Map();
 for(const item of items){
  if(!/^20\d{2}-H[12]$/.test(item.period))continue;
  if(!groups.has(item.period))groups.set(item.period,{period:item.period,plans:new Set(),states:{COMPLETED:0,IN_PROGRESS:0,NOT_STARTED:0},forms:new Map(),seen:new Set()});
  const g=groups.get(item.period);
  if(!g.plans.has(item.public_id)){g.plans.add(item.public_id);if(Object.hasOwn(g.states,item.status))g.states[item.status]++;}
  for(const form of item.forms||[]){
   if(form.source_type==='PRIOR_PDF'||!form.snapshot_id||!catalog.forms[form.form])continue;
   const key=String(form.form)+':'+form.snapshot_id;if(g.seen.has(key))continue;g.seen.add(key);
   if(!g.forms.has(form.form))g.forms.set(form.form,{form:form.form,count:0,scores:[],fail:0,pass:0,na:0});
   const r=g.forms.get(form.form);r.count++;
   if(typeof form.score==='number'&&Number.isFinite(form.score))r.scores.push(form.score);
   if(form.verdicts)for(const [src,dst]of [['FAIL','fail'],['PASS','pass'],['NA','na']])if(Number.isInteger(form.verdicts[src])&&form.verdicts[src]>=0)r[dst]+=form.verdicts[src];
  }
 }
 return [...groups.values()].sort((a,b)=>b.period.localeCompare(a.period)).map(g=>({period:g.period,plans:g.plans.size,states:g.states,forms:catalog.order.map(key=>{const r=g.forms.get(key)||{form:key,count:0,scores:[],fail:0,pass:0,na:0};return {form:key,count:r.count,scored:r.scores.length,average:r.scores.length?r.scores.reduce((a,b)=>a+b,0)/r.scores.length:null,fail:r.fail,pass:r.pass,na:r.na};})}));
}
const node=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
export function renderEvaluationStatus(host,items,catalog){
 host.replaceChildren();host.style.cssText='margin:12px 0;padding:14px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#172b4d';
 const title=node('h2','반기 평가 현황');title.style.cssText='margin:0 0 8px;font-size:18px';host.append(title);
 if(host.dataset.periodRange){const range=node('p','내 담당 평가 · 조회기간 '+host.dataset.periodRange);range.style.cssText='margin:6px 0;font-size:13px;color:#475569';host.append(range);}
 if(items===null){host.append(node('p','평가 현황을 확인하고 있습니다.'));return;}
 const groups=evaluationStatus(items,catalog);
 if(!groups.length){host.append(node('p','선택한 기간에 조회할 평가계획이 없습니다.'));return;}
 for(const g of groups){
  const [year,half]=g.period.split('-H');const text=node('p',`${year}년 ${half==='1'?'상반기':'하반기'} · 평가계획 ${g.plans}건 · 완료 ${g.states.COMPLETED} · 진행중 ${g.states.IN_PROGRESS} · 미평가 ${g.states.NOT_STARTED}`);text.style.cssText='margin:8px 0;line-height:1.6;overflow-wrap:anywhere';host.append(text);
  const table=node('table');table.style.cssText='width:100%;border-collapse:collapse;font-size:14px';const thead=node('thead'),head=node('tr');for(const label of ['평가표','작성 완료','결과'])head.append(node('th',label));thead.append(head);table.append(thead);const body=node('tbody');
  for(const r of g.forms){const schema=catalog.forms[r.form],tr=node('tr');let result='—';if(r.count)result=schema.scoring==='COMPLIANCE'?`적합 ${r.pass} · 부적합 ${r.fail} · 해당없음 ${r.na}`:r.average===null?'점수 확인 필요':`평균 ${Number(r.average.toFixed(1))}점`;tr.append(node('td',schema.title),node('td',r.count+'건'),node('td',result));body.append(tr);}table.append(body);for(const cell of table.querySelectorAll('th,td'))cell.style.cssText='padding:8px 5px;text-align:left;border-bottom:1px solid #e2e8f0;vertical-align:top;overflow-wrap:anywhere';host.append(table);
 }
 const note=node('p','점수는 작성 완료한 전자평가표 기준입니다. PDF 등록과 현장 평가완료는 각각의 확인 기록을 따릅니다.');note.style.cssText='margin:10px 0 0;font-size:13px;line-height:1.5;color:#475569';host.append(note);
}
