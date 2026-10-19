const API = 'https://api.besma.co.kr';
const token = localStorage.getItem('besma_token');
const app = document.querySelector('#app');
let caps, photos = [], selected = null, busy = false, blobs = [], generation = 0;
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
const button = (label, fn, cls = '') => { const n = el('button', label, cls); n.type = 'button'; n.addEventListener('click', fn); return n; };
function session() { if (!token || localStorage.getItem('besma_token') !== token) throw Error('로그인이 필요합니다. BESMA에서 로그인한 뒤 다시 열어 주세요.'); }
async function api(path, options = {}) {
  session();
  const r = await fetch(API + '/team-photos' + path, { ...options, cache: 'no-store', headers: { ...options.headers, Authorization: 'Bearer ' + token } });
  session();
  if (!r.ok) { let msg = '요청에 실패했습니다. 다시 시도해 주세요.'; try { const j = await r.json(); if (typeof j.detail === 'string') msg = j.detail; } catch {} if (r.status === 401 || r.status === 403) clearSession(); if (r.status === 401) msg = '로그인이 만료되었습니다. 다시 로그인해 주세요.'; throw Error(msg); }
  return r;
}
function release() { blobs.forEach(u => URL.revokeObjectURL(u)); blobs = []; }
function message(msg, error = false) { const n = document.querySelector('#status'); if (n) { n.textContent = msg; n.className = error ? 'status error' : 'status'; } }
function clearSession() { release(); generation++; app.replaceChildren(el('h1', '사진공유'), el('p', '로그인이 변경되었습니다. 다시 열어 주세요.')); const a = el('a', 'BESMA 로그인'); a.href = '/'; app.append(a); }
window.addEventListener('storage', e => { if (e.key === 'besma_token') clearSession(); });
async function image(photo, variant, target) {
  const version = generation;
  try { const r = await api('/' + photo.id + '/' + variant); const blob = await r.blob(); session(); if (version !== generation || !target.isConnected) return; const url = URL.createObjectURL(blob); blobs.push(url); target.src = url; }
  catch (err) { target.alt = err.message; }
}
function pick(slot, camera) {
  if (busy) return;
  const input = document.querySelector(camera ? '#camera' : '#library');
  input.value = ''; input.dataset.slot = slot; input.click();
}
function slotButtons(slot) {
  const row = el('div', '', 'actions');
  row.append(button('촬영', () => pick(slot, true), 'primary'), button('사진 선택', () => pick(slot, false)));
  return row;
}
function render() {
  release(); generation++;
  const head = el('header'); const back = el('a', '‹ 팀 스케줄'); back.href = '/hq-safe/team-schedule';
  const who = el('span', caps.user_name + ' · 안전보건실', 'who'); head.append(back, who);
  const h = el('h1', '사진공유');
  const intro = el('p', '본사 화재대피훈련 · 문, 계단, 집결지, 사무실 전경', 'intro');
  const hint = el('p', '가로로 촬영해 주세요. 문·계단은 이동 방향이, 집결지는 모일 공간이 보이게 찍으면 됩니다.', 'hint');
  const tools = el('div', '', 'toolbar');
  const done = caps.slots.filter(s => photos.some(p => p.slot === s.id)).length;
  tools.append(el('strong', `${done} / ${caps.slots.length} 항목 등록`), button('새로고침', refresh));
  const status = el('p', '', 'status'); status.id = 'status'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const grid = el('section', '', 'grid'); grid.setAttribute('aria-label', '촬영할 사진');
  for (const slot of caps.slots) {
    const card = el('article', '', 'card'); card.dataset.slot = slot.id;
    const matches = photos.filter(p => p.slot === slot.id), latest = matches[0];
    const meta = el('div', '', 'meta'); meta.append(el('span', slot.group, 'badge'), el('span', latest ? '등록됨' : '촬영 전', latest ? 'done' : 'pending'));
    card.append(meta, el('h2', slot.title), el('p', slot.hint, 'hint'));
    if (latest) {
      const view = button('', () => openPhoto(latest), 'photo-button'); view.setAttribute('aria-label', slot.title + ' 사진 보기');
      const img = el('img'); img.alt = slot.title; view.append(img); card.append(view);
      queueMicrotask(() => image(latest, 'thumb', img));
      card.append(el('p', latest.uploader_name + ' · ' + date(latest.created_at), 'byline'));
      const download = button('원본 다운로드', () => downloadPhoto(latest), 'download'); card.append(download);
    } else { const empty = button('사진 찍기', () => pick(slot.id, true), 'placeholder'); empty.setAttribute('aria-label', slot.title + ' 촬영'); card.append(empty); }
    card.append(slotButtons(slot.id));
    if (matches.length > 1) card.append(button('이전 사진 ' + (matches.length - 1) + '장', () => history(slot, matches), 'history'));
    grid.append(card);
  }
  const extra = el('section', '', 'extra'); extra.append(el('h2', '추가 사진'), el('p', '다른 업무 사진이나 훈련 당일 단체사진을 공유합니다.', 'hint'), slotButtons('extra'));
  for (const p of photos.filter(p => p.slot === 'extra')) { const row = el('div', '', 'extra-row'); row.append(button(p.caption || p.original_name, () => openPhoto(p)), el('span', p.uploader_name + ' · ' + date(p.created_at), 'byline')); extra.append(row); }
  const camera = el('input'); camera.id = 'camera'; camera.type = 'file'; camera.accept = 'image/jpeg,image/png,image/webp'; camera.setAttribute('capture', 'environment'); camera.hidden = true;
  const library = el('input'); library.id = 'library'; library.type = 'file'; library.accept = 'image/jpeg,image/png,image/webp'; library.hidden = true;
  [camera, library].forEach(input => input.addEventListener('change', () => choose(input.files?.[0], input.dataset.slot)));
  const foot = el('footer', '안전보건실 팀원에게 공유됩니다. · 2026.10.19.1');
  app.replaceChildren(head, h, intro, hint, tools, status, grid, extra, foot, camera, library);
}
function date(value) { return new Date(value).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
function dialog(title) {
  const d = el('dialog'); const heading = el('h2', title); const body = el('div', '', 'dialog-body');
  d.append(heading, body, button('닫기', () => { if (!busy) d.close(); }));
  d.addEventListener('cancel', e => { if (busy) e.preventDefault(); });
  d.addEventListener('close', () => { d.remove(); selected = null; });
  document.body.append(d); d.showModal(); return { d, body };
}
function choose(file, slot) {
  if (!file) return;
  if (file.size > caps.max_bytes) return message('사진은 25MB 이하로 올려 주세요.', true);
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return message('JPG·PNG·WEBP 사진을 선택해 주세요. HEIC는 JPG로 저장한 뒤 선택해 주세요.', true);
  const info = caps.slots.find(s => s.id === slot);
  const { d, body } = dialog(info?.title || '추가 사진');
  const url = URL.createObjectURL(file); const img = el('img'); img.src = url; img.alt = '업로드할 사진';
  d.addEventListener('close', () => URL.revokeObjectURL(url), { once: true });
  const label = el('label', '설명 (선택)'); const caption = el('input'); caption.type = 'text'; caption.maxLength = 300; label.append(caption);
  const status = el('p'); status.setAttribute('role', 'status');
  const send = button('팀에 공유', async () => {
    if (busy) return;
    busy = true; send.disabled = true; status.textContent = '사진을 올리고 있습니다…';
    const data = new FormData(); data.append('file', file); data.append('slot', slot); data.append('caption', caption.value); data.append('request_id', selected.id);
    try { await api('', { method: 'POST', body: data }); busy = false; d.close(); await refresh(); message('사진을 공유했습니다.'); }
    catch (err) { status.textContent = err.message; status.className = 'error'; busy = false; send.disabled = false; }
  }, 'primary');
  selected = { id: crypto.randomUUID() }; body.append(img, el('p', file.name + ' · ' + (file.size / 1024 / 1024).toFixed(1) + 'MB', 'byline'), label, status, send);
}
function history(slot, items) { const { body } = dialog(slot.title + ' · 사진 이력'); for (const p of items) { const row = el('div', '', 'extra-row'); row.append(button(date(p.created_at) + ' · ' + p.uploader_name, () => openPhoto(p))); body.append(row); } }
function openPhoto(p) { const { body } = dialog(p.caption || caps.slots.find(s => s.id === p.slot)?.title || '사진'); const img = el('img'); img.alt = p.caption || '공유 사진'; body.append(img, el('p', p.uploader_name + ' · ' + date(p.created_at), 'byline'), button('원본 다운로드', () => downloadPhoto(p), 'primary')); image(p, 'preview', img); }
async function downloadPhoto(p) {
  try { message('원본을 내려받고 있습니다…'); const r = await api('/' + p.id + '/original'); const blob = await r.blob(); session(); const url = URL.createObjectURL(blob); const a = el('a'); a.href = url; a.download = p.original_name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); message('원본 다운로드를 요청했습니다.'); }
  catch (err) { message(err.message, true); }
}
async function refresh() { if (busy || document.querySelector('dialog[open]')) return; try { photos = (await (await api('?limit=500')).json()).photos; render(); } catch (err) { message(err.message, true); } }
try { caps = await (await api('/capabilities')).json(); await refresh(); }
catch (err) { app.replaceChildren(el('h1', '사진공유'), el('p', err.message, 'error')); const a = el('a', 'BESMA로 돌아가기'); a.href = '/'; app.append(a); }
setInterval(() => { if (localStorage.getItem('besma_token') !== token) return clearSession(); if (!document.hidden) refresh(); }, 20000);
