import { mountMap as k } from "/assets/company-map-336a01cf582b.js";
import { Marker as v, Popup as A } from "/workspace-assets/vendor/maplibre-6.16.0/maplibre-gl.mjs";
const n = { name: "\uBD80\uD604\uC804\uAE30 \uC11C\uC6B8\uC0AC\uC5C5\uC18C", address: "\uC11C\uC6B8\uD2B9\uBCC4\uC2DC \uC601\uB4F1\uD3EC\uAD6C \uAC00\uB9C8\uC0B0\uB85C48\uAE38 16, \uC2E0\uD48D\uD504\uB77C\uC790 4\uCE35", longitude: 126.90122105674523, latitude: 37.50148569505714 };
function o(r, t, e) {
  const i = document.createElement(r);
  return t && (i.textContent = t), e && (i.style.cssText = e), i;
}
function attachOffice(r, { signal: t } = {}) {
  if (t?.aborted) return () => {
  };
  const e = o("button", null, "border:0;background:transparent;padding:0;cursor:pointer;display:flex;align-items:center;flex-direction:column;min-width:44px;min-height:44px;color:#163950;font:600 12px sans-serif;");
  e.type = "button", e.className = "company-office-marker", e.setAttribute("aria-label", n.name + " \uC0AC\uBB34\uC2E4 \uC815\uBCF4"), e.setAttribute("aria-expanded", "false");
  const i = o("span", null, "display:grid;place-items:center;width:38px;height:38px;background:#173e57;border:2px solid white;border-radius:9px;box-shadow:0 2px 6px #0005;"), p = document.createElement("img");
  p.src="/workspace-assets/boohyun-symbol.svg";p.alt="부현전기";i.append(p);
  const h = o("span", n.name, "background:white;padding:3px 6px;border-radius:4px;margin-top:3px;box-shadow:0 1px 4px #0003;white-space:nowrap;");
  e.append(i, h);
  const a = o("section", null, "font:14px/1.5 sans-serif;color:#18394b;width:min(272px,calc(100vw - 78px));padding:8px;box-sizing:border-box;");
  a.className = "company-office-card", a.setAttribute("aria-label", n.name), a.append(o("h3", n.name, "font-size:17px;margin:0 18px 8px 0;"), o("p", n.address, "margin:0 0 6px;"));
  const f = o("a", "02-848-8804", "display:inline-block;margin-bottom:8px;color:#155b82;");
  f.href = "tel:028488804", a.append(f);
  const b = o("figure", null, "margin:0;text-align:center;"), l = o("img", null, "display:block;width:100%;height:210px;object-fit:contain;background:#f5f7f8;border-radius:6px;");
  l.src = "/workspace-assets/company/ceo-kim-hong-su.png", l.alt = "\uBD80\uD604\uC804\uAE30 \uAE40\uD64D\uC218 \uB300\uD45C\uC774\uC0AC", l.decoding = "async", l.onerror = () => {
    l.replaceWith(o("p", "\uB300\uD45C\uC774\uC0AC \uAE40\uD64D\uC218"));
  }, b.append(l, o("figcaption", "\uB300\uD45C\uC774\uC0AC \uAE40\uD64D\uC218", "margin-top:5px;font-weight:600;")), a.append(b);
  const m = o("a", "\uAE38\uCC3E\uAE30 \u2197", "display:inline-block;margin-top:8px;color:#155b82;");
  m.href = "https://map.naver.com/p/search/" + encodeURIComponent(n.address), m.target = "_blank", m.rel = "noopener noreferrer", a.append(m);
  const s = new A({ offset: 35, maxWidth: "310px", closeOnClick: true, focusAfterOpen: false }).setLngLat([n.longitude, n.latitude]).setDOMContent(a), w = new v({ element: e, anchor: "bottom" }).setLngLat([n.longitude, n.latitude]).addTo(r);
  s.on("open", () => {
    const u = a.parentElement;
    u && (u.style.maxHeight = Math.max(80, Math.min(340, r.getCanvas().clientHeight / 2 - 80)) + "px", u.style.overflowY = "auto"), e.setAttribute("aria-expanded", "true");
    const x = a.parentElement?.querySelector(".maplibregl-popup-close-button");
    x && x.setAttribute("aria-label", "\uC11C\uC6B8\uC0AC\uC5C5\uC18C \uC815\uBCF4 \uB2EB\uAE30");
  }), s.on("close", () => e.setAttribute("aria-expanded", "false")), e.onclick = (u) => {
    u.stopPropagation(), s.isOpen() ? s.remove() : (s.addTo(r), requestAnimationFrame(() => {
      s.isOpen() && s.setLngLat([n.longitude, n.latitude]);
    }));
  };
  let g = false;
  function d() {
    g || (g = true, s.remove(), w.remove(), t?.removeEventListener("abort", d), r.off("remove", d));
  }
  return t?.addEventListener("abort", d, { once: true }), r.on("remove", d), d;
}
async function mountMap(r) {
  const t = await k(r);
  if (r.signal?.aborted) return t;
  const e = attachOffice(t.map, r), i = t.dispose;
  return { ...t, dispose() {
    return e(), i.call(t);
  } };
}
export {
  attachOffice,
  mountMap
};
