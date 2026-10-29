export function createSiteInfoEditor({site,request,onSaved,onNotice,isCurrent=()=>true}){
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
 const section=el('section');section.className='site-info-editor site-correction-editor';
 const toggle=el('button','현장 정보 수정');toggle.type='button';toggle.className='site-info-toggle';toggle.setAttribute('aria-expanded','false');
 const form=el('form');form.className='missing-info-fields site-correction-fields';form.hidden=true;
 const address=el('input');address.type='text';address.maxLength=400;address.required=true;address.value=site.address||'';address.autocomplete='off';
 const description=el('textarea');description.maxLength=1200;description.rows=4;description.value=site.description||'';description.placeholder='현장 소개나 찾아갈 때 참고할 내용을 적으세요.';
 function field(name,input){const label=el('label');label.append(el('span',name),input);form.append(label);input.setAttribute('aria-label',name);}
 field('현장 주소',address);field('현장 설명',description);
 const state=el('p');state.setAttribute('role','status');const actions=el('div');actions.className='site-info-actions';const save=el('button','저장'),cancel=el('button','취소');save.type='submit';cancel.type='button';actions.append(save,cancel);form.append(state,actions);section.append(toggle,form);
 let busy=false,key=crypto.randomUUID(),last=null;
 const dirty=()=>address.value.trim()!==(site.address||'')||description.value.trim()!==(site.description||'');
 const update=()=>{section.dataset.dirty=String(dirty());state.textContent='';};address.oninput=description.oninput=update;
 toggle.onclick=()=>{form.hidden=!form.hidden;toggle.setAttribute('aria-expanded',String(!form.hidden));if(!form.hidden)address.focus({preventScroll:true});};
 cancel.onclick=()=>{if(busy)return;address.value=site.address||'';description.value=site.description||'';section.dataset.dirty='false';form.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus({preventScroll:true});};
 form.onsubmit=async event=>{event.preventDefault();if(busy||!isCurrent())return;if(!address.value.trim()){state.textContent='주소를 입력해 주세요.';address.focus();return;}if(!dirty()){cancel.click();return;}
  const current=JSON.stringify([address.value.trim(),description.value.trim()]);if(last!==current){key=crypto.randomUUID();last=current;}
  const body={request_id:key,expected_revision:site.edit_revision||0,expected_address:site.address||'',expected_description:site.description||'',address:address.value.trim(),description:description.value.trim()};
  busy=true;section.dataset.busy='true';for(const input of[address,description,save,cancel,toggle])input.disabled=true;state.textContent='저장 중…';
  try{const receipt=await request('/workspace/sites/'+encodeURIComponent(site.code)+'/info',{method:'PUT',body:JSON.stringify(body)});if(!isCurrent())return;if(receipt.saved!==true||receipt.site_code!==site.code)throw Error('저장 결과를 확인하지 못했습니다.');section.dataset.dirty='false';section.dataset.busy='false';await onSaved();onNotice('현장 정보를 저장했습니다.');}
  catch(error){if(isCurrent()){state.textContent=error.message||'저장하지 못했습니다. 입력 내용은 남아 있습니다.';onNotice(state.textContent);}}
  finally{busy=false;section.dataset.busy='false';for(const input of[address,description,save,cancel,toggle])input.disabled=false;}
 };
 return section;
}
