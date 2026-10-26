import fs from 'node:fs/promises';import path from 'node:path';import crypto from 'node:crypto';
import{transform}from 'esbuild';
const [R,baselineRoot]=process.argv.slice(2);if(!R||!baselineRoot)throw Error('Usage: npm run build -- <task-root> <verified-baseline-static>');const F=R+'/release/frontend',O=R+'/frontend-release/.vercel/output',S=O+'/static';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex'),baseline=JSON.parse(await fs.readFile(R+'/qa/frontend-baseline.json','utf8'));
const original=await fs.readFile(baselineRoot+'/index.html','utf8');
for(const[name,h]of Object.entries(baseline))if(name!=='index.html'&&hash(await fs.readFile(S+'/'+name))!==h)throw Error('Preserved file changed: '+name);
const assets={};
for(const name of ['workspace.css','company.css','workspace-legacy.css','workspace.js','workspace-nav.js']){
 let source=await fs.readFile(F+'/'+name,'utf8');for(const[k,v]of Object.entries(assets))source=source.replaceAll('/assets/'+k,'/'+v);
 const result=await transform(source,{loader:name.endsWith('css')?'css':'js',target:'es2022',minify:true});const target='assets/'+name.replace(/\.(js|css)$/,'-'+hash(result.code).slice(0,12)+'.$1');await fs.writeFile(S+'/'+target,result.code);assets[name]=target;
}
for(const name of ['workspace.html','company.html']){let html=await fs.readFile(F+'/'+name,'utf8');for(const[k,v]of Object.entries(assets))html=html.replaceAll('/assets/'+k,'/'+v);await fs.writeFile(S+'/'+name,html);}
await fs.cp(F+'/workspace-assets',S+'/workspace-assets',{recursive:true});
const index=original.replace('</head>',`<script type="module" src="/${assets['workspace-nav.js']}"></script></head>`);await fs.writeFile(S+'/index.html',index);
const config=JSON.parse(await fs.readFile(O+'/config.json','utf8'));config.routes=config.routes.filter(x=>x.src!=='/'&&x.src!=='/company.html');config.routes.unshift({src:'/',dest:'/company.html'});await fs.writeFile(O+'/config.json',JSON.stringify(config));
await fs.writeFile(R+'/qa/frontend-build.json',JSON.stringify({assets,index_sha256:hash(index),baseline_index_sha256:baseline['index.html'],preserved_files:Object.keys(baseline).length-1,version:'2026.10.26.1'},null,2));console.log('BESMA workspace build passed; existing assets preserved.');
