import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const manifest=JSON.parse(await fs.readFile(path.join(repo,'tools/releases/preview-inputs-20261106.json'),'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const safe=s=>typeof s==='string'&&!s.includes('\\')&&!s.startsWith('/')&&!s.split('/').some(x=>!x||x==='.'||x==='..')&&!s.includes(':');
async function walk(root,prefix=''){const a=[];for(const x of await fs.readdir(root,{withFileTypes:true})){if(x.isSymbolicLink())throw Error('SYMLINK_INPUT');const n=prefix+x.name;if(x.isDirectory())a.push(...await walk(path.join(root,x.name),n+'/'));else a.push(n);}return a;}
if(process.env.VERCEL_ENV&&process.env.VERCEL_ENV!=='preview')throw Error('PREVIEW_ONLY_BUILD');
const actual=(await walk(path.join(repo,'frontend'))).filter(x=>x!=='vercel.json'&&!x.startsWith('.vercel/')&&!x.startsWith('.preview-build-')).map(x=>'frontend/'+x).sort();
const expected=Object.keys(manifest.source_inputs).sort();
if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error('SOURCE_FILE_SET_CHANGED: refresh verified preview inputs');
for(const n of expected){if(!safe(n)||hash(await fs.readFile(path.join(repo,n)))!==manifest.source_inputs[n])throw Error('SOURCE_INPUT_CHANGED: '+n);}
const names=manifest.files.map(x=>x.path);
if(names.some(n=>!safe(n))||new Set(names.map(n=>n.toLowerCase())).size!==names.length)throw Error('INVALID_OUTPUT_PATHS');
if(manifest.baseline_origin!=='https://www.besma.co.kr')throw Error('INVALID_BASELINE_ORIGIN');
const overlays=new Set(manifest.overlays),cacheRoot=process.env.BESMA_PREVIEW_BASELINE_DIR;
if(cacheRoot&&!process.env.BESMA_PREVIEW_LOCAL_TEST)throw Error('LOCAL_BASELINE_TEST_ONLY');
const output=path.join(repo,'frontend/.vercel/output');
// Never reuse an existing build silently; failed inputs cannot leave a valid output.
try{await fs.access(output);throw Error('OUTPUT_ALREADY_EXISTS: use a fresh checkout');}catch(e){if(e.code!=='ENOENT')throw e;}
const staging=path.join(repo,'frontend/.preview-build-'+process.pid);await fs.mkdir(staging);
let downloaded=0,overlayCount=0,index=0;
async function read(row){
 if(overlays.has(row.path)){overlayCount++;return fs.readFile(path.join(repo,'tools/releases/public-ux-20261106-output',row.path));}
 if(!row.path.startsWith('static/'))throw Error('UNDECLARED_CONFIG');
 if(cacheRoot)return fs.readFile(path.join(cacheRoot,row.path));
 const url=manifest.baseline_origin+'/'+row.path.slice(7).split('/').map(encodeURIComponent).join('/');
 let error;for(let attempt=0;attempt<3;attempt++){try{const response=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(30000)});if(!response.ok)throw Error('HTTP_'+response.status);const b=Buffer.from(await response.arrayBuffer());if(b.length!==row.bytes||hash(b)!==row.sha256)throw Error('BASELINE_CONTENT_CHANGED');downloaded++;return b;}catch(e){error=e;}}
 throw Error('BASELINE_UNAVAILABLE: '+row.path+' '+error.message);
}
await Promise.all(Array.from({length:4},async()=>{for(;;){const i=index++;if(i>=manifest.files.length)return;const row=manifest.files[i],b=await read(row);if(b.length!==row.bytes||hash(b)!==row.sha256)throw Error('OUTPUT_INTEGRITY_MISMATCH: '+row.path);const target=path.join(staging,row.path);await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,b);}}));
if((await walk(staging)).length!==manifest.files.length)throw Error('OUTPUT_COUNT_MISMATCH');
await fs.mkdir(path.dirname(output),{recursive:true});await fs.rename(staging,output);
console.log(JSON.stringify({passed:true,version:manifest.version,files:manifest.files.length,downloaded,overlays:overlayCount,source_inputs:expected.length,baseline_hashes_verified:true}));
