import fs from 'node:fs/promises';import path from 'node:path';import crypto from 'node:crypto';
import{transform}from 'esbuild';
const [R,baselineRoot]=process.argv.slice(2);if(!R||!baselineRoot)throw Error('Usage: npm run build -- <task-root> <verified-baseline-static>');const F=R+'/release/frontend',O=R+'/frontend-release/.vercel/output',S=O+'/static';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex'),baseline=JSON.parse(await fs.readFile(R+'/qa/frontend-baseline.json','utf8'));
const original=await fs.readFile(baselineRoot+'/index.html','utf8');
for(const[name,h]of Object.entries(baseline))if(name!=='index.html'&&hash(await fs.readFile(S+'/'+name))!==h)throw Error('Preserved file changed: '+name);
const assets={};
for(const name of ['workspace.css','company.css','workspace-legacy.css','collection-monitor.css','government-workspace.css','government-workspace.js','map-teams.js','company-map-region.js','company-map-photos.js','company-map.js','company-home.js','customer-policy.js','workspace.js','workspace-nav.js']){
 let source=await fs.readFile(F+'/'+name,'utf8');for(const[k,v]of Object.entries(assets))source=source.replaceAll('/assets/'+k,'/'+v);
 const result=await transform(source,{loader:name.endsWith('css')?'css':'js',target:'es2022',minify:true});const target='assets/'+name.replace(/\.(js|css)$/,'-'+hash(result.code).slice(0,12)+'.$1');await fs.writeFile(S+'/'+target,result.code);assets[name]=target;
}
for(const name of ['workspace.html','company.html']){let html=await fs.readFile(F+'/'+name,'utf8');for(const[k,v]of Object.entries(assets))html=html.replaceAll('/assets/'+k,'/'+v);await fs.writeFile(S+'/'+name,html);}
await fs.cp(F+'/workspace-assets',S+'/workspace-assets',{recursive:true});
let legacyScripts=[...original.matchAll(/<script\b[^>]*type="module"[^>]*src="([^"]+)"[^>]*><\/script>/g)].map(m=>m[1]);
if(!legacyScripts.length)throw Error('No verified legacy scripts found');
// Keep every original artifact intact, but seal HQ routes in a derived router bundle.
// The guard runs after the existing authentication/onboarding checks and before mounting.
const originalMain='/assets/index-Deu6IP5r.js',originalName=path.basename(originalMain);
const sourceBundle=await fs.readFile(S+originalMain,'utf8');
const anchor='const l=((g=i.user)==null?void 0:g.role)||"";';
if(sourceBundle.split(anchor).length!==2)throw Error('Production route guard anchor changed');
const allowed='^/hq-safe/(functional-eval(?:-monitoring|-rewards-sanctions|/grade-report)?|documents(?:/.*)?|document-explorer|document-instances/.*|government-contact|communications|safety-policy-goals|user-guide|google-feedback|worker-voice)/?$';
const seal=`if(i.isAuthenticated&&["HQ_SAFE","HQ_SAFE_ADMIN","SUPER_ADMIN","ACCIDENT_ADMIN","HQ_OTHER","FUNCTIONAL_EVAL_VIEWER","HQ_BUDGET_ESTIMATE","HQ_OUTSOURCING_PURCHASE"].includes(i.user?.role)&&["HQ_SAFE","HQ_OTHER"].includes(i.user?.ui_type)&&/^\\/hq-(safe|other)(\\/|$)/.test(a.path)&&!new RegExp(${JSON.stringify(allowed)}).test(a.path)){document.documentElement.classList.add("besma-route-gate");window.location.replace("/");t(false);return}`;
let guarded=sourceBundle.replace(anchor,anchor+seal);const fingerprint=hash(guarded).slice(0,12),mainName='index-workspace-'+fingerprint+'.js';
for(const name of ['LawRegisterPage-S5I_OeWG.js','ServiceEntryPage-D6PI_M8c.js']){
 const related=await fs.readFile(S+'/assets/'+name,'utf8');if(!related.includes(originalName))throw Error('Related module import changed');
 const derived=name.replace(/\.js$/,'-workspace-'+fingerprint+'.js');await fs.writeFile(S+'/assets/'+derived,related.replaceAll(originalName,mainName));guarded=guarded.replaceAll(name,derived);
}
await fs.writeFile(S+'/assets/'+mainName,guarded);legacyScripts=legacyScripts.map(src=>src===originalMain?'/assets/'+mainName:src==='/assets/government-workspace-644ea612d669.js'?'/'+assets['government-workspace.js']:src);
const bootSource=(await fs.readFile(F+'/workspace-boot.js','utf8')).replace('__BESMA_LEGACY_SCRIPTS__',JSON.stringify(legacyScripts)).replace('__BESMA_NAV_SCRIPT__',JSON.stringify('/'+assets['workspace-nav.js']));
const boot=(await transform(bootSource,{loader:'js',target:'es2022',minify:true})).code;
const gate='<style>.besma-route-gate #app,.besma-login-preparing #app{visibility:hidden!important}#besma-route-status{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;gap:12px;background:#173544;color:#fff;font:15px sans-serif;z-index:9999}</style>';
const index=original.replace(/<script\b[^>]*type="module"[^>]*src="[^"]+"[^>]*><\/script>/g,'').replace('<head>',`<head>${gate}<script>${boot}</script><link rel="stylesheet" href="/${assets['workspace-legacy.css']}">`);await fs.writeFile(S+'/index.html',index);
const config=JSON.parse(await fs.readFile(O+'/config.json','utf8'));config.routes=config.routes.filter(x=>x.src!=='/'&&x.src!=='/company.html');config.routes.unshift({src:'/',dest:'/company.html'});await fs.writeFile(O+'/config.json',JSON.stringify(config));
await fs.writeFile(R+'/qa/frontend-build.json',JSON.stringify({assets,index_sha256:hash(index),route_guard_bundle:'assets/'+mainName,route_guard_sha256:hash(guarded),baseline_index_sha256:baseline['index.html'],preserved_files:Object.keys(baseline).length-1,version:'2026.10.26.12'},null,2));console.log('BESMA workspace build passed; existing assets preserved; sealed HQ routes cannot mount.');
