import {chromium} from 'file:///D:/JSI/besma-safety-ledgers-deploy/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';import path from 'node:path';import crypto from 'node:crypto';
const root='D:/JSI/workfiles/besma-government-release-20261008';const staticRoot=root+'/frontend-release/.vercel/output/static';
const overview=JSON.parse(await fs.readFile(root+'/compact/overview.json','utf8'));const other=JSON.parse(await fs.readFile(root+'/config-other-overview.json','utf8'));
const initialSettings=JSON.parse(await fs.readFile(root+'/compact/settings.json','utf8'));
const codes=overview.documents.map(d=>d.code);const publicFolder='관급 공개 양식/02. 안전점검';
const bytes=Buffer.from('manual NAS browser fixture');const hash=crypto.createHash('sha256').update(bytes).digest('hex');
let folderVisible=false,fileEnabled=true;const makeCatalog=()=>({total:2,public:folderVisible&&fileEnabled?1:0,private:folderVisible&&fileEnabled?1:2,public_candidates:1,items:[{relative_path:'02. 안전점검/공개양식.xlsx',folder:'02. 안전점검',name:'공개양식.xlsx',visibility:folderVisible&&fileEnabled?'PUBLIC':'PRIVATE',recommended_visibility:'PUBLIC_CANDIDATE',public_copy_prepared:true,public_folder_visible:folderVisible,file_enabled:fileEnabled},{relative_path:'내부/대외비.xlsx',folder:'내부',name:'대외비.xlsx',visibility:'PRIVATE',recommended_visibility:'PRIVATE',public_copy_prepared:false,public_folder_visible:false,file_enabled:false}]});
const browser=await chromium.launch({headless:true});const results=[];
for(const scenario of [{name:'hq-desktop',role:'HQ_SAFE',width:1440,target:'/hq-safe/documents'},{name:'hq-narrow',role:'HQ_SAFE',width:1024,target:'/hq-safe/documents'},{name:'hq-mobile',role:'HQ_SAFE',width:390,target:'/hq-safe/documents'},{name:'settings',role:'HQ_SAFE',width:1440,target:'/hq-safe/settings'},{name:'settings-mobile',role:'HQ_SAFE',width:390,target:'/hq-safe/settings'},{name:'site',role:'SITE',width:390,target:'/site/documents'},{name:'readonly',role:'HQ_OTHER',width:1440,target:'/hq-safe/documents'}]){
 const context=await browser.newContext({viewport:{width:scenario.width,height:950}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));let msgs=[];let settings=structuredClone(initialSettings);folderVisible=false;fileEnabled=true;
 await page.addInitScript(()=>{const files=new Map();window.__nasFiles=files;const directory=(prefix='')=>({name:prefix?'관급':'★월간 자료 취합',getDirectoryHandle:async name=>directory(prefix+name+'/'),getFileHandle:async(name,options={})=>{const key=prefix+name;if(!files.has(key)&&!options.create)throw new DOMException('missing','NotFoundError');if(!files.has(key))files.set(key,new Uint8Array());return {getFile:async()=>new File([files.get(key)],name),createWritable:async()=>({write:async b=>files.set(key,b),close:async()=>{},abort:async()=>{}})};}});window.showDirectoryPicker=async()=>directory();});
 await page.route('https://www.besma.co.kr/**',async route=>{let rel=new URL(route.request().url()).pathname.slice(1);if(!rel||!path.extname(rel))rel='index.html';try{await route.fulfill({body:await fs.readFile(path.join(staticRoot,rel)),contentType:rel.endsWith('.js')?'application/javascript':rel.endsWith('.css')?'text/css':rel.endsWith('.svg')?'image/svg+xml':rel.endsWith('.png')?'image/png':'text/html'});}catch{await route.fulfill({status:404,body:''});}});
 await page.route('https://api.besma.co.kr/**',async route=>{const url=new URL(route.request().url());const p=url.pathname;let body={items:[],sites:[],requirements:[],summary:{},rows:[],total:0};
  if(p==='/auth/login')body={access_token:'synthetic-ui-fixture',token_type:'bearer'};
  if(p==='/auth/me')body={id:999999,name:'검증 계정',login_id:'fixture',role:scenario.role,ui_type:scenario.role==='SITE'?'SITE':'HQ_SAFE',site_id:scenario.role==='SITE'?74:null,person_id:null,must_change_password:false,can_role_preview:false};
  if(p==='/collection-monitor/settings'){
   if(route.request().method()==='PUT'){settings=route.request().postDataJSON();settings.revision++;settings.items=settings.items.map((item,index)=>({...item,code:item.code||'GOV_CUSTOM_UI'+index,group_id:['EVENT','ADHOC'].includes(item.frequency)?'EVENT':item.frequency==='WEEKLY'?'WEEKLY':'MONTHLY'}));}body=settings;
  }
  if(p==='/collection-monitor/site-configuration')body={groups:settings.groups,items:settings.items};
  if(p==='/collection-monitor/context')body={role:scenario.role,can_read_monitor:scenario.role!=='SITE',can_manage:scenario.role==='HQ_SAFE',channel:scenario.role==='SITE'?'BESMA':'NAVERWORKS'};
  if(p==='/collection-monitor/overview')body=url.searchParams.get('scope')==='other'?other:overview;
  if(p==='/sites')body=overview.sites;
  if(p==='/government-contact/access')body={allowed:scenario.role!=='HQ_OTHER',side:scenario.role==='SITE'?'SITE':'HQ',site_id:74,site_name:overview.sites[0].site_name};
  if(p==='/government-contact/sites')body={items:overview.sites.map(s=>({site_id:s.id,site_name:s.site_name,unread_count:0}))};
  if(p==='/government-contact/messages'){
   if(route.request().method()==='POST'){msgs.push({id:msgs.length+1,sender_side:scenario.role==='SITE'?'SITE':'HQ',sender_name:'검증 계정',body:route.request().postDataJSON().body,created_at:'2026-10-08T03:00:00',read_at:null});body={id:msgs.length};}
   else body={site_id:Number(url.searchParams.get('site_id')||74),site_name:overview.sites[0].site_name,has_more:false,items:msgs};
  }
  if(p==='/document-explorer/government-document-catalog')body=makeCatalog();
  if(p==='/document-explorer/government-folders'){if(route.request().method()==='PUT')folderVisible=route.request().postDataJSON().visible;body={folders:[{folder:publicFolder,visible:folderVisible}]};}
  if(p==='/document-explorer/government-files'){fileEnabled=route.request().postDataJSON().visible;body={visible:fileEnabled};}
  if(p==='/documents/requirements/status')body={items:overview.documents.map((d,i)=>({requirement_id:i+1,document_type_code:d.code,title:d.title,is_required:true,status:'NOT_SUBMITTED',current_cycle_status:'NOT_SUBMITTED',frequency:d.frequency})),summary:{},completion_upload_enabled:false};
  if(p==='/collection-monitor/nas-export')body={unavailable_count:0,items:[{key:'431-1-'+hash,sha256:hash,size:bytes.length,relative_path:'3. 위험성평가/관급/26.10월/24028 검증현장/위험성평가/문서431_v1.txt'}]};
  if(p.startsWith('/collection-monitor/nas-files/')){await route.fulfill({body:bytes,contentType:'application/octet-stream'});return;}
  if(p==='/collection-monitor/report.xlsx'){await route.fulfill({body:await fs.readFile(root+'/report.xlsx'),contentType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});return;}
  await route.fulfill({json:body});
 });
 await page.goto('https://www.besma.co.kr/login?redirect='+encodeURIComponent(scenario.target));await page.locator('input[type=text]').first().fill('fixture');await page.locator('input[type=password]').fill('synthetic-fixture');await page.locator('button[type=submit]').click();await page.waitForURL('**'+scenario.target);await page.waitForTimeout(1300);
 if(scenario.name.startsWith('settings')){
  await page.locator('#gov-collection-settings table tbody tr').first().waitFor();
  if(await page.locator('#gov-collection-settings table tbody tr').count()!==24)throw Error('settings document catalog');
  await page.getByRole('textbox',{name:'구분명 MONTHLY',exact:true}).fill('월간 취합');
  await page.getByRole('textbox',{name:'서류명 GOV_RISK_MONTHLY',exact:true}).fill('월간 위험성평가');
  await page.getByRole('button',{name:'취합 서류 추가',exact:true}).click();
  await page.getByRole('textbox',{name:'서류명 신규',exact:true}).fill('새 점검 확인서');
  await page.getByRole('combobox',{name:'제출 주기 신규',exact:true}).selectOption('WEEKLY');
  await page.getByRole('button',{name:'취합 설정 저장',exact:true}).click();
  await page.getByText('저장했습니다. 현장 제출 목록과 다음 NAS 저장에 적용됩니다.',{exact:true}).waitFor();
  if(await page.getByRole('button',{name:'취합 설정 저장',exact:true}).isDisabled())throw Error('save remains disabled');
  await page.locator('#gov-settings').getByRole('button',{name:'목록 새로고침',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#gov-collection-settings table tbody')?.children.length===25);
  if(await page.getByRole('textbox',{name:'구분명 MONTHLY',exact:true}).inputValue()!=='월간 취합')throw Error('group rename persistence');
  if(!settings.items.some(i=>i.title==='새 점검 확인서'&&i.frequency==='WEEKLY'&&i.collection_folder==='새 점검 확인서'))throw Error('new title folder binding');
  await page.locator('#gov-catalog table tbody tr').first().waitFor();await page.locator('#gov-settings summary').click();await page.getByRole('button',{name:'비공개 · 공개로 변경',exact:true}).click();await page.getByRole('button',{name:'제공 허용 · 제한하기',exact:true}).click();await page.getByRole('button',{name:'제공 제한 · 허용하기',exact:true}).first().click();
  await page.waitForFunction(()=>document.querySelector('#gov-settings')?.textContent.includes('현재 공개 1건'));
 }else if(scenario.role==='SITE'){await page.locator('#gov-site-priority').waitFor();if(await page.locator('#gov-site-priority .gov-folder').count()!==9)throw Error('priority count');}
 else{
  await page.locator('#collection-monitor').waitFor();
  await page.locator('.cm-matrix').waitFor();
  if(JSON.stringify((await page.locator('.cm-matrix thead tr').first().locator('th').allTextContents()).slice(1))!==JSON.stringify(['월간','주간','착공시']))throw Error('group ordering labels');
  if(await page.locator('.cm-matrix tbody tr').count()!==6)throw Error('matrix sites');
  const headers=await page.locator('.cm-matrix thead tr').nth(1).locator('th').allTextContents();if(!headers.includes('PCM 자료')||!headers.includes('산업안전보건관리비'))throw Error('requested columns absent');
  if(scenario.width>700){
   await page.locator('.cm-matrix-wrap').scrollIntoViewIfNeeded();
   const layout=await page.evaluate(()=>{const w=document.querySelector('.cm-matrix-wrap'),table=w.querySelector('table'),head=table.querySelector('thead');const column=table.querySelector('td:first-child');const before=head.getBoundingClientRect().top;w.scrollTop=100;w.scrollLeft=100;return {before,top:head.getBoundingClientRect().top,left:column.getBoundingClientRect().left,wrapLeft:w.getBoundingClientRect().left,headCss:getComputedStyle(head).position,columnCss:getComputedStyle(column).position,canScroll:w.scrollHeight>w.clientHeight,tableWidth:table.getBoundingClientRect().width,colWidth:column.getBoundingClientRect().width,scrollTop:w.scrollTop,scrollLeft:w.scrollLeft};});
   if(layout.headCss!=='sticky'||layout.columnCss!=='sticky'||Math.abs(layout.top-layout.before)>2||Math.abs(layout.left-layout.wrapLeft)>2||!layout.canScroll||layout.colWidth>210)throw Error('freeze/compact layout '+JSON.stringify(layout));
   if(scenario.name==='hq-desktop'){
    const before=await page.evaluate(()=>{const w=document.querySelector('.cm-matrix-wrap');return {top:w.scrollTop,left:w.scrollLeft};});
    await page.clock.install();await page.clock.fastForward(31000);await page.waitForTimeout(100);
    const after=await page.evaluate(()=>{const w=document.querySelector('.cm-matrix-wrap');return {top:w.scrollTop,left:w.scrollLeft};});if(JSON.stringify(before)!==JSON.stringify(after))throw Error('poll reset scroll');
   }
  }

  if(await page.locator('.cm-matrix tbody tr').first().locator('td').count()!==10)throw Error('matrix document columns');
  if((await page.locator('#cm-results').innerText()).includes('취합률'))throw Error('government rate overview still visible');
  if((await page.locator('#cm-results').innerText()).includes('김포고촌'))throw Error('team5 site in government matrix');
  if(!(await page.locator('#cm-results').innerText()).includes('소장:')||!(await page.locator('#cm-results').innerText()).includes('연락처:'))throw Error('contact labels');
  if(await page.locator('.cm-matrix tbody tr').first().locator('td').nth(4).locator('.cm-period-status').count()!==2)throw Error('weekly periods');
if(await page.locator('#cm-results table tbody tr').count()!==6)throw Error('default gov scope');
  if(scenario.role==='HQ_SAFE'){
   const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'취합현황 보고서 다운로드',exact:true}).click();await downloaded;await page.getByRole('button',{name:'닫기',exact:true}).click();
   await page.getByRole('button',{name:'NAS에 저장',exact:true}).click();await page.getByText('NAS 저장 완료:',{exact:false}).waitFor();await page.getByRole('button',{name:'닫기',exact:true}).click();
   await page.getByRole('button',{name:'NAS에 저장',exact:true}).click();await page.getByText('기존 동일 파일 1건.',{exact:false}).waitFor();await page.getByRole('button',{name:'닫기',exact:true}).click();
   if(await page.evaluate(()=>window.__nasFiles.size)!==1)throw Error('duplicate NAS save');
   await page.getByRole('button',{name:'기타 현장',exact:true}).click();await page.waitForTimeout(200);if(await page.locator('#cm-results table tbody tr').count()!==60)throw Error('other active scope');await page.getByRole('button',{name:'관급공사',exact:true}).click();
  }else if(await page.getByRole('button',{name:'NAS에 저장',exact:true}).count()||await page.getByRole('button',{name:'취합현황 보고서 다운로드',exact:true}).count())throw Error('readonly download button exposed');
 }
 if(scenario.role!=='HQ_OTHER'){
  await page.locator('.gov-contact-page').click();await page.getByRole('textbox',{name:'전달 내용'}).fill('양방향 소통 검증');await page.getByRole('button',{name:'등록',exact:true}).click();await page.locator('.gov-message-list').getByText('양방향 소통 검증',{exact:true}).waitFor();await page.getByRole('button',{name:'닫기',exact:true}).click();
 }
 await page.screenshot({path:root+'/compact/'+scenario.name+'.png',fullPage:true});results.push({...scenario,errors});await context.close();
}
await browser.close();await fs.writeFile(root+'/compact/ui-regression.json',JSON.stringify({scope:'original operating Vue assets plus isolated additive release and synthetic authenticated API fixtures; manual NAS File System Access handles simulated',results},null,2));console.log(JSON.stringify(results));if(results.some(r=>r.errors.length))process.exit(1);
