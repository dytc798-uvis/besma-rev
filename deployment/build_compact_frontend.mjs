import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {transform} from 'file:///D:/JSI/besma-safety-ledgers-deploy/frontend/node_modules/esbuild/lib/main.js';
const root='D:/JSI/workfiles/besma-government-release-20261008';
const staticRoot=root+'/frontend-release/.vercel/output/static';
let html=await fs.readFile('D:/JSI/workfiles/besma-collection-monitor-20261008/frontend-release/.vercel/output/static/index.html','utf8');
html=html.replace(/\s*<script type="module" src="\/assets\/collection-monitor-[^"]+"><\/script>/g,'').replace(/\s*<link rel="stylesheet" href="\/assets\/collection-monitor-[^"]+">/g,'');
const files=[];
for(const name of ['collection-monitor.js','collection-monitor.css','government-workspace.js','government-workspace.css']){
 let source=await fs.readFile(root+'/release/frontend/'+name,'utf8');
 await fs.writeFile(root+'/release/frontend/'+name,source);
 const output=await transform(source,{loader:name.endsWith('.css')?'css':'js',minify:true,target:'es2022'});
 const hash=crypto.createHash('sha256').update(output.code).digest('hex');const ext=path.extname(name);const filename=name.slice(0,-ext.length)+'-'+hash.slice(0,12)+ext;
 await fs.writeFile(staticRoot+'/assets/'+filename,output.code);
 files.push({path:'assets/'+filename,sha256:hash,source:name});
 html=html.replace('</head>',(ext==='.js'?`<script type="module" src="/assets/${filename}"></script>`:`<link rel="stylesheet" href="/assets/${filename}">`)+'\n  </head>');
}
await fs.writeFile(staticRoot+'/index.html',html);
await fs.writeFile(root+'/frontend-build.json',JSON.stringify({version:'government-documents-20261008-compact-frozen-1.3.1',files,index_sha256:crypto.createHash('sha256').update(html).digest('hex')},null,2));
console.log(JSON.stringify({built_addons:files.length,index_sha256:crypto.createHash('sha256').update(html).digest('hex')}));
