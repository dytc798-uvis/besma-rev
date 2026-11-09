const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto'),esbuild=require('esbuild');
const G=path.resolve(__dirname,'..'),base=path.resolve(process.argv[2]),dest=path.resolve(process.argv[3]),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const baseline='dpl_4xCKgnB3WmDFUFxkHYdQJMCiouU5';
function files(dir,p=''){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(f=>f.isDirectory()?files(path.join(dir,f.name),p+f.name+'/'):[{path:p+f.name,sha256:sha(fs.readFileSync(path.join(dir,f.name))),bytes:fs.statSync(path.join(dir,f.name)).size}]);}
assert(!fs.existsSync(dest),'OUTPUT_ALREADY_EXISTS');
fs.mkdirSync(path.join(dest,'.vercel'),{recursive:true});fs.cpSync(path.join(base,'.vercel/output'),path.join(dest,'.vercel/output'),{recursive:true});fs.copyFileSync(path.join(base,'.vercel/project.json'),path.join(dest,'.vercel/project.json'));
const O=path.join(dest,'.vercel/output'),S=path.join(O,'static'),before=files(O);
assert.equal(sha(fs.readFileSync(path.join(S,'local-photo-queue.js'))),'92ac890075792e03e2b857320bc6f4ef2a1f367d8bbf268d4d529956ee55b692');
const code=esbuild.transformSync(fs.readFileSync(path.join(G,'frontend/team-inspection/local-photo-queue.js'),'utf8'),{loader:'js',target:'es2022',minify:true}).code;
assert.equal(sha(code),'4524d58408954827403b4b1e8037029ab0b95a340fc263f8ef5af210d6235e3c');
function asset(prefix,content){const name='assets/'+prefix+'-'+sha(content).slice(0,12)+'.js';assert(!fs.existsSync(path.join(S,name)));fs.writeFileSync(path.join(S,name),content);return name;}
function replaceOne(content,from,to){assert.equal(content.split(from).length,2,'IMPORT_NOT_UNIQUE');return content.replace(from,to);}
const queue=asset('local-photo-queue',code),editor=asset('half-year-editor',replaceOne(fs.readFileSync(path.join(S,'half-year-editor.js'),'utf8'),'/local-photo-queue.js?v=2026.11.09.2','/'+queue)),plan=asset('inspection-plan',replaceOne(fs.readFileSync(path.join(S,'inspection-plan.js'),'utf8'),'/half-year-editor.js?v=2026.11.09.5','/'+editor));
fs.writeFileSync(path.join(S,'inspection-plan.html'),replaceOne(fs.readFileSync(path.join(S,'inspection-plan.html'),'utf8'),'/inspection-plan.js?v=2026.11.09.5','/'+plan));
const after=files(O),changed=after.filter(r=>before.find(b=>b.path===r.path)?.sha256!==r.sha256).map(r=>r.path);
assert.equal(changed.length,4);assert.equal(after.length,before.length+3);assert.equal(before.filter(r=>after.find(a=>a.path===r.path)?.sha256===r.sha256).length,before.length-1);
fs.writeFileSync(path.join(dest,'build660.json'),JSON.stringify({passed:true,release:'2026.11.09.7',baseline,before,after,changed,preserved:before.length-1,queue,editor,plan,source_sha256:sha(fs.readFileSync(path.join(G,'frontend/team-inspection/local-photo-queue.js'))),esbuild:esbuild.version,account_portal_included:false,backend_changes:0},null,2));
console.log(JSON.stringify({passed:true,release:'2026.11.09.7',files:after.length,preserved:before.length-1,changed}));
