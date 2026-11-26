// Reviewed submission evidence fills only unanswered items when an evaluator opens a form.
// Reading or receiving material never starts or completes a field evaluation.
export function applySubmittedDefaults({catalog,form,subject,state,draft,period}) {
 const data=state?.data,review=data?.submitted_assessment_defaults,schema=catalog?.forms?.[form];
 if(!review||review.version!==1||review.period!==period||review.criteria_version!==catalog.version||!schema||!draft?.data)return 0;
 const record=data.assessments?.[form+':'+subject];
 if(record?.completed||data.score_confirmation?.status==='CONFIRMED')return 0;
 const signed=(data.signed_receipts||[]).some(r=>(r.site_manager_signed_forms||r.signed_forms||[]).includes(form));
 if(signed)return 0;
 const files=new Map((data.files||[]).map(f=>[f.id,f]));let changed=0;
 for(const [id,item] of Object.entries(review.forms?.[form]||{})) {
  const q=schema.criteria.find(q=>q.id===id);if(!q||!item||typeof item.note!=='string'||!item.note.trim())continue;
  if(!Array.isArray(item.sources)||!item.sources.length||item.sources.some(s=>s.kind==='private_review'?!(review.private_sources||[]).includes(s.sha256):!files.has(s.id)||files.get(s.id).sha256!==s.sha256))continue;
  if(q.evidence.some(id=>data.evidence?.[id]?.hold))continue;
  const value=item.value;
  if(schema.scoring==='COMPLIANCE'?!['PASS','FAIL','NA'].includes(value):!Number.isInteger(value)||value<0||value>q.max_score)continue;
  const old=draft.data.answers?.[id],saved=record?.draft?.data?.answers?.[id];
  if(saved?.value!=null)continue;
  // A newly opened form may have a monthly opinion count; the verified site ledger takes precedence.
  if(old?.value!=null&&!(id==='p10'&&!record?.draft&&old.value===state.opinion_default?.score))continue;
  draft.baseData??=structuredClone(draft.data);draft.data.answers??={};
  const note=old?.note||'',extra='제출자료 확인: '+item.note.trim();
  draft.data.answers[id]={value,note:note.includes(extra)?note:note+(note?'\n\n':'')+extra};
  draft.changed=true;changed++;
 }
 return changed;
}

