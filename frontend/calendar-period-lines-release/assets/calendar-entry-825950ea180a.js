const token=localStorage.getItem('besma_token'),current=()=>token&&localStorage.getItem('besma_token')===token,make=(t,s)=>{const e=document.createElement(t);if(s)e.textContent=s;return e;};
function mount(){
 if(document.querySelector('.home-sidebar')){
  const box=make('section');box.id='home-calendar-shortcuts';box.className='home-calendar-shortcuts';box.setAttribute('aria-label','안전보건 업무');
  for(const [name,label,path]of[['opinion','근로자의견','/workspace.html#voice'],['mine','내 점검','/inspection-calendar.html?mine=1'],['calendar','점검계획','/inspection-calendar.html']]){const a=make('a'),title=make('span',label),status=make('b',name==='opinion'?'시행중':current()?'캘린더 보기':'로그인 필요');a.dataset.calendarShortcut=name;a.href=current()?path:'/login?form=1';a.append(title,status);box.append(a);}
  document.querySelector('.home-sidebar .attendance-block')?.after(box);
  // The dedicated entries replace the old duplicate task summaries.
  for(const id of ['today-opinion-tasks','today-inspection-tasks']){const old=document.getElementById(id);if(old)old.classList.add('calendar-replaced-summary');}
 }
 if(['half-year-reader.html','inspection-plan.html'].some(p=>location.pathname.endsWith(p))){const nav=make('a','업무툴 캘린더 보기');nav.className='assessment-calendar-entry';nav.href='/inspection-calendar.html';const host=document.querySelector('main')||document.body;host.prepend(nav);}
}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',mount,{once:true}):mount();
