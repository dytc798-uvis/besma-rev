// Uses the existing missing-info endpoint and its original revision/permission rules.
export function hasMissingSiteInfo(site){return !String(site.address||'').trim()||(site.contacts||[]).some(c=>c.contact_id&&(!String(c.phone||'').trim()||(!String(c.rank||'').trim()&&!String(c.role||'').split('·').includes('소장'))));}
export function createMissingInfoEditor({site,request,onSaved,onNotice,isCurrent=()=>true,open=false}){
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
 const section=el('section');section.className='site-info-editor';const box=el('div');box.className='missing-info-fields';box.hidden=!open;const fields=[];
 function field(label,key,maxLength,contact=null){const row=el('label'),input=el('input');input.type=key==='phone'?'tel':'text';input.maxLength=maxLength;input.autocomplete='off';input.setAttribute('aria-label',label);input.oninput=()=>{section.dataset.dirty=String(fields.some(f=>f.input.value.trim()));};row.append(el('span',label),input);box.append(row);fields.push({key,input,contact});}
 if(!String(site.address||'').trim())field('주소','address',400);
 for(const c of site.contacts||[]){if(!c.contact_id)continue;const name=c.name||c.role||'담당자';if(!String(c.phone||'').trim())field(name+' 전화번호','phone',40,c);if(!String(c.rank||'').trim()&&!String(c.role||'').split('·').includes('소장'))field(name+' 직급','rank',20,c);}
 if(!fields.length)return null;
 const edit=el('button','누락 정보 보완');edit.type='button';edit.setAttribute('aria-expanded',String(open));edit.onclick=()=>{box.hidden=!box.hidden;edit.setAttribute('aria-expanded',String(!box.hidden));if(!box.hidden)fields[0].input.focus({preventScroll:true});};
 box.prepend(el('p','빈 항목을 입력한 뒤 저장하세요.'));
 const actions=el('div');actions.className='site-info-actions';const save=el('button','저장'),cancel=el('button','취소');save.type=cancel.type='button';let busy=false;
 save.onclick=async()=>{
  if(busy||!isCurrent())return;const body={expected_revision:site.info_revision,contacts:[]},contacts=new Map();let entered=0;
  for(const f of fields){const value=f.input.value.trim();if(!value)continue;
   if(f.key==='phone'&&(!/^[+0-9() -]+$/.test(value)||value.replace(/\D/g,'').length<4||value.replace(/\D/g,'').length>20)){onNotice('전화번호를 확인해 주세요.');f.input.focus();return;}
   if(f.key==='rank'&&!/^[가-힣A-Za-z ]+$/.test(value)){onNotice('직급을 확인해 주세요.');f.input.focus();return;}
   entered++;if(f.key==='address')body.address=value;else{let c=contacts.get(f.contact.contact_id);if(!c){c={contact_id:f.contact.contact_id,expected_rank_revision:f.contact.rank_revision||0};contacts.set(c.contact_id,c);}c[f.key]=value;}
  }
  if(!entered){onNotice('보완할 정보를 입력해 주세요.');return;}body.contacts=[...contacts.values()];busy=true;section.dataset.busy='true';for(const f of fields)f.input.disabled=true;save.disabled=cancel.disabled=edit.disabled=true;
  try{await request('/workspace/sites/'+encodeURIComponent(site.code)+'/missing-info',{method:'PUT',body:JSON.stringify(body)});if(!isCurrent())return;section.dataset.dirty='false';await onSaved();if(isCurrent())onNotice('누락 정보를 저장했습니다.');}
  catch(error){if(isCurrent())onNotice(error.message);}
  finally{busy=false;section.dataset.busy='false';for(const f of fields)f.input.disabled=false;save.disabled=cancel.disabled=edit.disabled=false;}
 };
 cancel.onclick=()=>{for(const f of fields)f.input.value='';section.dataset.dirty='false';box.hidden=true;edit.setAttribute('aria-expanded','false');edit.focus({preventScroll:true});};
 actions.append(save,cancel);box.append(actions);section.append(edit,box);return section;
}
