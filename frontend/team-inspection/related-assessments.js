const names={EXCELLENT:'우수',NORMAL:'보통',POOR:'미흡',PASS:'적합',FAIL:'부적합',NA:'해당없음'};
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
