import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { applyAuthSession } from './auth-session-release/apply.mjs';
import { applySiteNames } from './site-name-release/apply.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const source = path.join(root, 'auth-session-release');
const manifest = JSON.parse(fs.readFileSync(path.join(source, 'public-baseline.json'), 'utf8'));
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
assert.equal(manifest.origin, 'https://www.besma.co.kr');
assert.equal(manifest.files.length, 815);
const local = process.argv.indexOf('--baseline');
const baseline = local < 0 ? path.join(root, '.vercel/public-baseline') : path.resolve(process.argv[local + 1]);
const outArg = process.argv.indexOf('--output');
const output = outArg < 0 ? path.join(root, '.vercel/output') : path.resolve(process.argv[outArg + 1]);
assert(!fs.existsSync(output), 'Build output already exists; preserve and inspect it before rebuilding');
const paths = new Set();
for (const row of manifest.files) {
  assert(typeof row.path === 'string' && !row.path.includes('\\') && !path.posix.isAbsolute(row.path));
  assert(!row.path.split('/').some(part => part === '..' || part === '.' || part === ''));
  assert(!paths.has(row.path), 'Duplicate baseline path'); paths.add(row.path);
  assert(/^[a-f0-9]{64}$/.test(row.sha256) && Number.isSafeInteger(row.size) && row.size >= 0 && row.size <= 16 * 1024 * 1024);
}
let completed = 0, next = 0;
async function obtain(row) {
  const target = path.join(baseline, row.path);
  let data;
  if (local >= 0 || fs.existsSync(target)) {
    assert(fs.lstatSync(target).isFile() && !fs.lstatSync(target).isSymbolicLink());
    data = fs.readFileSync(target);
  } else if (row.path === 'index.html' || row.path === 'page-share.html') {
    // Index changes after promotion; page-share is shadowed by an existing rewrite.
    // Preserve both exact underlying files rather than storing a rewritten response.
    data = fs.readFileSync(path.join(source, 'baseline-' + row.path));
  } else {
    const url = new URL(row.path.split('/').map(encodeURIComponent).join('/'), manifest.origin + '/');
    assert.equal(url.origin, manifest.origin);
    let last;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(25000) });
        assert(response.ok, `Public baseline unavailable: ${row.path} (${response.status})`);
        const reader = response.body.getReader(), chunks = []; let size = 0;
        while (true) {
          const item = await reader.read(); if (item.done) break;
          size += item.value.byteLength;
          if (size > row.size) { await reader.cancel(); throw Error(`Baseline size changed: ${row.path}`); }
          chunks.push(item.value);
        }
        data = Buffer.concat(chunks); last = null; break;
      } catch (error) { last = error; }
    }
    if (last) throw last;
  }
  assert.equal(data.length, row.size, `Baseline size changed: ${row.path}`);
  assert.equal(sha(data), row.sha256, `Baseline changed; rebase explicitly: ${row.path}`);
  if (local < 0 && !fs.existsSync(target)) {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, data, { flag: 'wx' });
  }
  completed++;
  if (completed % 100 === 0) console.log(`Verified public assets: ${completed}/${manifest.files.length}`);
}
await Promise.all(Array.from({ length: 6 }, async () => {
  while (next < manifest.files.length) await obtain(manifest.files[next++]);
}));
const config = fs.readFileSync(path.join(source, 'output-config.json'));
assert.equal(JSON.parse(config).version, 3);
const result = applyAuthSession(baseline, path.join(output, 'static'), source);
const siteNames = applySiteNames(path.join(output, 'static'));
Object.assign(result,siteNames,{total_files:result.total_files+1,changed_baseline:[...result.changed_baseline,'company.html'],unchanged_baseline_files:result.unchanged_baseline_files-1});
fs.writeFileSync(path.join(output, 'config.json'), config, { flag: 'wx' });
// Receipts remain outside the deployable output tree.
fs.mkdirSync(path.join(root, '.vercel'), { recursive: true });
fs.writeFileSync(path.join(root, '.vercel/AUTH_SESSION_BUILD_CHECK.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify({ ...result, public_baseline_verified: completed, network_baseline: local < 0 }));
