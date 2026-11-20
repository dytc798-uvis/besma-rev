import { inspectionHref as Ge } from "/assets/inspection-work-entry-ef50e3143442.js";
import "/assets/home-task-shortcuts-cb9e26ae237f.js";
import { createHomeInspectionTasks as ht } from "/assets/home-inspection-tasks-376ee66bfd24.js";
import { createHomeOpinionTasks as gt } from "/assets/home-opinion-tasks-da996a064671.js";
import { createHomeEvaluationTasks as yt } from "/assets/home-evaluation-tasks-93979fc36629.js";
import "/assets/home-document-tasks-651fa78a67ad.js";
import { loadTransport as wt, transportCard as $e } from "/assets/site-transport-12fd4305fc70.js";
import { siteChatLink as vt } from "/assets/chat-context-93aa92f18522.js";
import { showChatLauncher as bt } from "/assets/chat-entry-2aed194f2248.js";
import { mountRequestNotifications as kt } from "/assets/request-notifications-adfa4cc7226d.js";
import { bindNaverDirections as Ye } from "/assets/naver-directions-ed1547ad3456.js";
import { siteCustomerName as St } from "/assets/customer-policy-46f8226bce17.js";
import { mountSiteNotes as _t } from "/assets/site-notes-55013a5cfd20.js";
import { attendanceSummary as xt } from "/assets/attendance-summary-3469370c4b8f.js";
import { hasMissingSiteInfo as Qe } from "/assets/site-missing-info-2097605422af.js";
import { createHQSiteCorrectionEditor as Ct } from "/assets/site-correction-access-9580af784eea.js";
import { TEAM_COLORS as De } from "/assets/map-teams-93050eef332d.js";
import { mountMap as It } from "/assets/company-office-10289dc995d6.js";
const de = "https://api.besma.co.kr", C = localStorage.getItem("besma_token"), r = (e) => document.getElementById(e), i = (e, t, n) => {
  const o = document.createElement(e);
  return t != null && (o.textContent = t), n && (o.className = n), o;
}, Le = r("map-team-legend"), B = (e, t, n) => {
  const o = i("button", e, n);
  return o.type = "button", o.onclick = t, o;
}, ie = document.createElement("section");
ie.id = "home-request-notifications", ie.hidden = true, document.querySelector(".field-dashboard").before(ie);
let Xe = null;
C && kt(ie, { api: Z, compact: true, isCurrent: () => localStorage.getItem("besma_token") === C }).then((e) => Xe = e), addEventListener("storage", (e) => {
  (e.key === "besma_token" || e.key === null) && (Xe?.(), ie.replaceChildren(), ie.hidden = true);
});
let pe = false, re = null, ke = "";
const ue = { update() {
} };
ue.update("documents", { state: "HIDDEN" });
const et = { refresh() {
  ue.update("documents", { state: "HIDDEN" });
}, clear() {
  ue.update("documents", { state: "HIDDEN" });
} }, tt = yt({ anchor: r("today-document-tasks") || r("seoul-weather"), api: de, token: C, onNavigate: () => {
  x();
  try {
    sessionStorage.setItem(G, JSON.stringify({ owner: V, at: Date.now() }));
  } catch {
  }
} }), nt = ht({ onSummary: (e) => {
  ue.update("inspections", e);
}, anchor: r("seoul-weather"), api: de, token: C, onNavigate: () => {
  x();
  try {
    sessionStorage.setItem(G, JSON.stringify({ owner: V, at: Date.now() }));
  } catch {
  }
} });
new MutationObserver(() => queueMicrotask(xe)).observe(r("today-inspection-tasks"), { childList: true, subtree: true });
const Et = gt({ onSummary: (e) => ue.update("opinions", e), anchor: r("seoul-weather"), api: de, token: C, onNavigate: () => {
  x();
  try {
    sessionStorage.setItem(G, JSON.stringify({ owner: V, at: Date.now() }));
  } catch {
  }
} }), D = i("details", null, "attendance-coverage");
D.id = "attendance-coverage", D.hidden = true, document.querySelector(".attendance-block").after(D), D.addEventListener("toggle", () => {
  D.hidden || (pe = D.open, x());
});
function Tt(e, t) {
  if (D.replaceChildren(), D.hidden = t.state !== "current", D.hidden) return;
  const n = (l) => Number.isSafeInteger(l.today_people) && l.today_people >= 0, o = e.sites.filter((l) => !n(l)), s = i("summary", "\uD604\uC7A5\uBCC4 \uCD9C\uC5ED \uD655\uC778 " + e.sites.filter(n).length + " \xB7 \uBBF8\uD655\uC778 " + o.length);
  if (D.append(s), D.open = pe, !o.length) {
    D.append(i("p", "\uD604\uC7AC \uD604\uC7A5\uC758 \uCD9C\uC5ED\uC790\uB8CC\uB97C \uBAA8\uB450 \uD655\uC778\uD588\uC2B5\uB2C8\uB2E4."));
    return;
  }
  D.append(i("p", "\uBBF8\uD655\uC778 \uD604\uC7A5\uC744 \uB20C\uB7EC \uB2F4\uB2F9\uC790\uC5D0\uAC8C \uD655\uC778\uD558\uC138\uC694."));
  const a = i("ul");
  for (const l of o) {
    const d = i("li"), p = i("a", l.name);
    p.href = "/workspace.html#sites?site=" + encodeURIComponent(l.code), p.dataset.homePreserveFocus = "true", d.append(p), a.append(d);
  }
  D.append(a);
}
let v = null, T = "\uC804\uCCB4", h = null, J = 0, K = 0, g = "all", y = "all", E = "", k = "all", te = "loading", Oe = null, S = null, Fe = null, se = null, le = "\uC804\uAD6D", Pe = false, L = null;
const Se = /* @__PURE__ */ new Map(), fe = /* @__PURE__ */ new Set();
let ne = /* @__PURE__ */ new Set(), $ = false, O = false;
const _e = /* @__PURE__ */ new Set();
let H = "LOADING", at = "", At = [], me = [], ot = 0, he = null;
function ge(e) {
  return me.filter((t) => t.site_codes.includes(e.code));
}
function ye() {
  if (H !== "VERIFIED") return { known: false, total: null, pending: null };
  const e = /* @__PURE__ */ new Set();
  for (const t of ze()) if (j(t)) for (const n of ge(t)) e.add(n.public_id);
  return { known: true, total: _e.size, pending: [..._e].filter((t) => !e.has(t)).length };
}
function Nt() {
  const e = ye();
  return e.known ? e.pending ? "\uC810\uAC80\uACC4\uD68D\uC740 \uC788\uC2B5\uB2C8\uB2E4. \uC9C0\uB3C4 \uC5F0\uACB0\uC744 \uD655\uC778\uD574\uC57C \uD558\uB294 \uACC4\uD68D\uC740 \uC67C\uCABD \uB0B4 \uC810\uAC80 \uBAA9\uB85D\uC5D0\uC11C \uD655\uC778\uD558\uC138\uC694." : e.total ? "\uD604\uC7AC \uC870\uAC74\uC5D0 \uB9DE\uB294 \uC810\uAC80 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4." : "\uB4F1\uB85D\uB41C \uB0B4 \uC810\uAC80\uACC4\uD68D\uC774 \uC5C6\uC2B5\uB2C8\uB2E4." : te === "error" || H === "UNKNOWN" ? "\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uD655\uC778\uD574 \uC8FC\uC138\uC694." : "\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uACE0 \uC788\uC2B5\uB2C8\uB2E4.";
}
function xe() {
  if (!v) return;
  const e = me.map((n) => n.public_id), t = H + "|" + e.join("|");
  if (t !== at) {
    at = t, _e.clear();
    for (const n of e) _e.add(n);
    k === "inspections" && M();
  }
}
function Mt(e) {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  y = y === e ? "all" : e, T = "\uC804\uCCB4", g = "all", k = "all", E = "", h = null, O = false, r("home-site-query").value = "", M();
  const t = y;
  Ee().then(() => {
    if (t !== y || k !== "all") return;
    const n = y === "all" ? N() : N().filter((o) => Y(o) === y);
    n.some(j) ? S?.fitSites(n, { name: y === "all" ? "\uC804\uAD6D" : y + "\uD300", maxZoom: n.length === 1 ? 15 : 12 }) : w("\uC120\uD0DD\uD55C \uD300\uC758 \uC9C0\uB3C4 \uC704\uCE58\uB97C \uD655\uC778\uD560 \uC218 \uC788\uB294 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4."), x();
  });
}
async function Z(e, t = {}) {
  if (!C || localStorage.getItem("besma_token") !== C) throw Error("\uBCF8\uC0AC \uB85C\uADF8\uC778 \uD6C4 \uD655\uC778\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.");
  const n = await fetch(de + e, { ...t, headers: { Authorization: "Bearer " + C, ...t.body ? { "Content-Type": "application/json" } : {} }, cache: "no-store" });
  if (localStorage.getItem("besma_token") !== C) throw Error("\uB85C\uADF8\uC778 \uACC4\uC815\uC774 \uBCC0\uACBD\uB418\uC5C8\uC2B5\uB2C8\uB2E4.");
  if (!n.ok) {
    let o = "";
    try {
      const s = await n.json();
      typeof s.detail == "string" && (o = s.detail);
    } catch {
    }
    throw Error(n.status === 409 ? o || "\uB2E4\uB978 \uC0AC\uC6A9\uC790\uAC00 \uBA3C\uC800 \uC218\uC815\uD588\uC2B5\uB2C8\uB2E4. \uC0C8\uB85C\uACE0\uCE68 \uD6C4 \uD655\uC778\uD574 \uC8FC\uC138\uC694." : n.status === 403 ? "\uC774 \uACC4\uC815\uC758 \uC774\uC6A9 \uAD8C\uD55C\uC744 \uD655\uC778\uD574 \uC8FC\uC138\uC694." : n.status === 401 ? "\uB85C\uADF8\uC778 \uD6C4 \uD655\uC778\uD574 \uC8FC\uC138\uC694." : o || "\uCC98\uB9AC\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uC2DC\uB3C4\uD574 \uC8FC\uC138\uC694.");
  }
  return n.json();
}
function w(e) {
  r("home-action-status").textContent = e;
}
function F() {
  return !!document.querySelector('.site-info-editor[data-dirty="true"],.site-info-editor[data-busy="true"],.site-shared-notes[data-dirty="true"],.site-shared-notes[data-busy="true"]');
}
function bn(e) {
  const t = ne.has(e.code), n = B(t ? "\u2605" : "\u2606", (o) => {
    o?.stopPropagation(), qt(e);
  }, "site-favorite");
  return n.setAttribute("aria-label", e.name + " \uC990\uACA8\uCC3E\uAE30 " + (t ? "\uD574\uC81C" : "\uCD94\uAC00")), n.setAttribute("aria-pressed", String(t)), n.disabled = !$ || fe.has(e.code), n;
}
async function qt(e) {
  if (!(!$ || fe.has(e.code))) {
    fe.add(e.code);
    for (const t of document.querySelectorAll(".site-favorite")) t.closest("[data-site-code]")?.dataset.siteCode === e.code && (t.disabled = true);
    try {
      const t = await Z("/workspace/sites/" + encodeURIComponent(e.code) + "/favorite", { method: "PUT", body: JSON.stringify({ favorite: !ne.has(e.code) }) });
      if (t.code !== e.code || typeof t.favorite != "boolean") throw Error("\uC990\uACA8\uCC3E\uAE30 \uACB0\uACFC\uB97C \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uC0C8\uB85C\uACE0\uCE68\uD574 \uC8FC\uC138\uC694.");
      t.favorite ? ne.add(e.code) : ne.delete(e.code), M(), x(), w(t.favorite ? "\uC990\uACA8\uCC3E\uAE30\uC5D0 \uC800\uC7A5\uD588\uC2B5\uB2C8\uB2E4." : "\uC990\uACA8\uCC3E\uAE30\uC5D0\uC11C \uD574\uC81C\uD588\uC2B5\uB2C8\uB2E4.");
    } catch (t) {
      w(t.message);
    } finally {
      fe.delete(e.code);
      for (const t of document.querySelectorAll(".site-favorite")) t.closest("[data-site-code]")?.dataset.siteCode === e.code && (t.disabled = !$);
    }
  }
}
function kn(e) {
  return j(e) && !["locality", "range", "municipality", "region"].includes(e.location_precision);
}
function Sn() {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  if (!$) {
    w("\uC990\uACA8\uCC3E\uAE30\uB97C \uD655\uC778\uD55C \uB4A4 \uB2E4\uC2DC \uB20C\uB7EC \uC8FC\uC138\uC694.");
    return;
  }
  T = "\uC804\uCCB4", k = "all", g = "favorites", y = "all", E = "", h = null, O = false, r("home-site-query").value = "", M(), S?.fitSites(N(), { name: "\uC990\uACA8\uCC3E\uAE30" }), x();
}
function Rt() {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  const e = g === "government";
  T = "\uC804\uCCB4", k = "all", g = e ? "all" : "government", y = e ? "all" : "government", E = "", h = null, O = false, r("home-site-query").value = "", M(), e ? S?.reset() : S?.fitSites(N(), { name: "\uAD00\uAE09\uACF5\uC0AC" }), x(), w(e ? "\uC804\uCCB4 \uD604\uC7A5\uC744 \uD45C\uC2DC\uD569\uB2C8\uB2E4." : "\uAD00\uAE09\uACF5\uC0AC \uD604\uC7A5\uB9CC \uD45C\uC2DC\uD569\uB2C8\uB2E4.");
}
function Ue(e) {
  if (!e) return "";
  const t = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(e) ? e : e.replace(" ", "T") + "Z");
  return Number.isNaN(t.getTime()) ? e : new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(t);
}
async function Dt() {
  const e = r("notice-list");
  if (e.replaceChildren(), !v.notices.length) {
    e.append(i("p", "\uB4F1\uB85D\uB41C \uACF5\uC9C0\uC0AC\uD56D\uC774 \uC5C6\uC2B5\uB2C8\uB2E4."));
    return;
  }
  for (const t of v.notices) {
    const n = i("details"), o = i("summary");
    o.append(i("span", t.title), i("time", Ue(t.created_at))), n.append(o);
    let s = false;
    n.addEventListener("toggle", async () => {
      if (!n.open || s) return;
      s = true;
      const a = i("p", "\uBD88\uB7EC\uC624\uB294 \uC911\uC785\uB2C8\uB2E4.", "notice-body");
      n.append(a);
      try {
        const l = await Z("/notices/" + t.id);
        a.textContent = l.notice.body;
      } catch (l) {
        a.textContent = l.message, s = false;
      }
    }), e.append(n);
  }
}
const z = (e, t = {}) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", e);
  for (const [o, s] of Object.entries(t)) n.setAttribute(o, s);
  return n;
};
function it(e) {
  if (e.region !== "\uC218\uB3C4\uAD8C") return e.region || "\uC8FC\uC18C \uD655\uC778 \uC911";
  const t = String(e.address || "").replace(/\s/g, "");
  return t.startsWith("\uC11C\uC6B8") ? "\uC11C\uC6B8" : t.startsWith("\uACBD\uAE30") ? "\uACBD\uAE30" : t.startsWith("\uC778\uCC9C") ? "\uC778\uCC9C" : "\uC8FC\uC18C \uD655\uC778 \uC911";
}
function ze() {
  return (v?.sites || []).filter((e) => e.map_visible === false ? false : e.map_visible === true ? true : !/(?<![배간전])선공사|임시(?:동력|전력|가설)|가설(?:공사|전기)/u.test(String(e.name || "").normalize("NFC").replace(/\s/g, "")));
}
function j(e) {
  return typeof e.latitude == "number" && typeof e.longitude == "number" && Number.isFinite(e.latitude) && Number.isFinite(e.longitude) && e.latitude >= 33 && e.latitude <= 39 && e.longitude >= 124 && e.longitude <= 132;
}
function Lt(e) {
  return e.is_government === true ? "government" : e.is_government === false ? "general" : "unclassified";
}
function Ot(e) {
  return e.is_government === true ? "\uAD00\uAE09\uACF5\uC0AC" : e.is_government === false ? "\uC77C\uBC18 \uD604\uC7A5" : "\uACF5\uC0AC \uAD6C\uBD84 \uD655\uC778 \uC911";
}
function rt(e, t = false) {
  try {
    const n = new URL(e, location.href), o = n.protocol === "http:" && (n.origin === location.origin || t && ["boohyun.kr", "www.boohyun.kr"].includes(n.hostname) && !n.port);
    return n.protocol === "https:" || o ? n : null;
  } catch {
    return null;
  }
}
function Ce(e) {
  const t = e.photo;
  if (!t || t.verified !== true || t.site_code !== e.code || typeof t.url != "string" || typeof t.source_url != "string" || !t.url.trim() || !t.source_url.trim()) return null;
  const n = rt(t.url), o = rt(t.source_url, true);
  return n && o && !n.username && !n.password && !o.username && !o.password ? { ...t, url: n.href, source_url: o.href } : null;
}
async function Ft(e, t, n) {
  if (e.latitude == null) {
    t.textContent = "\uC704\uCE58 \uD655\uC778 \uD6C4 \uB0A0\uC528 \uC81C\uACF5";
    return;
  }
  const o = e.code;
  try {
    let s = Se.get(o);
    (!s || s.expires < Date.now()) && (s = { promise: Z("/workspace/site-weather/" + encodeURIComponent(o)), expires: Date.now() + 3e5 }, Se.set(o, s));
    const a = await s.promise;
    if (n !== J || !t.isConnected) return;
    if (t.replaceChildren(), !a.available) {
      t.textContent = a.status_text || a.reason || "\uB0A0\uC528 \uD655\uC778 \uC911";
      return;
    }
    const l = i("strong", (a.weather_label || "\uD604\uC7AC \uB0A0\uC528") + " \xB7 " + (a.temperature == null ? "\u2014" : Math.round(a.temperature) + "\u2103")), d = i("a", String(a.source || "").startsWith("kma") ? "\uAE30\uC0C1\uCCAD" : "Open-Meteo");
    d.href = String(a.source || "").startsWith("kma") ? "https://www.weather.go.kr/" : "https://open-meteo.com/", d.target = "_blank", d.rel = "noopener", d.className = "weather-provider", t.append(d, l, i("small", [a.wind_speed != null ? "\uBC14\uB78C " + a.wind_speed + "m/s" : "", a.humidity != null ? "\uC2B5\uB3C4 " + a.humidity + "%" : ""].filter(Boolean).join(" \xB7 ")), i("small", (String(a.source || "").startsWith("kma") ? "\uAE30\uC0C1\uCCAD" : "\uC704\uCE58 \uAE30\uBC18 \uAE30\uC0C1\uC790\uB8CC") + " \xB7 \uC790\uB8CC\uC2DC\uAC01 " + Ue(a.observed_at)));
  } catch (s) {
    Se.delete(o), t.isConnected && (t.textContent = s.message);
  }
}
async function Pt(e) {
  const t = r("seoul-weather");
  t.replaceChildren(i("p", "\uC11C\uC6B8 \uC608\uBCF4 \uD655\uC778 \uC911", "seoul-weather-state"));
  function n(o, s, a) {
    let d = a && { \uB9D1\uC74C: "clear", "\uB300\uCCB4\uB85C \uB9D1\uC74C": "fair", "\uAD6C\uB984 \uC870\uAE08": "fair", "\uAD6C\uB984 \uB9CE\uC74C": "partlycloudy", \uD750\uB9BC: "cloud", \uC548\uAC1C: "fog", \uBE44: "rain", \uC18C\uB098\uAE30: "rain", \uB208: "snow", \uC9C4\uB208\uAE68\uBE44: "sleet", \uB1CC\uC6B0: "thunder" }[o] || "unknown";
    if (a && typeof s == "string") {
      const c = s.split("_")[0];
      d = { clearsky: "clear", fair: "fair", partlycloudy: "partlycloudy", cloudy: "cloud", fog: "fog" }[c] || (c.includes("thunder") ? "thunder" : c.includes("sleet") ? "sleet" : c.includes("snow") ? "snow" : c.includes("rain") ? "rain" : "unknown");
    }
    const p = z("svg", { viewBox: "0 0 48 48", class: "seoul-weather-icon", "aria-hidden": "true", focusable: "false", "data-condition": d });
    function m(c = 24, f = 24, _ = 8) {
      const A = z("g", { class: "seoul-icon-sun" });
      A.append(z("circle", { cx: c, cy: f, r: _ }));
      for (let q = 0; q < 8; q++) {
        const R = q * Math.PI / 4;
        A.append(z("line", { x1: (c + Math.cos(R) * (_ + 4)).toFixed(2), y1: (f + Math.sin(R) * (_ + 4)).toFixed(2), x2: (c + Math.cos(R) * (_ + 7)).toFixed(2), y2: (f + Math.sin(R) * (_ + 7)).toFixed(2) }));
      }
      p.append(A);
    }
    function u() {
      p.append(z("path", { d: "M12 31h24a8 8 0 0 0 1-16 11 11 0 0 0-21-3 9.5 9.5 0 0 0-4 19Z", class: "seoul-icon-cloud" }));
    }
    function I(c, f) {
      const _ = z("g", { class: "seoul-icon-snow" });
      for (let A = 0; A < 3; A++) {
        const q = A * Math.PI / 3;
        _.append(z("line", { x1: c - Math.cos(q) * 4, y1: f - Math.sin(q) * 4, x2: c + Math.cos(q) * 4, y2: f + Math.sin(q) * 4 }));
      }
      p.append(_);
    }
    if (d === "clear") m();
    else if (d === "unknown") p.append(z("circle", { cx: 24, cy: 24, r: 16, class: "seoul-icon-unknown" }), z("path", { d: "M18 19a6 6 0 1 1 9 5c-2 1-3 2-3 5", class: "seoul-icon-unknown" }), z("circle", { cx: 24, cy: 35, r: 1.5, class: "seoul-icon-unknown-dot" }));
    else {
      if ((d === "fair" || d === "partlycloudy") && m(17, 15, 7), u(), d === "rain" || d === "sleet") for (const c of d === "rain" ? [14, 24, 34] : [15, 25]) p.append(z("line", { x1: c, y1: 36, x2: c - 3, y2: 42, class: "seoul-icon-rain" }));
      if (d === "snow") for (const c of [15, 32]) I(c, 39);
      if (d === "sleet" && I(35, 39), d === "fog") for (const [c, f, _] of [[36, 9, 37], [41, 14, 41]]) p.append(z("line", { x1: f, y1: c, x2: _, y2: c, class: "seoul-icon-fog" }));
      d === "thunder" && p.append(z("path", { d: "m25 29-8 10h7l-3 8 13-13h-9l4-5Z", class: "seoul-icon-lightning" }));
    }
    return p;
  }
  try {
    const o = await Z("/workspace/seoul-weather");
    if (e !== K || !v || localStorage.getItem("besma_token") !== C) return;
    t.replaceChildren();
    const s = i("div", null, "seoul-weather-heading");
    if (s.append(i("strong", "\uC11C\uC6B8 \uB0A0\uC528"), i("span", "\uB0A0\uC9DC\uBCC4 \uC608\uBCF4 \xB7 \uD55C\uAD6D\uC2DC\uAC04")), t.append(s), !o.available || o.forecast_kind !== "point_forecast" || o.timezone !== "Asia/Seoul" || !Array.isArray(o.days)) {
      t.append(i("p", "\uC608\uBCF4\uB97C \uD655\uC778\uD558\uACE0 \uC788\uC2B5\uB2C8\uB2E4.", "seoul-weather-state"));
      return;
    }
    const a = /* @__PURE__ */ new Date(v.date + "T00:00:00Z"), l = i("div", null, "seoul-forecast");
    for (let u = 0; u < 7; u++) {
      const I = new Date(a);
      I.setUTCDate(a.getUTCDate() + u);
      const c = I.toISOString().slice(0, 10), f = o.days.find((P) => P.date === c), _ = i("div", null, "seoul-forecast-day" + (u === 0 ? " today" : ""));
      _.dataset.date = c;
      const A = typeof f?.forecast_at == "string" && f.forecast_at.startsWith(c + "T") && f.forecast_at.endsWith("+09:00") && /^([01]\d|2[0-3]):[0-5]\d$/.test(f.forecast_time || "") && f.forecast_at.slice(11, 16) === f.forecast_time, q = A && typeof f?.temperature == "number" && Number.isFinite(f.temperature) && f.temperature >= -70 && f.temperature <= 70 ? f.temperature : null, R = A && typeof f?.weather_label == "string" && f.weather_label ? f.weather_label : "\uD655\uC778 \uC911";
      _.append(i("small", (u === 0 ? "\uC624\uB298 " : new Intl.DateTimeFormat("ko-KR", { weekday: "short", timeZone: "UTC" }).format(I) + " ") + (I.getUTCMonth() + 1) + "." + I.getUTCDate(), "seoul-weather-date")), _.append(n(R, f?.symbol_code, A)), _.append(i("strong", q !== null ? q + "\u2103" : "\uAE30\uC628 \uD655\uC778 \uC911", "seoul-weather-temperature" + (q === null ? " missing" : ""))), _.append(i("span", R, "seoul-weather-condition"), i("small", A ? f.forecast_time + " \uC608\uBCF4" : "\uC2DC\uAC01 \uD655\uC778 \uC911", "seoul-weather-time")), l.append(_);
    }
    const d = i("p", null, "seoul-weather-source"), p = i("a", "MET Norway"), m = i("a", "CC BY 4.0");
    p.href = "https://api.met.no/weatherapi/locationforecast/2.0/documentation", m.href = "https://creativecommons.org/licenses/by/4.0/";
    for (const u of [p, m]) u.target = "_blank", u.rel = "noopener";
    d.append(p, document.createTextNode(" \xB7 "), m, document.createTextNode(" \xB7 \uC81C\uACF5 \uC2DC\uC810 \uC120\uD0DD")), o.updated_at && d.append(document.createTextNode(" \xB7 " + Ue(o.updated_at) + " \uBC1C\uD45C")), t.append(l, d);
  } catch {
    e === K && t.replaceChildren(i("strong", "\uC11C\uC6B8 \uB0A0\uC528"), i("p", "\uC608\uBCF4\uB97C \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.", "seoul-weather-state"));
  }
}
const st = ["\uC11C\uC6B8", "\uACBD\uAE30", "\uC778\uCC9C", "\uAC15\uC6D0\uAD8C", "\uCDA9\uCCAD\uAD8C", "\uD638\uB0A8\uAD8C", "\uC601\uB0A8\uAD8C", "\uC81C\uC8FC\uAD8C", "\uC8FC\uC18C \uD655\uC778 \uC911"], je = "besma-home-map-view-v3", G = "besma-home-map-return-v1";
let V = "";
const Ut = C && crypto.subtle ? crypto.subtle.digest("SHA-256", new TextEncoder().encode(C)).then((e) => {
  V = Array.from(new Uint8Array(e), (t) => t.toString(16).padStart(2, "0")).join("");
}).catch(() => {
}) : Promise.resolve();
function x(e = h) {
  if (!(!v || !V || localStorage.getItem("besma_token") !== C)) try {
    sessionStorage.setItem(je, JSON.stringify({ version: 3, owner: V, at: Date.now(), selected: T, selectedTeam: g, highlightedTeam: y, mapView: k, focused: e, query: E, mapTitle: le, attendanceGapsOpen: pe, camera: S?.state() || L?.camera, scroll: scrollY, sidebar: r("selected-site-slot").closest(".home-progress-panel").scrollTop, expanded: !!r("map-dialog").open }));
  } catch {
  }
}
function zt() {
  if (Pe) return null;
  Pe = true;
  try {
    const e = performance.getEntriesByType("navigation")[0]?.type, t = JSON.parse(sessionStorage.getItem(G) || "null");
    if (sessionStorage.removeItem(G), !["reload", "back_forward"].includes(e) && !(t?.owner === V && Date.now() - t.at >= 0 && Date.now() - t.at < 144e5)) return null;
    const n = JSON.parse(sessionStorage.getItem(je) || "null");
    return n?.version !== 3 || !V || n.owner !== V || !Number.isFinite(n.at) || Date.now() - n.at < 0 || Date.now() - n.at > 144e5 ? null : (T = ["\uC804\uCCB4", ...st].includes(n.selected) ? n.selected : "\uC804\uCCB4", g = ["favorites", "government", "handover", "all", "unconfirmed", "1", "2", "3", "4", "5", "6"].includes(n.selectedTeam) ? n.selectedTeam : "all", g === "favorites" && (g = "all", T = "\uC804\uCCB4", n.camera = null, n.focused = null, n.query = "", n.expanded = false, n.mapTitle = "\uC804\uAD6D"), y = ["all", "government", ...Object.keys(De)].includes(n.highlightedTeam) ? n.highlightedTeam : "all", k = ["all", "inspections", "needs-info"].includes(n.mapView) ? n.mapView : "all", pe = n.attendanceGapsOpen === true, h = v.sites.some((o) => o.code === n.focused) ? n.focused : null, E = typeof n.query == "string" ? n.query.slice(0, 100) : "", le = typeof n.mapTitle == "string" ? n.mapTitle.slice(0, 80) : "\uC804\uAD6D", n);
  } catch {
    return null;
  }
}
function Be(e) {
  we(), r("site-search-candidates")?.replaceChildren(), clearTimeout(Oe), te = "loading", tt.clear(e), nt.clear(e), et.clear(e), D.hidden = true, D.replaceChildren(), pe = false, jt(), ne.clear(), $ = false, fe.clear(), O = false, y = "all", Le.replaceChildren(), Fe?.abort(), S = null, se = null, v = null, J++, r("attendance-title").textContent = "\uCD9C\uC5ED\uC778\uC6D0", r("attendance-value").textContent = "\u2014", document.querySelector(".attendance-total>span").hidden = true, r("attendance-note").textContent = e, r("seoul-weather").replaceChildren(i("p", e, "seoul-weather-state")), r("site-map").replaceChildren(i("p", e, "home-empty"));
  for (const t of ["region-list", "map-sites", "selected-site"]) r(t).replaceChildren();
  r("notice-list").replaceChildren(i("p", e));
}
function Y(e) {
  const t = e.team;
  return typeof t == "object" && t ? String(t.key) : t ? String(t) : "unconfirmed";
}
function N() {
  const e = E.trim().normalize("NFKC").toLocaleLowerCase("ko");
  return ze().filter((t) => (T === "\uC804\uCCB4" || it(t) === T) && (g === "all" || g === "favorites" && ne.has(t.code) || g === "government" && t.is_government === true || g === "handover" && t.document_handover === true || Y(t) === g) && (k === "all" || k === "inspections" && H === "VERIFIED" && ge(t).length || k === "needs-info" && Qe(t)) && (!e || (t.name + " " + (t.address || "") + " " + (t.contacts || []).map((n) => [n.role, n.rank, n.name].filter(Boolean).join(" ")).join(" ")).normalize("NFKC").toLocaleLowerCase("ko").includes(e)));
}
function Ie(e) {
  le = !e || ["\uC990\uACA8\uCC3E\uAE30", "\uAD00\uAE09\uACF5\uC0AC", "\uC804\uCCB4", "\uC804\uAD6D"].includes(e) ? "\uC804\uAD6D" : e;
  const t = le === "\uC804\uAD6D" ? "\uD604\uC7A5 \uD604\uD669" : le + " \uD604\uC7A5 \uD604\uD669";
  r("map-title").textContent = t, r("map-dialog-title").textContent = t;
}
const ae = /* @__PURE__ */ new Map();
let He = new AbortController();
function jt() {
  He.abort(), He = new AbortController();
  for (const e of ae.values()) e.then((t) => URL.revokeObjectURL(t)).catch(() => {
  });
  ae.clear();
}
async function Bt(e, t) {
  const n = e.manager_photo, o = "/workspace/site-manager-photo/" + encodeURIComponent(e.code);
  if (!n || n.verified !== true || n.site_code !== e.code || n.contact_id !== t.contact_id || n.name !== t.name || n.url !== o) throw Error("\uC0AC\uC9C4 \uD655\uC778 \uC911");
  const s = e.code + ":" + t.contact_id + ":" + (n.content_sha256 || "");
  if (ae.has(s)) return ae.get(s);
  const a = J, l = He.signal, d = (async () => {
    const p = await fetch(de + o, { headers: { Authorization: "Bearer " + C }, credentials: "omit", redirect: "error", cache: "no-store", signal: l });
    if (!p.ok || p.headers.get("content-type")?.split(";")[0] !== "image/webp" || Number(p.headers.get("content-length") || 0) > 131072) throw Error("\uC0AC\uC9C4 \uD655\uC778 \uC911");
    const m = p.body.getReader(), u = [];
    let I = 0;
    try {
      for (; ; ) {
        const c = await m.read();
        if (c.done) break;
        if (I += c.value.byteLength, I > 131072) throw Error("\uC0AC\uC9C4 \uD655\uC778 \uC911");
        u.push(c.value);
      }
    } finally {
      await m.cancel(), m.releaseLock();
    }
    if (a !== J || localStorage.getItem("besma_token") !== C || l.aborted) throw Error("\uACC4\uC815 \uBCC0\uACBD");
    return URL.createObjectURL(new Blob(u, { type: "image/webp" }));
  })();
  return ae.set(s, d), d.catch(() => {
    ae.get(s) === d && ae.delete(s);
  }), d;
}
function lt(e, t) {
  const n = Ce(e), o = i("div", null, "site-photo-gallery"), s = i("figure", null, "site-project-picture"), a = i("figure", null, "site-manager-picture");
  if (n) {
    const p = i("img");
    if (p.src = n.url, p.alt = n.caption || e.name + " \uD604\uC7A5\uC0AC\uC9C4", p.referrerPolicy = "no-referrer", p.decoding = "async", p.loading = "lazy", p.onerror = () => {
      const u = n.rendering && Ce({ ...e, photo: n.rendering });
      if (u && p.dataset.fallback !== "true") {
        p.dataset.fallback = "true", p.src = u.url, p.alt = u.caption;
        const I = s.querySelector("figcaption");
        I && (I.textContent = u.caption);
      } else p.replaceWith(i("span", "\uD604\uC7A5 \uC0AC\uC9C4 \uD655\uC778 \uC911", "photo-placeholder"));
    }, s.append(p), n.rendering?.verified === true && n.rendering.site_code === e.code) {
      const u = Ce({ ...e, photo: n.rendering });
      if (u) {
        const I = i("div", null, "project-photo-tabs");
        I.append(B("\uACF5\uC0AC \uC0AC\uC9C4", () => {
          p.src = n.url, p.alt = n.caption, s.querySelector("figcaption").textContent = n.caption;
        }), B("\uC870\uAC10\uB3C4", () => {
          p.src = u.url, p.alt = u.caption, s.querySelector("figcaption").textContent = u.caption;
        })), s.append(I);
      }
    }
    const m = i("a", "\uC0AC\uC9C4 \uCD9C\uCC98 \u2197");
    m.href = n.source_url, m.target = "_blank", m.rel = "noopener noreferrer", s.append(m), n.caption && s.append(i("figcaption", n.caption));
  } else s.append(i("span", "\uD604\uC7A5 \uC0AC\uC9C4 \uD655\uC778 \uC911", "photo-placeholder"));
  const l = e.contacts?.find((p) => String(p.role || "").split("\xB7").includes("\uC18C\uC7A5"));
  a.append(i("figcaption", "\uD604\uC7A5\uC18C\uC7A5"));
  const d = i("span", l ? "\uC0AC\uC9C4 \uD655\uC778 \uC911" : "\uB2F4\uB2F9 \uD655\uC778 \uC911", "photo-placeholder");
  if (a.append(d), l && e.manager_photo) {
    const p = i("img");
    p.alt = "\uD604\uC7A5\uC18C\uC7A5 " + l.name, p.decoding = "async", p.onerror = () => p.replaceWith(d), Bt(e, l).then((m) => {
      t.isConnected && localStorage.getItem("besma_token") === C && (p.src = m, d.replaceWith(p));
    }).catch(() => {
    });
  }
  o.append(s, a), t.append(o);
}
function ct(e) {
  const t = r("map-hover");
  if (!e) {
    t?.remove();
    return;
  }
  const n = N().find((a) => a.code === e);
  if (!n) return;
  t?.remove();
  const o = i("aside", null, "map-hover");
  o.id = "map-hover", o.setAttribute("aria-label", "\uD604\uC7A5 \uC694\uC57D"), lt(n, o), o.append(i("strong", n.name), i("p", n.address || "\uC8FC\uC18C \uD655\uC778 \uC911"), i("p", n.today_people == null ? "\uC624\uB298 \uCD9C\uC5ED \uBBF8\uD655\uC778" : n.today_people + "\uBA85"));
  const s = $e(n.transport);
  s && o.append(s), r("home-map-slot").append(o);
}
function W(e, t) {
  const n = i("div");
  return n.append(i("dt", e), i("dd", String(t))), n;
}
function dt() {
  const e = N().filter(j);
  return /^[1-6]$/.test(y) ? e.filter((t) => Y(t) === y) : e;
}
function pt(e) {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  const t = dt();
  if (!t.length) return;
  const n = t.findIndex((s) => s.code === h), o = t[n < 0 ? e > 0 ? 0 : t.length - 1 : (n + e + t.length) % t.length];
  oe(o.code, { focusMap: true, present: true, editMissing: O });
}
function Ht() {
  r("map-dialog").open ? (r("selected-site-slot").append(r("selected-site")), r("map-site-info").hidden = true, requestAnimationFrame(() => {
    S?.map.resize(), S?.map.getCanvas().focus({ preventScroll: true });
  })) : (document.querySelector(".map-panel").scrollIntoView({ block: "start", behavior: "smooth" }), S?.map.getCanvas().focus({ preventScroll: true })), x();
}
function Vt(e) {
  const t = i("p", "\uC810\uAC80\uC77C " + e.scheduled_date + (e.due_date && e.due_date !== e.scheduled_date ? " ~ " + e.due_date : "") + (e.owner_name ? " \xB7 " + e.owner_name : ""), "inspection-badge site-inspection-date");
  return t.style.color = "#203d50", t;
}
function ut(e) {
  const t = i("nav", null, "site-quick-actions");
  t.setAttribute("aria-label", e.name + " \uC9C0\uB3C4\xB7\uC804\uD654"), t.style.cssText = "display:flex;gap:6px 12px;flex-wrap:wrap;align-items:center;padding:8px 0;margin:0 0 8px;border-bottom:1px solid #d6e0e5;font-size:14px";
  const n = i("a");
  Ye(n, e, w), n.textContent = "\uC9C0\uB3C4\xB7\uAE38\uCC3E\uAE30", n.style.cssText = "min-height:36px;display:inline-flex;align-items:center;font-weight:600", t.append(n);
  const o = /* @__PURE__ */ new Set();
  for (const s of ["\uC18C\uC7A5", "\uACF5\uBB34", "\uC548\uC804"]) {
    const a = e.contacts?.find((m) => String(m.role || "").split("\xB7").some((u) => u.trim() === s) && /^\+?\d{7,15}$/.test(String(m.phone || "").replace(/[^+\d]/g, "")));
    if (!a) continue;
    const l = String(a.phone), d = l.replace(/[^+\d]/g, "");
    if (o.has(d)) continue;
    o.add(d);
    const p = i("a", s + " " + [a.rank, a.name].filter(Boolean).join(" ") + " " + l);
    p.href = "tel:" + d, p.style.cssText = "min-height:36px;display:inline-flex;align-items:center", t.append(p);
  }
  return t;
}
function Wt(e) {
  const t = i("nav", null, "site-quick-actions site-evaluation-links");
  if (t.setAttribute("aria-label", e.name + " \uB0B4 \uD3C9\uAC00"), H !== "VERIFIED") return t;
  const n = ge(e);
  for (const o of n) {
    let s;
    try {
      s = Ge(o);
    } catch {
      continue;
    }
    const a = i("a", n.length === 1 ? "\uD3C9\uAC00 \uC5F4\uAE30" : o.scheduled_date + " \uD3C9\uAC00 \uC5F4\uAE30");
    a.href = s, a.dataset.mapEvaluationPlan = o.public_id, a.style.cssText = "display:inline-flex;align-items:center;min-height:44px;padding:0 14px;border-radius:7px;background:#c86d2e;color:#fff;font-weight:700;text-decoration:none", a.onclick = (l) => {
      if (localStorage.getItem("besma_token") !== C) {
        l.preventDefault(), w("\uB85C\uADF8\uC778 \uACC4\uC815\uC744 \uD655\uC778\uD558\uACE0 \uB2E4\uC2DC \uC5F4\uC5B4 \uC8FC\uC138\uC694.");
        return;
      }
      x(e.code);
      try {
        sessionStorage.setItem(G, JSON.stringify({ owner: V, at: Date.now() }));
      } catch {
      }
    }, t.append(a);
  }
  return t;
}
function oe(e, { focusMap: t = false, scroll: n = false, editMissing: o = false, present: s = false } = {}) {
  const a = v?.sites.find((b) => b.code === e);
  if (!a) return;
  if (F()) {
    h !== e ? w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.") : s && (matchMedia("(max-width:740px)").matches || document.getElementById("map-dialog").open) && (Ae(), document.getElementById("map-site-info").hidden = false, document.getElementById("map-site-info").append(document.getElementById("selected-site")));
    return;
  }
  h = e;
  dispatchEvent(new Event("besma-home-selection"));
  const l = r("selected-site");
  if (l.replaceChildren(), l.dataset.siteCode = e, a.document_handover) {
    const b = i("p", "\uBB38\uC11C\uC774\uAD00 \uB300\uC0C1 \xB7 \uC900\uACF5 \uC608\uC815 " + a.planned_end_date, "site-handover");
    b.style.cssText = "background:#fff0d1;color:#744000;border-left:5px solid #d97706;padding:10px;font-weight:700", l.append(b);
  }
  if ((k === "inspections" ? ge(a) : a.inspections)?.length) for (const b of k === "inspections" ? ge(a) : a.inspections) l.append(Vt(b));
  const d = i("nav", null, "site-navigation");
  d.setAttribute("aria-label", "\uC120\uD0DD \uBC94\uC704\uC758 \uD604\uC7A5 \uC774\uB3D9");
  const p = B("\uC774\uC804 \uD604\uC7A5", () => pt(-1)), m = B("\uB2E4\uC74C \uD604\uC7A5", () => pt(1)), u = dt(), I = u.findIndex((b) => b.code === e), c = i("span", (I < 0 ? "\u2014" : I + 1) + " / " + u.length);
  p.disabled = m.disabled = u.length < 2, p.dataset.siteStep = "previous", m.dataset.siteStep = "next", c.setAttribute("aria-label", "\uC120\uD0DD \uBC94\uC704\uC758 \uD604\uC7A5 \uC21C\uC11C"), d.append(p, c, m, B("\uC9C0\uB3C4\uB85C \uB3CC\uC544\uAC00\uAE30", Ht)), l.append(d), l.append(i("span", Ot(a), "site-kind " + Lt(a)));
  const f = i("div", null, "selected-site-heading");
  f.append(i("h3", a.name)), l.append(f, Wt(a), ut(a));
  const _ = i("div", null, "home-site-links"), A = vt(a);
  A.onclick = () => x(a.code), _.append(A), l.append(_), a.description && l.append(i("p", a.description, "site-description"));
  const q = Ct({ site: a, role: re, token: C, onSaved: async () => {
    await Ne();
  }, onNotice: w, isCurrent: () => h === a.code && v !== null && localStorage.getItem("besma_token") === C, open: o || O });
  q && l.append(q), lt(a, l);
  const R = $e(a.transport);
  R && l.append(R);
  const P = i("dl", null, "site-facts");
  P.append(W("\uD604\uC7A5 \uCF54\uB4DC", a.code), W("\uC8FC\uC18C", a.address || "\uC8FC\uC18C \uD655\uC778 \uC911"), W("\uCD9C\uC5ED", a.today_people == null ? "\uC624\uB298 \uCD9C\uC5ED \uBBF8\uD655\uC778" : a.today_people.toLocaleString("ko-KR") + "\uBA85"), W("\uB2F4\uB2F9 \uD300", a.team?.label || "\uD300 \uD655\uC778 \uC911")), a.contractor && P.append(W("\uC6D0\uB3C4\uAE09\uC0AC", a.contractor)), a.location_precision === "locality" ? P.append(W("\uC9C0\uB3C4 \uC704\uCE58", "\uB3D9\xB7\uC74D\xB7\uBA74 \uAE30\uC900")) : a.location_precision === "range" ? P.append(W("\uC9C0\uB3C4 \uC704\uCE58", "\uACF5\uC0AC \uAD6C\uAC04 \uB300\uD45C \uC704\uCE58")) : a.location_precision === "municipality" ? P.append(W("\uC9C0\uB3C4 \uC704\uCE58", "\uC2DC\xB7\uAD70 \uAE30\uC900")) : a.location_precision === "region" ? P.append(W("\uC9C0\uB3C4 \uC704\uCE58", "\uAD8C\uC5ED \uB300\uD45C \uC704\uCE58")) : j(a) || P.append(W("\uC9C0\uB3C4 \uC704\uCE58", "\uD655\uC778 \uC911"));
  for (const b of a.details || []) {
    if (!b || !b.label || b.value == null || b.value === "" || ["address", "contractor", "site_code", "site_name", "name"].includes(b.key)) continue;
    let U = b.value;
    typeof U != "object" && P.append(W(b.label, String(U) + (b.unit ? " " + b.unit : "")));
  }
  if (l.append(P), a.contacts?.length) {
    const b = i("section", null, "site-contacts");
    b.append(i("h4", "\uC5F0\uB77D\uCC98"));
    for (const U of a.contacts) {
      const Q = i("div"), Re = [U.role, U.rank, U.name].filter(Boolean).join(" ") || U.label;
      Q.append(i("span", Re || "\uB2F4\uB2F9\uC790"));
      const X = String(U.phone || ""), ee = X.replace(/[^+\d]/g, "");
      if (ee && /^\+?\d{7,15}$/.test(ee)) {
        const be = i("a", X);
        be.href = "tel:" + ee, Q.append(be);
      } else X && Q.append(i("span", X));
      b.append(Q);
    }
    l.append(b);
  }
  if (a.contracts?.length) {
    const b = i("section", null, "site-contracts");
    b.append(i("h4", "\uACF5\uC0AC\uACC4\uC57D"));
    for (const U of a.contracts) {
      const Q = i("details"), Re = i("summary", U.name || "\uACC4\uC57D \uB0B4\uC5ED"), X = i("dl", null, "site-facts");
      for (const [ee, be] of [["amount", "\uACC4\uC57D\uAE08\uC561"], ["basis", "\uAE30\uC900"], ["start", "\uCC29\uACF5"], ["end", "\uC900\uACF5"]]) U[ee] != null && U[ee] !== "" && X.append(W(be, U[ee]));
      Q.append(Re, X), b.append(Q);
    }
    l.append(b);
  }
  const Ze = i("div", null, "home-site-links"), Je = i("a"), ve = i("a", "\uD604\uC7A5\uC548\uC804\uAE30\uC900"), Me = i("a", "\uD604\uC7A5 \uC815\uBCF4");
  Ye(Je, a, w), ve.href = "/workspace.html#contractors?" + new URLSearchParams({ company: St(a), client: a.client || "", contractor: a.contractor || "", site: a.code }), ve.dataset.action = "site-safety-standards", Me.href = "/workspace.html#sites?site=" + encodeURIComponent(a.code), ve.onclick = Me.onclick = () => x(a.code), Ze.append(Je, ve, Me), l.append(Ze, _t({ site: a, request: Z, role: re, isCurrent: () => h === a.code && v !== null && localStorage.getItem("besma_token") === C })), Y(a) === "unconfirmed" && l.append(i("p", "\uB2F4\uB2F9\uD300\uC740 \uD604\uC7A5 \uC6D0\uC7A5 \uD655\uC778\uC774 \uD544\uC694\uD569\uB2C8\uB2E4.", "site-info-note")), !j(a) && a.address && l.append(i("p", "\uC8FC\uC18C\uC5D0 \uB9DE\uB294 \uC9C0\uB3C4 \uC704\uCE58\uB294 \uD655\uC778 \uC911\uC785\uB2C8\uB2E4.", "site-info-note"));
  const qe = i("div", null, "home-weather");
  qe.append(B("\uD604\uC7A5 \uB0A0\uC528 \uBCF4\uAE30", () => Ft(a, qe, J))), l.append(qe), S?.highlight?.(e), t && j(a) && S?.select(e);
  for (const b of r("map-sites").children) b.classList.toggle("selected", b.dataset.siteCode === e);
  x(), s && (matchMedia("(max-width:740px)").matches || r("map-dialog").open) ? (Ae(), r("map-site-info").hidden = false, r("map-site-info").append(l), r("map-site-info").scrollTop = 0) : n && l.scrollIntoView({ block: "nearest", behavior: "smooth" });
}
function Ve() {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  T = "\uC804\uCCB4", g = "all", y = "all", k = "all", O = false, h = null, E = "", r("home-site-query").value = "", r("selected-site-slot").append(r("selected-site")), r("map-site-info").hidden = true, S?.highlight?.(null), Ie("\uC804\uAD6D"), M(), matchMedia("(max-width:740px)").matches ? S?.reset({ flat: !r("map-dialog").open }) : S?.fitSites(N(), { name: "\uC804\uAD6D", maxZoom: 9 }), x();
}
function M() {
  dispatchEvent(new Event("besma-home-selection"));
  if (F() || !v) return;
  const e = ze(), t = N();
  Gt(e, t);
  const n = Le, o = i("details", null, "map-legend-panel"), s = i("summary"), a = i("div", null, "map-legend-options"), l = k === "inspections" ? H === "VERIFIED" ? "\uB0B4 \uC810\uAC80 \xB7 \uC9C0\uB3C4 " + t.filter(j).length + "\uACF3" + (ye().pending ? " \xB7 \uC5F0\uACB0 \uD655\uC778 " + ye().pending + "\uAC74" : "") : "\uB0B4 \uC810\uAC80 \uD655\uC778 \uC911" : g === "favorites" ? "\uC990\uACA8\uCC3E\uAE30 (" + t.length + ")" : g === "government" ? "\uAD00\uAE09 (" + t.length + ")" : g === "handover" ? "\uBB38\uC11C\uC774\uAD00 \uB300\uC0C1 (" + t.length + ")" : y === "all" ? "\uC804\uCCB4 (" + t.length + ")" : y === "unconfirmed" ? "\uBBF8\uD655\uC778" : y + "\uD300 \uAC15\uC870";
  s.textContent = "\uD604\uC7A5 \uC120\uD0DD \xB7 " + l, o.open = !matchMedia("(max-width:740px)").matches, o.append(s, a), n.replaceChildren(o);
  const d = i("p");
  d.style.cssText = "font-size:12px;line-height:1.5;margin:8px 0 0;color:#263544", d.textContent = ke || "", !ke && t.some((c) => c.transport) && (d.textContent = "\uC8FC\uD669 \uD14C\uB450\uB9AC: \uCC28\uB7C9 \uC6B0\uC120 \uAC80\uD1A0 \xB7 \uBCF4\uB77C \uD14C\uB450\uB9AC: \uCD9C\uC785\uAD6C \uD655\uC778"), d.textContent && o.append(d);
  function p(c, f, _, A, q) {
    const R = B(f, () => {
      if (F()) {
        w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
        return;
      }
      A();
    }, "team-legend-button");
    R.dataset.teamKey = c, R.setAttribute("aria-pressed", String(q));
    const P = i("i");
    return P.style.background = _, R.prepend(P), a.append(R), R;
  }
  for (const c of ["all", "1", "2", "3", "4", "5", "6"]) {
    const f = c === "all" ? e.length : e.filter((_) => Y(_) === c).length;
    p(c, (c === "all" ? "\uC804\uCCB4" : c + "\uD300") + " (" + f + ")", c === "all" ? "#667b82" : De[c], () => {
      if (c === "all") {
        Ve();
        return;
      }
      Mt(c);
    }, g !== "favorites" && y === c);
  }
  const m = p("government", "\uAD00\uAE09 (" + e.filter((c) => c.is_government === true).length + ")", "transparent", Rt, g === "government");
  m.classList.add("government-outline"), m.title = "\uAD00\uAE09\uACF5\uC0AC\uB9CC \uBCF4\uAE30 \xB7 \uB2E4\uC2DC \uB204\uB974\uBA74 \uC804\uCCB4 \uD604\uC7A5", p("handover", "\uBB38\uC11C\uC774\uAD00 \uB300\uC0C1 (" + e.filter((c) => c.document_handover === true).length + ")", "#d97706", () => {
    T = "\uC804\uCCB4", k = "all", g = g === "handover" ? "all" : "handover", y = "all", h = null, E = "", r("home-site-query").value = "", M(), ce(), x();
  }, g === "handover"), p("unconfirmed", "\uBBF8\uD655\uC778 (" + e.filter((c) => Y(c) === "unconfirmed").length + ")", De.unconfirmed, () => {
    y = "unconfirmed", g = "unconfirmed", h = null, O = true, M(), x();
  }, g === "unconfirmed"), a.append(i("small", g === "favorites" ? "\uBCC4\uD45C\uB85C \uAC04\uD3B8 \uC124\uC815\xB7\uD574\uC81C" : y === "all" ? "\uD300\uC744 \uB204\uB974\uBA74 \uAC15\uC870" : y === "unconfirmed" ? "\uB2F4\uB2F9\uD300 \uD655\uC778 \uD544\uC694" : y === "government" ? "\uAD00\uAE09\uACF5\uC0AC \uAC15\uC870" : y + "\uD300 \uAC15\uC870"));
  if (/^[1-6]$/.test(y)) {
    const list=i("section",null,"map-team-sites");list.setAttribute("aria-label",y+"팀 현장 목록");list.append(i("h3",y+"팀 현장"));
    for(const site of t.filter(site=>Y(site)===y)) {const row=B(site.name,()=>{oe(site.code,{focusMap:true,present:true});for(const item of list.querySelectorAll("button"))item.setAttribute("aria-current",String(item.dataset.siteCode===site.code));});row.dataset.siteCode=site.code;row.setAttribute("aria-current",String(site.code===h));if(!j(site))row.append(i("small","위치 확인 필요"));list.append(row);}
    n.append(list);
  }
  const u = ["1", "2", "3", "4", "5", "6", "unconfirmed"].map((c) => ({ key: c, label: c === "unconfirmed" ? "\uD300 \uD655\uC778 \uC911" : "\uACF5\uC0AC" + c + "\uD300", site_count: v.sites.filter((f) => Y(f) === c).length, map_site_count: e.filter((f) => Y(f) === c).length }));
  if (S?.setSites(t), S?.setFavoriteView?.(g === "favorites"), S?.setHighlightedTeam?.(y), r("map-caption").textContent = (g === "government" ? "\uAD00\uAE09\uACF5\uC0AC \xB7 " : "") + "\uD45C\uC2DC \uB300\uC0C1 " + t.length + "\uAC1C \xB7 \uC704\uCE58 \uD655\uC778 \uC911 " + t.filter((c) => !j(c)).length + " \xB7 \uC8FC\uC18C \uBBF8\uB4F1\uB85D " + v.sites.filter((c) => !c.address?.trim()).length + "\uAC1C" + (v.sites.length > e.length ? " \xB7 \uC120\uACF5\uC0AC\xB7\uC784\uC2DC\uB3D9\uB825\xB7\uAC00\uC124 " + (v.sites.length - e.length) + "\uAC1C \uC9C0\uB3C4 \uC81C\uC678" : ""), k === "inspections" && ye().known) {
    const c = ye();
    r("map-caption").textContent = "\uB0B4 \uC810\uAC80 " + c.total + "\uAC74 \xB7 \uC9C0\uB3C4 " + t.filter(j).length + "\uACF3" + (c.pending ? " \xB7 \uC9C0\uB3C4 \uC5F0\uACB0 \uD655\uC778 " + c.pending + "\uAC74. \uC67C\uCABD \uB0B4 \uC810\uAC80 \uBAA9\uB85D\uC5D0\uC11C \uD655\uC778\uD558\uC138\uC694." : "");
  }
  k === "inspections" && H !== "VERIFIED" && (r("map-caption").textContent = te === "error" || H === "UNKNOWN" ? "\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uD655\uC778\uD574 \uC8FC\uC138\uC694." : "\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uACE0 \uC788\uC2B5\uB2C8\uB2E4.");
  const I = r("map-sites");
  I.replaceChildren();
  for (const c of t) {
    const f = i("article", null, "home-site" + (c.code === h ? " selected" : ""));
    f.dataset.siteCode = c.code;
    const _ = i("div", null, "home-site-heading"), A = B(c.name, () => oe(c.code, { focusMap: true, scroll: true, present: true, editMissing: O }), "site-select");
    A.dataset.siteCode = c.code, _.append(A), c.inspections?.length && _.append(i("span", "\uC810\uAC80\uC608\uC815", "inspection-badge")), f.append(_, i("p", c.address || "\uC8FC\uC18C \uD655\uC778 \uC911"), i("small", c.today_people == null ? "\uCD9C\uC5ED \uBBF8\uD655\uC778" : c.today_people + "\uBA85")), I.append(f);
  }
  t.length || I.append(i("p", k === "inspections" ? Nt() : g === "favorites" ? "\uC990\uACA8\uCC3E\uB294 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4. \uC804\uCCB4\uC5D0\uC11C \uBCC4\uD45C\uB97C \uB20C\uB7EC \uCD94\uAC00\uD558\uC138\uC694." : "\uC870\uAC74\uC5D0 \uB9DE\uB294 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.")), !h && t.length && (g === "favorites" || O) && (h = (O ? t.find(Qe) : t.find(Ce))?.code || t[0].code), h && t.some((c) => c.code === h) ? oe(h, { editMissing: O }) : (r("selected-site").replaceChildren(i("p", "\uC9C0\uB3C4\uB098 \uBAA9\uB85D\uC5D0\uC11C \uD604\uC7A5\uC744 \uC120\uD0DD\uD558\uC138\uC694.")), r("selected-site").removeAttribute("data-site-code"), h = null, S?.highlight?.(null)), Kt(t), ct(null);
}
async function Ee() {
  if (S) return S;
  if (se) return se;
  Fe = new AbortController();
  const e = Fe.signal;
  return r("site-map").replaceChildren(), se = It({ container: r("site-map"), sites: N(), legendElement: Le, signal: e, onSelect: (t) => oe(t, { scroll: true, present: true }), onHover: ct, onRegion: (t, n) => {
    Ie(t), n?.kind === "admin" && !n.restore && (T = "\uC11C\uC6B8", h = null, M());
  }, onStatus: (t) => {
    r("map-status").textContent = t;
  } }).then((t) => {
    if (e.aborted) return t.dispose(), null;
    S = t, t.setSites(N());
    const n = matchMedia("(max-width:740px)").matches && !r("map-dialog").open;
    return L?.camera ? (!L.camera.viewPreset && T === "\uC804\uCCB4" && !h && !E ? t.reset({ flat: n }) : t.restoreCamera?.(L.camera), T === "\uC11C\uC6B8" && t.state().lockedRegion !== "\uC11C\uC6B8" && t.regionByName("\uC11C\uC6B8", { fit: false }), Ie(le)) : g === "favorites" ? t.fitSites(N(), { name: "\uC990\uACA8\uCC3E\uAE30" }) : t.fitSites(N(), { name: "\uC804\uAD6D", maxZoom: 9 }), E.trim() && ce(), t.map.on("moveend", () => x()), h && t.highlight?.(h), t.setTerrain(L?.camera ? L.camera.terrain !== false : true), r("map-tilt").setAttribute("aria-pressed", String(t.state().pitch > 0)), r("map-terrain").setAttribute("aria-pressed", String(t.state().terrain)), Te(), t.setFavoriteView?.(g === "favorites"), t.setHighlightedTeam?.(y), x(), t;
  }).catch((t) => (e.aborted || (r("site-map").replaceChildren(i("p", t.message || "\uC9C0\uB3C4\uB97C \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.", "home-empty")), r("map-status").textContent = "\uD604\uC7A5 \uC815\uBCF4\uB294 \uC67C\uCABD \uBAA9\uB85D\uC5D0\uC11C \uD655\uC778\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4."), null)).finally(() => {
    se = null;
  }), se;
}
function Te() {
  const e = matchMedia("(max-width:740px)").matches && !r("map-dialog").open;
  r("home-map-slot").classList.toggle("compact", e);
  const t = S?.map;
  if (!t) return;
  for (const o of ["scrollZoom", "dragPan", "boxZoom", "doubleClickZoom", "touchZoomRotate", "keyboard"]) t[o]?.[e ? "disable" : "enable"]();
  const n = matchMedia("(max-width:740px)").matches;
  t.setPaintProperty("site-points", "circle-radius", n ? ["interpolate", ["linear"], ["zoom"], 5, 3, 8, 4.5, 11, 7.5, 14, 11] : ["interpolate", ["linear"], ["zoom"], 5, 4, 8, 6, 10, 9, 14, 14]), t.setPaintProperty("site-halo", "circle-radius", n ? ["interpolate", ["linear"], ["zoom"], 5, 4.5, 8, 6, 11, 10, 14, 15] : ["interpolate", ["linear"], ["zoom"], 5, 6, 8, 9, 10, 12, 14, 19]), t.setLayoutProperty("site-team", "text-size", n ? ["interpolate", ["linear"], ["zoom"], 8, 0, 9, 9, 14, 11] : ["interpolate", ["linear"], ["zoom"], 7, 0, 9, 9, 14, 12]), t.resize();
}
function Ae() {
  const e = r("map-dialog");
  e.open || (r("expanded-map").append(r("site-map")), e.showModal(), Te(), requestAnimationFrame(() => S?.map.resize()), x());
}
function ft() {
  r("map-dialog").open && r("map-dialog").close();
}
async function Ne() {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  const e = ++K;
  try {
    const t = (u) => Z(u, { signal: AbortSignal.timeout(15e3) }), n = Promise.allSettled([t("/workspace/sites")]).then(([u]) => u), [o, s] = await Promise.allSettled([t("/workspace/home"), t("/workspace/bootstrap")]);
    if (o.status !== "fulfilled") throw o.reason;
    const a = { ...o.value, sites: o.value.sites.filter((site) => /\p{L}/u.test(String(site.name ?? "").normalize("NFKC"))) };
    if (await Ut, e !== K || localStorage.getItem("besma_token") !== C) return;
    re = s.status === "fulfilled" ? s.value.user?.role : null, bt(s.status === "fulfilled" ? s.value : null), et.refresh(a, re), tt.refresh(a, re), nt.refresh(a, s.status === "fulfilled" ? s.value.user : null), Et.refresh(s.status === "fulfilled" ? s.value : null);
    const l = xt(a.attendance, a.date);
    Tt(a, l), r("attendance-title").textContent = l.heading, r("attendance-value").textContent = l.people === null ? "\uC218\uC9D1 \uB300\uAE30" : l.people.toLocaleString("ko-KR"), document.querySelector(".attendance-total>span").hidden = l.people === null, r("attendance-note").textContent = l.note, document.querySelector(".attendance-block").dataset.state = l.state, r("home-date").textContent = a.date.replaceAll("-", ".");
    const d = await n;
    if (e !== K || localStorage.getItem("besma_token") !== C) return;
    v = a, dispatchEvent(new CustomEvent("besma-home-refreshed",{detail:a})), queueMicrotask(xe), ke = "", $ = d.status === "fulfilled" && Array.isArray(d.value.items), $ && (ne = new Set(d.value.items.filter((u) => u.favorite === true).map((u) => u.code)));
    const p = !Pe;
    L = zt() || L, p && !L && (g = "all"), $ || w("\uC990\uACA8\uCC3E\uAE30\uB97C \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uC804\uCCB4 \uD604\uC7A5\uC5D0\uC11C \uACC4\uC18D \uCC3E\uC744 \uC218 \uC788\uC2B5\uB2C8\uB2E4."), r("home-site-query").value = E, Pt(e), $t(e), Yt(e);
    const m = document.querySelector(".company-header .login");
    if (m.href = "/workspace.html", m.firstChild.textContent = "\uC5C5\uBB34\uACF5\uAC04\uC73C\uB85C ", document.querySelector(".hero-button").href = "/workspace.html", await Dt(), k === "inspections") try {
      if (await Ke(), e !== K || localStorage.getItem("besma_token") !== C) return;
      L?.focused && v.sites.some((u) => u.code === L.focused) && (h = L.focused), xe();
    } catch (u) {
      w(u.message || "\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uB20C\uB7EC \uC8FC\uC138\uC694.");
    }
    if (M(), await Ee(), Ke().catch(() => {
    }), L) {
      L.expanded && matchMedia("(max-width:740px)").matches && Ae();
      const u = L;
      L = null, requestAnimationFrame(() => {
        scrollTo({ top: Number.isFinite(u.scroll) ? Math.max(0, Math.min(5e4, u.scroll)) : 0, behavior: "instant" }), Number.isFinite(u.sidebar) && (document.querySelector(".home-progress-panel").scrollTop = Math.max(0, u.sidebar));
      });
    }
  } catch (t) {
    e === K && Be(t.message);
  }
}
r("home-site-query").oninput = (e) => {
  e.isComposing || mt(e.target);
}, r("home-site-query").addEventListener("compositionend", (e) => mt(e.target)), r("home-site-query").addEventListener("keydown", (e) => {
  if (!e.isComposing) if (e.key === "ArrowDown") {
    const t = r("site-search-candidates")?.querySelector("button");
    t && (e.preventDefault(), t.focus());
  } else e.key === "Escape" ? we() : e.key === "Enter" && N().length > 0 && (e.preventDefault(), We(N()[0]));
}), r("refresh-home").onclick = () => {
  if (F()) {
    w("\uC785\uB825\uD55C \uC815\uBCF4\uB97C \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  Ne();
}, r("map-reset").onclick = Ve, r("map-tilt").onclick = (e) => {
  const t = e.currentTarget.getAttribute("aria-pressed") !== "true";
  e.currentTarget.setAttribute("aria-pressed", String(t)), S?.setTilt(t);
}, r("map-terrain").onclick = (e) => {
  const t = e.currentTarget.getAttribute("aria-pressed") !== "true";
  e.currentTarget.setAttribute("aria-pressed", String(t)), S?.setTerrain(t);
}, r("open-map").onclick = Ae, r("close-map").onclick = ft, r("map-dialog").addEventListener("close", () => {
  r("selected-site-slot").append(r("selected-site")), r("map-site-info").hidden = true, r("home-map-slot").prepend(r("site-map")), Te(), requestAnimationFrame(() => S?.map.resize()), x(), r("open-map").focus();
}), addEventListener("pagehide", () => x()), document.addEventListener("click", (e) => {
  const t = e.target.closest('a[href^="/workspace.html#sites?"],a[href^="/workspace.html#requests"]');
  if (t) {
    const n = new URLSearchParams(t.href.split("?")[1] || "");
    x(t.dataset.homePreserveFocus === "true" ? h : n.get("site") || h);
    try {
      sessionStorage.setItem(G, JSON.stringify({ owner: V, at: Date.now() }));
    } catch {
    }
  }
}), matchMedia("(max-width:740px)").addEventListener("change", Te), addEventListener("storage", (e) => {
  if (e.key === "besma_token") {
    K++, Se.clear();
    try {
      sessionStorage.removeItem(je), sessionStorage.removeItem(G);
    } catch {
    }
    ft(), Be("\uB85C\uADF8\uC778 \uACC4\uC815\uC774 \uBCC0\uACBD\uB418\uC5C8\uC2B5\uB2C8\uB2E4. \uD654\uBA74\uC744 \uB2E4\uC2DC \uC5F4\uC5B4 \uC8FC\uC138\uC694.");
  }
}), C ? Ne() : Be("\uBCF8\uC0AC \uB85C\uADF8\uC778 \uD6C4 \uD655\uC778\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4."), setInterval(() => {
  C && document.visibilityState === "visible" && localStorage.getItem("besma_token") === C && !F() && Ne();
}, 12e4), r("expanded-map-reset").onclick = () => r("map-reset").click();
function we() {
  const e = r("site-search-candidates");
  e && (e.hidden = true), r("home-site-query").setAttribute("aria-expanded", "false");
}
function We(e) {
  we(), oe(e.code, { focusMap: true, scroll: false, present: "map" }), Ee().then((t) => {
    h === e.code && (t?.setSites(N()), j(e) && t?.select(e.code));
  });
}
function Kt(e) {
  let t = r("site-search-candidates");
  if (t || (t = i("div", null, "site-search-candidates"), t.id = "site-search-candidates", t.setAttribute("role", "region"), t.setAttribute("aria-label", "\uD604\uC7A5 \uAC80\uC0C9 \uD6C4\uBCF4"), r("home-site-query").after(t), r("home-site-query").setAttribute("aria-controls", t.id)), t.replaceChildren(), t.hidden = !E.trim(), r("home-site-query").setAttribute("aria-expanded", String(!t.hidden)), t.hidden) return;
  const n = i("p", "\uAC80\uC0C9 \uACB0\uACFC " + e.length + "\uAC1C", "site-search-count");
  n.setAttribute("role", "status");
  const o = i("div", null, "site-search-head"), s = B("\xD7", we, "site-search-close");
  s.setAttribute("aria-label", "\uAC80\uC0C9 \uD6C4\uBCF4 \uB2EB\uAE30"), o.append(n, s), t.append(o);
  for (const a of e) {
    const l = B(a.name, () => We(a), "site-search-option");
    if (l.dataset.siteCode = a.code, l.append(i("small", a.address || "\uC8FC\uC18C \uD655\uC778 \uC911")), E.trim().length >= 2) {
      const p = (a.contacts || []).filter((m) => String(m.name || "").normalize("NFKC").includes(E.trim().normalize("NFKC")));
      p.length && l.append(i("small", p.map((m) => [m.role, m.rank, m.name].filter(Boolean).join(" ")).join(" \xB7 ")));
    }
    const d = i("div", null, "site-search-result");
    d.append(l, ut(a)), t.append(d);
  }
  e.length || t.append(i("p", "\uC77C\uCE58\uD558\uB294 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4."));
}
function ce() {
  if (!S || !v) return;
  const e = N();
  if (!e.some(j)) {
    w(e.length ? "\uC9C0\uB3C4 \uC704\uCE58\uAC00 \uD655\uC778\uB418\uC9C0 \uC54A\uC740 \uD604\uC7A5\uC785\uB2C8\uB2E4. \uAC80\uC0C9 \uD6C4\uBCF4\uC5D0\uC11C \uD604\uC7A5 \uC815\uBCF4\uB97C \uD655\uC778\uD558\uC138\uC694." : "\uC870\uAC74\uC5D0 \uB9DE\uB294 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.");
    return;
  }
  S.fitSites(e, { name: k === "inspections" ? "\uB0B4 \uC810\uAC80" : E.trim() ? "\uAC80\uC0C9 \uACB0\uACFC" : T === "\uC804\uCCB4" ? "\uC804\uAD6D" : T, maxZoom: e.length === 1 ? 15 : E.trim() ? 13 : 9 }), x();
}
function mt(e) {
  if (F()) {
    e.value = E, w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  E = e.value.slice(0, 100), T = "\uC804\uCCB4", g = "all", y = "all", k = "all", h = null, O = false, M(), clearTimeout(Oe);
  const t = E, n = J;
  Oe = setTimeout(() => {
    if (t === E && n === J) {
      const o = N();
      o.length === 1 && t.trim() ? We(o[0]) : ce();
    }
  }, 320), x();
}
function Zt(e) {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  if (e === "inspections" && te !== "ready") {
    w("\uD655\uC815 \uC810\uAC80\uC77C\uC815\uC744 \uBA3C\uC800 \uD655\uC778\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  T = "\uC804\uCCB4", g = "all", y = "all", k = e, h = null, E = "", O = false, r("home-site-query").value = "", M(), ce(), x();
}
async function Jt() {
  if (F()) {
    w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
    return;
  }
  T = "\uC804\uCCB4", g = "all", y = "all", k = "inspections", h = null, E = "", O = false, r("home-site-query").value = "", we(), Ie("\uB0B4 \uC810\uAC80"), w("\uB2E4\uC74C \uD3C9\uAC00 \uD604\uC7A5\uC744 \uD655\uC778\uD558\uACE0 \uC788\uC2B5\uB2C8\uB2E4."), M();
  try {
    if (await Ke(), k !== "inspections" || !v) return;
    xe(), M();
    const e = await Ee();
    if (k !== "inspections" || !v) return;
    e?.setSites(N());
    const t = me[0];
    if (!t) {
      w("\uD3C9\uAC00\uD560 \uD604\uC7A5\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.");
      return;
    }
    const n = v.sites.find((o) => t.site_codes.includes(o.code) && o.map_visible !== false);
    if (n) {
      if (oe(n.code, { present: "map" }), await new Promise((o) => requestAnimationFrame(() => requestAnimationFrame(o))), k !== "inspections" || h !== n.code) return;
      e?.map.resize(), j(n) && e?.select(n.code), w("\uB2E4\uC74C \uD3C9\uAC00: " + n.name + " \xB7 " + t.scheduled_date);
    } else {
      w("\uB2E4\uC74C \uD3C9\uAC00: " + t.site_name + " \xB7 \uD604\uC7A5 \uC815\uBCF4\uB97C \uD655\uC778\uD574 \uC8FC\uC138\uC694.");
      const o = i("a", "\uD3C9\uAC00\uACC4\uD68D \uBCF4\uAE30");
      o.href = Ge(t), o.onclick = () => {
        x();
        try {
          sessionStorage.setItem(G, JSON.stringify({ owner: V, at: Date.now() }));
        } catch {
        }
      }, r("home-action-status").append(document.createTextNode(" "), o);
    }
    x();
  } catch (e) {
    k === "inspections" && (w(e.message || "\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uB20C\uB7EC \uC8FC\uC138\uC694."), M());
  }
}
async function Ke() {
  if (H === "VERIFIED" && Date.now() - ot < 6e4) return;
  if (he) return he;
  const e = v, t = J;
  return H = "LOADING", he = (async () => {
    try {
      const n = e.date, o = new Date(Date.parse(n) - 180 * 864e5).toISOString().slice(0, 10), s = new Date(Date.parse(n) + 180 * 864e5).toISOString().slice(0, 10), a = await Z("/safety-features/half-year-reviews/map-pending?" + new URLSearchParams({ from_date: o, to_date: s }));
      if (v !== e || J !== t) throw Error("\uD604\uC7A5 \uC815\uBCF4\uB97C \uC0C8\uB85C \uD655\uC778\uD574 \uC8FC\uC138\uC694.");
      if (!Array.isArray(a.items) || a.items.some((l) => typeof l.public_id != "string" || !Array.isArray(l.site_codes) || l.site_codes.some((d) => typeof d != "string") || !/^\d{4}-\d{2}-\d{2}$/.test(l.scheduled_date) || !["NOT_STARTED", "IN_PROGRESS"].includes(l.status))) throw Error("\uB0B4 \uC810\uAC80\uC744 \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC2DC \uB20C\uB7EC \uC8FC\uC138\uC694.");
      me = [...a.items].sort((l, d) => l.scheduled_date.localeCompare(d.scheduled_date) || l.public_id.localeCompare(d.public_id)), H = "VERIFIED", ot = Date.now();
    } catch (n) {
      throw v === e && (H = "UNKNOWN", me = []), n;
    } finally {
      he = null;
    }
  })(), he;
}
function Gt(e, t) {
  const n = r("region-list");
  n.replaceChildren(), r("map-bottom-filters").replaceChildren(), n.classList.add("map-filter-toolbar");
  const o = i("label", "\uC9C0\uC5ED"), s = i("select");
  s.id = "home-region-select", s.setAttribute("aria-label", "\uC9C0\uC5ED \uC120\uD0DD");
  for (const a of ["\uC804\uCCB4", ...st]) {
    const l = a === "\uC804\uCCB4" ? e.length : e.filter((p) => it(p) === a).length;
    if (!l && !["\uC804\uCCB4", "\uC11C\uC6B8", "\uACBD\uAE30", "\uC778\uCC9C"].includes(a)) continue;
    const d = i("option", (a === "\uC8FC\uC18C \uD655\uC778 \uC911" ? "\uAD8C\uC5ED \uD655\uC778 \uC911" : a) + " (" + l + ")");
    d.value = a, s.append(d);
  }
  s.value = T, s.onchange = () => {
    if (F()) {
      s.value = T, w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694.");
      return;
    }
    T = s.value, g = "all", y = "all", h = null, E = "", O = T === "\uC8FC\uC18C \uD655\uC778 \uC911", r("home-site-query").value = "", M(), ce(), x();
  }, o.append(s), n.append(o);
  for (const [a, l] of [["all", "\uC804\uCCB4"], ["inspections", "\uB0B4 \uC810\uAC80"], ["needs-info", "\uD655\uC778\uD544\uC694"]]) {
    const d = B(l, () => a === "all" ? Ve() : a === "inspections" ? Jt() : Zt(a), "map-view-filter");
    d.dataset.mapView = a, d.setAttribute("aria-pressed", String(k === a)), a === "inspections" && d.setAttribute("aria-controls", "site-map today-inspection-tasks"), r("map-bottom-filters").append(d);
  }
}
async function $t(e) {
  te = "loading";
  try {
    const t = await Z("/workspace/inspection-publications");
    if (e !== K || !v) return;
    if (!Array.isArray(t.items) || typeof t.date != "string") throw Error("\uD655\uC815 \uC810\uAC80\uC77C\uC815 \uD655\uC778 \uD544\uC694");
    At = t.items;
    for (const n of v.sites) n.inspections = t.items.filter((o) => o.site_code === n.code && !o.archived && ["PLANNED", "IN_PROGRESS"].includes(o.status) && typeof o.confirmed_at == "string" && o.confirmed_at.length > 0 && /^\d{4}-\d{2}-\d{2}$/.test(o.scheduled_date) && (o.due_date || o.scheduled_date) >= t.date).sort((o, s) => o.scheduled_date.localeCompare(s.scheduled_date));
    te = "ready", r("inspection-map-status").textContent = "\uD655\uC815\uB41C \uC810\uAC80\uC77C\uC815", M(), k === "inspections" && (h && N().some((n) => n.code === h) ? S?.select(h) : ce());
  } catch {
    e === K && (te = "error", r("inspection-map-status").textContent = "\uC810\uAC80\uC77C\uC815\uC744 \uD655\uC778\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uC0C8\uB85C\uACE0\uCE68\uD574 \uC8FC\uC138\uC694.", M());
  }
}
async function Yt(e) {
  const t = v;
  await wt({ sites: t.sites, request: Z, role: re, today: t.date, isCurrent: () => e === K && v === t && localStorage.getItem("besma_token") === C, apply: (n, o) => {
    ke = o || "";
    for (const s of t.sites) s.transport = n.get(s.code) || null;
    M();
  } });
}
document.addEventListener("click", (e) => {
  const t = e.target?.closest?.("a[href]");
  t && F() && !/^tel:/i.test(t.getAttribute("href")) && !t.hasAttribute("download") && (e.preventDefault(), e.stopImmediatePropagation(), w("\uC785\uB825\uD55C \uB0B4\uC6A9\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uAC70\uB098 \uCDE8\uC18C\uD574 \uC8FC\uC138\uC694."));
}, true);

function mountHomeProgress() {
  const panel = document.getElementById('home-progress-overview');
  const middle = document.querySelector('.home-progress-panel');
  const weather = document.getElementById('seoul-weather');
  document.querySelector('.company-header').append(weather);
  const functional = document.getElementById('today-evaluation-tasks');
  if (functional) document.getElementById('home-functional-detail').append(functional);
  const actions = document.querySelector('.map-actions');
  for (const [id, label, icon] of [['map-reset','전국 보기','전국'],['map-tilt','입체 보기','◇'],['map-terrain','지형 보기','△']]) {
    const button = document.getElementById(id); button.textContent=icon; button.title=label;button.setAttribute('aria-label',label);
  }
  // Place below the native zoom/compass group, relative to the map itself.
  function placeActions() { const slot=document.getElementById('home-map-slot');if(!slot)return;actions.style.top=(slot.offsetTop+114)+'px'; }
  new ResizeObserver(placeActions).observe(document.querySelector('.map-panel'));placeActions();
  document.getElementById('home-show-overview').onclick=()=>{if(F())return;h=null;homeSelection();};
  function homeSelection(){const selected=!!h;panel.hidden=selected;document.getElementById('selected-site-slot').hidden=!selected;document.getElementById('home-progress-title').textContent=selected?'현장 정보':'전 현장 진행현황';document.getElementById('home-show-overview').hidden=!selected;}
  window.addEventListener('besma-home-selection',homeSelection);
  homeSelection();
  const make=(tag,text)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;return el;};
  let seq=0;
  async function refreshProgress(home){
    const current=++seq;const month=home.date.slice(0,7);
    const results=await Promise.allSettled([Z('/monthly-collection/overview?'+new URLSearchParams({month})),Z('/workspace/home-progress')]);
    if(current!==seq||localStorage.getItem('besma_token')!==C)return;
    const monthly=document.getElementById('home-monthly-value'),half=document.getElementById('home-half-year-value');monthly.replaceChildren();half.replaceChildren();
    if(results[0].status==='fulfilled'){
      const value=results[0].value;
      monthly.append(make('strong',Number(value.count).toLocaleString('ko-KR')+'건'),make('p',month.replace('-','년 ')+'월 · '+value.site_count+'개 현장 취합'));
      const dl=make('dl');dl.className='home-progress-categories';
      for(const item of value.categories||[])dl.append(make('dt',item.label),make('dd',item.count+'건'));
      monthly.append(dl);if(value.pending_file_count)monthly.append(make('p','현장 연결 확인 '+value.pending_file_count+'건'));
      if(value.generated_at)monthly.append(make('p','자료 반영 '+new Date(value.generated_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})));
    }else monthly.append(make('p','취합현황을 확인하지 못했습니다. 다시 확인해 주세요.'));
    if(results[1].status==='fulfilled'){
      const value=results[1].value,counts=value.half_year;
      const total=counts.planned_sites,done=counts.completed_sites;
      if(total){const metric=make('div');metric.className='home-progress-metric';const ring=make('div');ring.className='home-progress-ring';const percent=Math.round(done/total*100);ring.style.setProperty('--progress',percent+'%');ring.append(make('span',percent+'%'));ring.setAttribute('role','img');ring.setAttribute('aria-label','등록 점검 대상 '+total+'개 현장 중 완료 '+done+'개');const text=make('div');text.append(make('strong',done+' / '+total+'개'),make('p','완료 / 등록 점검 대상'));metric.append(ring,text);half.append(metric);}else half.append(make('p','등록된 점검계획이 없습니다.'));
      half.append(make('p',value.period.replace('-H','년 ' )+'반기 · 진행 중 '+counts.in_progress_sites+'개 · 시작 전 '+counts.not_started_sites+'개'));
    }else half.append(make('p','반기 평가현황을 확인하지 못했습니다. 다시 확인해 주세요.'));
  }
  window.addEventListener('besma-home-refreshed',event=>void refreshProgress(event.detail));
  window.addEventListener('storage',event=>{if(event.key==='besma_token'||event.key===null){seq++;for(const id of ['home-monthly-value','home-half-year-value'])document.getElementById(id).replaceChildren(make('p','로그인 후 확인할 수 있습니다.'));}});
}
mountHomeProgress();
