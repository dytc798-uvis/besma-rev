export function inspectionMonth(value){return typeof value==='string'&&/^20\d{2}-(0[1-9]|1[0-2])$/.test(value)?value:null;}
export function inspectionPlanId(value){return typeof value==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value)?value:null;}
export function inspectionEntry(search){
 const p=new URLSearchParams(search),requested=['plan','month','return'].some(k=>p.has(k));
 if(!requested)return {requested:false,valid:true};
 if(['plan','month','return'].some(k=>p.getAll(k).length>1)||!inspectionPlanId(p.get('plan'))||!inspectionMonth(p.get('month')))return {requested:true,valid:false};
 return {requested:true,valid:true,plan:p.get('plan'),month:p.get('month'),back:p.get('return')||'/company.html'};
}
export function inspectionHref(row){
 if(!inspectionPlanId(row?.public_id)||!inspectionMonth(row?.scheduled_date?.slice(0,7)))throw Error('점검계획의 현장·날짜를 확인해야 합니다.');
 return '/inspection-plan.html?'+new URLSearchParams({plan:row.public_id,month:row.scheduled_date.slice(0,7),return:'/company.html'});
}
