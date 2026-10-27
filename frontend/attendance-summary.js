const DAY=86400000;
function dayNumber(value){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return null;
 const number=Date.parse(value+'T00:00:00Z');
 return Number.isFinite(number)&&new Date(number).toISOString().slice(0,10)===value?number/DAY:null;
}
const count=value=>Number.isSafeInteger(value)&&value>=0;
function collectedAt(value,source,today,now){
 if(typeof value!=='string'||!/(?:Z|[+-]\d{2}:\d{2})$/.test(value))return null;
 const stamp=Date.parse(value);if(!Number.isFinite(stamp)||stamp>now+300000)return null;
 const day=dayNumber(new Date(stamp+9*3600000).toISOString().slice(0,10));
 return day!==null&&day>=source&&day<=today?stamp:null;
}
export function attendanceSummary(attendance,today,now=Date.now()){
 const pending={state:'waiting',heading:'출역인원',people:null,note:'ERP 출역자료 수집을 기다리고 있습니다.'};
 const reference=dayNumber(today),source=dayNumber(attendance?.source_date);
 if(reference===null||source===null)return pending;
 const captured=collectedAt(attendance.captured_at,source,reference,now);
 if(source>reference||captured===null)return {...pending,state:'unverified',note:'출역자료의 기준일과 수집 시각을 확인하고 있습니다.'};
 const stamp=new Intl.DateTimeFormat('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Seoul'}).format(captured);
 if(source===reference){
  if(attendance.current!==true||!count(attendance.people))return {...pending,state:'unverified',note:'오늘 출역자료의 집계 결과를 확인하고 있습니다.'};
  const sites=count(attendance.site_count)?attendance.site_count+'개 현장 · ':'';
  return {state:'current',heading:'오늘 출역인원',people:attendance.people,note:sites+stamp+' 수집 기준'};
 }
 if(attendance.current===true||!count(attendance.last_people))return {...pending,state:'unverified',note:'최근 출역자료의 집계 결과를 확인하고 있습니다.'};
 const [year,month,day]=attendance.source_date.split('-');
 return {state:'previous',heading:Number(month)+'.'+Number(day)+' 출역인원',people:attendance.last_people,note:year+'.'+month+'.'+day+' 기준 · '+stamp+' 수집 · 오늘 자료 미수집'};
}
