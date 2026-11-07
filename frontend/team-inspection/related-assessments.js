const names={EXCELLENT:'우수',NORMAL:'보통',POOR:'미흡',PASS:'적합',FAIL:'부적합',NA:'해당없음'};
// Only comparable checks share a grade. A generic equipment/inspection file
// cannot establish every separate on-site legal duty.
const comparable=[
 ['p01','p02','p03','p04','m19','s13','s15','s16','l02','l16'],
 ['p05','p06','p07','p08','m06','l03','l09','l10','l11'],
 ['p11','p12','p13','m09','s09','l05'],
 ['p03','p09','p10','m20','m21','l04'],
 ['p15','p16','p17','m13','l13','l14'],
 ['m16','l06']
];
export function evidenceDefaults({catalog,form,assessments,evidence={},answers={},blocked=new Set()}){
 const schema=catalog.forms[form],result={};
 for(const q of schema.criteria){
  if(answers[q.id]?.value!=null||blocked.has(q.id))continue;
  const allowed=new Set(comparable.filter(g=>g.includes(q.id)).flat());
  if(!allowed.size)continue;
  const sources=relatedAnswers({catalog,form,criterion:q,assessments}).filter(r=>allowed.has(r.criterion)&&r.value!=null&&r.value!=='NA');
  const full=r=>{const c=catalog.forms[r.form].criteria.find(c=>c.id===r.criterion);return r.value==='PASS'||r.value==='EXCELLENT'||typeof r.value==='number'&&Number.isInteger(r.value)&&r.value===c.max_score;};
  // A conflicting partial/poor verdict still needs the evaluator's decision.
  if(!sources.length||sources.some(r=>!full(r)))continue;
  const covered=new Set(sources.flatMap(r=>r.evidence));
  // Notes/files mark an evidence row checked, even when the note reports a gap.
  // Only a full graded counterpart can cover a target requirement.
  if(q.evidence.some(id=>evidence[id]?.hold===true||!covered.has(id)))continue;
  result[q.id]={value:schema.scoring==='COMPLIANCE'?'PASS':q.max_score,sources:sources.map(r=>({form:r.form,criterion:r.criterion,number:r.number,title:r.form_title})),supplemental:q.evidence.filter(id=>!covered.has(id))};
 }
 return result;
}
export function relatedAnswers({catalog,form,criterion,assessments}){
 const rows=[];
 for(const[key,record]of Object.entries(assessments||{})){
  const at=key.indexOf(':'),kind=key.slice(0,at),subject=key.slice(at+1),schema=catalog.forms[kind];if(!schema||kind===form)continue;
  const snapshot=record.draft||record.completed,data=snapshot?.data;if(!data)continue;
  for(const[index,q]of schema.criteria.entries()){
   if(kind==='report'&&(snapshot.criteria_version||1)<2&&q.id==='p02')continue;
   const common=q.evidence.filter(id=>criterion.evidence.includes(id)),a=data.answers?.[q.id];if(!common.length||!a||(a.value==null&&!a.note?.trim()))continue;
   const points=typeof a.value==='number'?a.value:['EXCELLENT','NORMAL','POOR'].includes(a.value)?q.max_score*({EXCELLENT:1,NORMAL:.5,POOR:0}[a.value]):null;
   rows.push({key:key+':'+q.id,form:kind,subject,criterion:q.id,number:index+1,title:q.title,form_title:schema.title,value:a.value,score:points==null?(names[a.value]||'미채점'):points+' / '+q.max_score+'점',note:a.note||'',evidence:common,rank:(a.note?.trim()?10:0)+common.length/Math.max(q.evidence.length,criterion.evidence.length)});
  }
 }
 return rows.sort((a,b)=>b.rank-a.rank||catalog.order.indexOf(a.form)-catalog.order.indexOf(b.form)||a.number-b.number);
}
export function renderRelated(host,rows,{jump,notice}){
 const signature=JSON.stringify(rows);if(host.dataset.signature===signature)return;host.dataset.signature=signature;host.replaceChildren();host.hidden=!rows.length;if(!rows.length)return;
 const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};host.append(node('strong','다른 평가에서 입력한 내용'));
 const add=(parent,row)=>{const item=node('article',null,'related-answer');item.dataset.relatedSource=row.key;item.append(node('strong',row.form_title+' '+row.number+'번 · '+row.title),node('p','이전 평가: '+row.score,'related-answer-score'));if(row.note.trim())item.append(node('p',row.note,'related-answer-note'));const open=node('button','이 평가 문항 보기');open.type='button';open.setAttribute('aria-label',row.form_title+' '+row.number+'번 보기');open.onclick=()=>Promise.resolve(jump(row)).catch(e=>notice(e.message));item.append(open);parent.append(item);};
 rows.slice(0,2).forEach(r=>add(host,r));if(rows.length>2){const more=node('details',null,'related-answer-more');more.append(node('summary','다른 입력 '+(rows.length-2)+'개 더보기'));rows.slice(2).forEach(r=>add(more,r));host.append(more);}
}
