import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
export function applySiteNames(output) {
 const source=path.dirname(fileURLToPath(import.meta.url));
 const m=JSON.parse(fs.readFileSync(source+'/manifest.json','utf8'));
 const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
 const old=fs.readFileSync(output+m.original_asset);assert.equal(sha(old),m.original_sha256);
 const html=fs.readFileSync(output+'/company.html','utf8');assert.equal(sha(html),m.company_html_sha256);
 assert.equal(html.split(m.original_asset).length,2);
 const raw=fs.readFileSync(source+m.asset);assert.equal(sha(raw),m.sha256);
 assert.equal(old.toString().replace(m.before,m.after),raw.toString());
 fs.writeFileSync(output+m.asset,raw,{flag:'wx'});
 fs.writeFileSync(output+'/company.html.new',html.replace(m.original_asset,m.asset),{flag:'wx'});
 fs.renameSync(output+'/company.html.new',output+'/company.html');
 return {site_name_filter:true,site_name_asset:m.asset,additional_files:1,additional_changed_baseline:['company.html']};
}
