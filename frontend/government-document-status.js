const counts=v=>Number.isSafeInteger(v)&&v>=0;
export function validWorkDate(value){if(typeof value!=='string'||!/^20\d{2}-(0[1-9]|1[0-2])-\d{2}$/.test(value))return false;const d=new Date(value+'T00:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===value;}
export async function loadGovernmentDocuments({api,token,month,codes,current=()=>true}){
 if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month)||!Array.isArray(codes))return {state:'UNAVAILABLE'};
 if(!codes.length)return {state:'NOT_APPLICABLE'};
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000),owned=()=>current()&&localStorage.getItem('besma_token')===token;
 async function get(path){if(!owned())throw Error('superseded');const r=await fetch(api+path,{headers:{Authorization:'Bearer '+token},credentials:'omit',redirect:'error',cache:'no-store',signal:controller.signal});if(!owned())throw Error('superseded');if(!r.ok)throw Error(r.status===401?'AUTH_REQUIRED':r.status===403?'FORBIDDEN':'UNAVAILABLE');return r.json();}
 try{
  const context=await get('/collection-monitor/context');
  if(context.can_read_monitor!==true||!['HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'].includes(context.role)||context.read_only!==false)return {state:'FORBIDDEN'};
  const value=await get('/collection-monitor/overview?'+new URLSearchParams({month,scope:'government'}));if(!owned())return null;
  if(value.scope!=='government'||value.month!==month||!validWorkDate(value.as_of_date)||!Array.isArray(value.sites))return {state:'UNAVAILABLE'};
  const seen=new Set();
  for(const site of value.sites){if(typeof site.site_code!=='string'||seen.has(site.site_code)||site.channel!=='BESMA'||site.active!==true||!Array.isArray(site.cells))return {state:'UNAVAILABLE'};seen.add(site.site_code);const cells=new Set();for(const cell of site.cells){if(typeof cell.code!=='string'||!/^GOV_[A-Z0-9_]+$/.test(cell.code)||cells.has(cell.code)||typeof cell.title!=='string'||typeof cell.known!=='boolean'||!counts(cell.expected)||!Array.isArray(cell.periods))return {state:'UNAVAILABLE'};cells.add(cell.code);}}
  return {state:'VERIFIED',month,asOf:value.as_of_date,sites:value.sites.filter(s=>codes.includes(s.site_code)),codes:[...new Set(codes)]};
 }catch(error){return owned()?{state:['AUTH_REQUIRED','FORBIDDEN'].includes(error.message)?error.message:'UNAVAILABLE'}:null;}
 finally{clearTimeout(timer);}
}
const states={NOT_SUBMITTED:'미제출',REJECTED:'반려 · 보완 필요',SUBMITTED:'검토할 문서',IN_REVIEW:'검토할 문서',UNDER_REVIEW:'검토할 문서',RESUBMITTED:'검토할 문서'};
export function governmentTasks(snapshot){
 if(snapshot?.state!=='VERIFIED')return {state:snapshot?.state||'UNAVAILABLE',tasks:[],unknown:[]};
 const tasks=[],unknown=[];
 for(const code of snapshot.codes){const site=snapshot.sites.find(s=>s.site_code===code);if(!site||!site.cells.some(c=>c.expected>0)){unknown.push({siteCode:code,title:'현장 취합대상 확인 필요'});continue;}
  for(const cell of site.cells){if(cell.expected===0)continue;const periods=new Set();if(!cell.known||cell.periods.length!==cell.expected||cell.periods.some(p=>typeof p.period!=='string'||periods.has(p.period)||!periods.add(p.period))){unknown.push({siteCode:code,siteName:site.site_name,title:cell.title,documentCode:cell.code});continue;}
   for(const p of cell.periods){if(['APPROVED','NOT_REQUIRED'].includes(p.status))continue;if(!states[p.status]){unknown.push({siteCode:code,siteName:site.site_name,title:cell.title,documentCode:cell.code,period:p.period});continue;}
    tasks.push({siteCode:code,siteName:site.site_name,title:cell.title,documentCode:cell.code,period:p.period,status:p.status,label:states[p.status],instanceId:Number.isSafeInteger(p.instance_id)&&p.instance_id>0?p.instance_id:null,dueDate:validWorkDate(p.due_date)?p.due_date:null,overdue:validWorkDate(p.due_date)&&p.due_date<snapshot.asOf});
   }
  }
 }
 return {state:'VERIFIED',tasks,unknown,month:snapshot.month};
}
export function governmentTaskHref(task,month,returnTo='/'){
 if(task.instanceId)return '/hq-safe/document-instances/'+task.instanceId+'?'+new URLSearchParams({from_workspace:'1',return:returnTo});
 if(!task.documentCode)return '/workspace.html#government';
 return '/hq-safe/documents?'+new URLSearchParams({collection:'1',work_entry:'1',month,site:task.siteCode,document_code:task.documentCode,...(task.period?{period:task.period}:{}),return:returnTo});
}
