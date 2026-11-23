import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url)),source=path.join(root,'calendar-role-dashboard-release');
const baseline=JSON.parse(fs.readFileSync(path.join(source,'baseline.json'),'utf8')),overlay=JSON.parse(fs.readFileSync(path.join(source,'overlay.json'),'utf8'));
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
assert.equal(baseline.origin,'https://www.besma.co.kr');assert.equal(baseline.schema,1);assert(baseline.files.length>800&&baseline.files.length<5000);
assert.equal(sha(fs.readFileSync(path.join(root,overlay.source_file),'utf8').replace(/\r\n/g,'\n')),overlay.source_normalized_sha256);
const local=process.argv.indexOf('--baseline'),arg=process.argv.indexOf('--output');
const output=arg<0?path.join(root,'.vercel/output'):path.resolve(process.argv[arg+1]);
const cache=local<0?path.join(root,'.vercel/public-baseline',baseline.deployment):path.resolve(process.argv[local+1]);
assert(!fs.existsSync(output),'Inspect existing output before rebuilding');
const seen=new Set();let next=0,verified=0;
for(const row of baseline.files){assert(typeof row.path==='string'&&!row.path.includes('\\')&&!path.posix.isAbsolute(row.path));assert(!row.path.split('/').some(x=>x===''||x==='.'||x==='..'));assert(!seen.has(row.path));seen.add(row.path);assert(/^[a-f0-9]{64}$/.test(row.sha256)&&Number.isSafeInteger(row.size)&&row.size>=0&&row.size<=16*1024*1024);}
async function obtain(row){
 let raw;const cached=path.join(cache,row.path);
 if(local>=0){assert(fs.lstatSync(cached).isFile()&&!fs.lstatSync(cached).isSymbolicLink());raw=fs.readFileSync(cached);}
 else if(fs.existsSync(path.join(source,'baseline-additions',row.path)))raw=fs.readFileSync(path.join(source,'baseline-additions',row.path));
 else if(row.path.endsWith('.html'))raw=fs.readFileSync(path.join(source,'pages',row.path));
 else if(fs.existsSync(cached)){assert(fs.lstatSync(cached).isFile()&&!fs.lstatSync(cached).isSymbolicLink());raw=fs.readFileSync(cached);}
 else{
  const url=new URL(row.path.split('/').map(encodeURIComponent).join('/'),baseline.origin+'/');assert.equal(url.origin,baseline.origin);let error;
  for(let attempt=0;attempt<3;attempt++){
   try{const response=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(25000)});assert(response.ok,'Baseline unavailable: '+row.path);const reader=response.body.getReader(),chunks=[];let size=0;for(;;){const item=await reader.read();if(item.done)break;size+=item.value.byteLength;if(size>row.size){await reader.cancel();throw Error('Baseline size changed: '+row.path);}chunks.push(item.value);}raw=Buffer.concat(chunks);error=null;break;}catch(e){error=e;}
  }
  if(error)throw error;
 }
 assert.equal(raw.length,row.size,'Baseline size changed: '+row.path);assert.equal(sha(raw),row.sha256,'Baseline changed; rebase explicitly: '+row.path);
 const dest=path.join(output,'static',row.path);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,raw,{flag:'wx'});
 if(local<0&&!row.path.endsWith('.html')&&!fs.existsSync(cached)){fs.mkdirSync(path.dirname(cached),{recursive:true});fs.writeFileSync(cached,raw,{flag:'wx'});}
 verified++;if(verified%100===0)console.log(`Verified baseline files: ${verified}/${baseline.files.length}`);
}
await Promise.all(Array.from({length:6},async()=>{while(next<baseline.files.length)await obtain(baseline.files[next++]);}));
assert.equal(overlay.files.length,4);let added=0,changed=0;
for(const row of overlay.files){
 assert((row.path.endsWith('.html')&&!row.path.includes('/'))||/^assets\/(company-home|company-map|company-office|home-layout|home-search-weather|home-progress-cards|attendance-summary|home-evaluation-tasks|home-auth-weather|login-lookup-entry|global-auth-nav|heat-stress|half-year-reader|half-year-reader-entry|inspection-plan-nav|inspection-calendar|calendar-entry|home-compact-cards|home-one-screen)-[a-f0-9]{12}\.(js|css)$/.test(row.path));
 const raw=fs.readFileSync(path.join(source,row.path));assert.equal(raw.length,row.size);assert.equal(sha(raw),row.sha256);
 const dest=path.join(output,'static',row.path);
 if(row.before_sha256){assert.equal(sha(fs.readFileSync(dest)),row.before_sha256);changed++;}else{assert(!fs.existsSync(dest));added++;}
 fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,raw);
}
assert.equal(added,2);assert.equal(changed,2);
const config=fs.readFileSync(path.join(source,'output-config.json'));assert.equal(JSON.parse(config).version,3);fs.writeFileSync(path.join(output,'config.json'),config,{flag:'wx'});
const result={passed:true,baseline_deployment:baseline.deployment,public_baseline_verified:verified,network_baseline:local<0,baseline_static_files:baseline.files.length,added_static_files:added,changed_existing_files:changed,total_static_files:baseline.files.length+added,source_hash_verified:true};
fs.mkdirSync(path.join(root,'.vercel'),{recursive:true});fs.writeFileSync(path.join(root,'.vercel/HOME_LAYOUT_BUILD.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
