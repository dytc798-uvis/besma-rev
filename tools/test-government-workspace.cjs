const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),R=process.argv[2],S=path.join(R,'frontend-release/.vercel/output/static');
const server=http.createServer((req,res)=>{let f=path.join(S,new URL(req.url,'http://local').pathname);if(!fs.existsSync(f)||fs.statSync(f).isDirectory())f=path.join(S,'index.html');res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg'})[path.extname(f)]||'application/octet-stream');fs.createReadStream(f).pipe(res)});
(async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port,b=await chromium.launch({channel:'msedge',headless:true}),checks=[];
for(const owner of [true,false]){const ctx=await b.newContext({viewport:{width:1440,height:1000}}),errors=[],adminRequests=[];
await ctx.addInitScript(()=>localStorage.setItem('besma_token','qa-synthetic-token'));
await ctx.route('https://api.besma.co.kr/**',async r=>{const u=new URL(r.request().url());let d={items:[]};
if(u.pathname==='/workspace/bootstrap')d={user:{name:'QA',role:owner?'HQ_SAFE':'HQ_OTHER'},permissions:{manage_government_forms:owner}};
else if(u.pathname==='/workspace/government-sites')d={items:[{name:'QA 관급 현장'}]};
else if(u.pathname==='/government-contact/access')d={allowed:true,side:'HQ',can_manage_forms:owner};
else if(u.pathname==='/government-contact/sites')d={items:[{site_id:1,site_name:'QA 관급 현장',unread_count:0}]};
else if(u.pathname.includes('/government-document-catalog'))d={items:[],total:0,public:0,private:0,public_candidates:0};
else if(u.pathname.includes('/government-folders'))d={folders:[]};
else if(u.pathname==='/collection-monitor/settings')d={revision:1,groups:[],items:[]};
if(/government-document-catalog|government-folders|collection-monitor\/settings/.test(u.pathname))adminRequests.push(u.pathname);
await r.fulfill({contentType:'application/json',body:JSON.stringify(d)});});
const p=await ctx.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'/workspace.html#government');await p.locator('#menus a').nth(7).waitFor();await p.getByRole('link',{name:/소통 활성/}).waitFor();
assert.equal(await p.locator('a[href="#government/settings"]').count(),owner?1:0);assert.equal(await p.locator('#menus a').count(),8);assert.equal(await p.locator('.gov-contact-menu').count(),0);
await p.locator('a[href="#government/communication"]').click();await p.locator('#gov-contact-hub .gov-contact-sites').waitFor();await p.waitForTimeout(700);assert.equal(await p.locator('#gov-contact-hub').count(),1);assert.equal(await p.locator('#gov-contact-hub .gov-contact-sites article').count(),1);
await p.goto(base+'/workspace.html#government/settings');if(owner){await p.locator('#gov-collection-settings h2').waitFor();await p.waitForTimeout(700);assert.equal(await p.locator('#gov-settings').count(),1);assert.equal(adminRequests.length,3);await p.screenshot({path:path.join(R,'qa/government-owner-settings.png'),fullPage:true});}else{await p.locator('.error').waitFor();assert.equal(adminRequests.length,0);assert.equal(await p.locator('#gov-settings').count(),0);}
assert.deepEqual(errors,[]);checks.push(owner?'owner: settings nested in 7 and communication stable':'HQ_OTHER: communication only, direct settings denied before loading catalogs');
for(const width of [390,320]){await p.setViewportSize({width,height:844});await p.goto(base+'/workspace.html#government/communication');await p.locator('#gov-contact-hub .gov-contact-sites').waitFor();assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}await ctx.close();}
await b.close();await new Promise(r=>server.close(r));fs.writeFileSync(path.join(R,'qa/government-ui-tests.json'),JSON.stringify({passed:true,checks},null,2));console.log('PASS government owner, HQ_OTHER, 390/320px and no duplicate menus');})().catch(e=>{console.error(e);process.exit(1)});
