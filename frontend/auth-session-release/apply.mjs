import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import assert from 'node:assert/strict';
export function applyAuthSession(baseline,output,source){
const manifest=JSON.parse(fs.readFileSync(source+'/manifest.json','utf8')),sha=b=>crypto.createHash('sha256').update(b).digest('hex');assert(!fs.existsSync(output),'Output already exists; inspect rather than overwrite');
assert.equal(sha(fs.readFileSync(baseline+'/index.html')),manifest.baseline_index_sha256);
for(const row of manifest.files)assert.equal(sha(fs.readFileSync(baseline+row.operating_asset)),row.operating_sha256);
for(const row of manifest.protected_current_release_files)assert.equal(sha(fs.readFileSync(baseline+row.path)),row.sha256);
const rows=[];function copy(folder,relative=''){for(const entry of fs.readdirSync(folder,{withFileTypes:true})){assert(!entry.isSymbolicLink());const rel=relative+entry.name,src=path.join(folder,entry.name),target=path.join(output,rel);if(entry.isDirectory())copy(src,rel+'/');else{assert(entry.isFile());fs.mkdirSync(path.dirname(target),{recursive:true});fs.linkSync(src,target);rows.push({path:rel,sha256:sha(fs.readFileSync(src))});}}}copy(baseline);
let html=fs.readFileSync(baseline+'/index.html','utf8');let changed=0;for(const[old,next]of Object.entries(manifest.mapping)){if(html.includes(old)){html=html.split(old).join(next);changed++;}}assert.equal(changed,1,'Only current main login loader changes');const temporary=output+'/index.html.auth-new';fs.writeFileSync(temporary,html);fs.renameSync(temporary,output+'/index.html');
for(const row of manifest.files){const src=source+row.candidate_asset,raw=fs.readFileSync(src);assert.equal(sha(raw),row.candidate_sha256);const target=output+row.candidate_asset;assert(!fs.existsSync(target));fs.copyFileSync(src,target);}
for(const row of rows)if(row.path!=='index.html')assert.equal(sha(fs.readFileSync(output+'/'+row.path)),row.sha256);
for(const row of manifest.files){const text=fs.readFileSync(output+row.candidate_asset,'utf8');for(const old of Object.keys(manifest.mapping))assert(!text.includes(old),'Old auth graph reference: '+old);}
for(const row of manifest.protected_current_release_files)assert.equal(sha(fs.readFileSync(output+row.path)),row.sha256);
return {passed:true,baseline_files:rows.length,unchanged_baseline_files:rows.length-1,new_assets:3,total_files:rows.length+3,changed_baseline:['index.html'],protected_current_release_files:manifest.protected_current_release_files.length,route_configuration_changed:false,actual_GUI:false,operating_deployed:false};}
