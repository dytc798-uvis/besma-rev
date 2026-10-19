// Additive navigation for the already-deployed HQ workspace.
let checkedToken, allowed = false, pending;
async function check() {
  const token = localStorage.getItem('besma_token');
  if (token === checkedToken || pending === token) return;
  checkedToken = undefined; allowed = false; document.querySelectorAll('[data-photo-share-nav]').forEach(n => n.remove());
  if (!token) return;
  pending = token;
  try { const r = await fetch('https://api.besma.co.kr/team-photos/capabilities', { headers: { Authorization: 'Bearer ' + token }, cache: 'no-store' }); if (localStorage.getItem('besma_token') === token) { checkedToken = token; allowed = r.ok && (await r.json()).can_read === true; } }
  catch {} finally { pending = undefined; install(); }
}
function install() {
  if (checkedToken !== localStorage.getItem('besma_token') || !allowed) return;
  for (const next of document.querySelectorAll('a[href="/hq-safe/team-schedule"]')) {
    if (next.previousElementSibling?.dataset.photoShareNav) continue;
    const link = document.createElement('a'); link.href = '/photo-share.html'; link.textContent = '사진공유'; link.className = next.className; link.dataset.photoShareNav = 'true';
    next.before(link);
  }
}
new MutationObserver(() => { check(); install(); }).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener('storage', check); setInterval(check, 3000); check();
