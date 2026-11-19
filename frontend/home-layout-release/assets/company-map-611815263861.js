import { TEAM_COLORS as O } from "/assets/map-teams-93050eef332d.js";
import { createRegionLock as te, fitRegionCamera as oe, mainlandFeatures as ie } from "/assets/company-map-region-a65019e855f5.js";
import { createPhotoMarkers as re } from "/assets/company-map-photos-7c1e929912f2.js";
import { Map as ae, Marker as ne, NavigationControl as se, ScaleControl as ce, setWorkerUrl as le } from "/workspace-assets/vendor/maplibre-6.16.0/maplibre-gl.mjs";
le(new URL("/workspace-assets/vendor/maplibre-6.16.0/maplibre-gl-worker.mjs", import.meta.url).href);
const de = [[125.1, 33.05], [129.9, 38.65]], G = ["coalesce", ["get", "name:ko"], ["get", "name:nonlatin"], ["get", "name"]];
function pe(s) {
  const a = s && typeof s == "object" ? s.key : s;
  if (typeof a != "string" && typeof a != "number") return "?";
  const z = String(a).trim().match(/^(?:team[-_ ]?)?([1-6])(?:팀)?$/i);
  return z ? z[1] : "?";
}
const I = (s) => ({ type: "FeatureCollection", features: s.filter((a) => Number.isFinite(a.longitude) && Number.isFinite(a.latitude) && a.longitude >= 124 && a.longitude <= 132.5 && a.latitude >= 32.8 && a.latitude <= 43.1).map((a) => ({ type: "Feature", id: a.code, properties: { transport: a.transport?.label || "", inspection: a.inspections?.length ? "\uC810\uAC80\uC608\uC815" : "", code: a.code, team: pe(a.team), government: a.is_government === true ? true : a.is_government === false ? false : null, category: a.is_government === true ? "government" : a.is_government === false ? "general" : "unknown" }, geometry: { type: "Point", coordinates: [a.longitude, a.latitude] } })) });
async function mountMap({ container: s, sites: a, onSelect: z, onRegion: w, onStatus: B, onHover: v, legendElement: u, signal: K }) {
  const Z = await fetch("/workspace-assets/map-liberty.json", { credentials: "omit", signal: K });
  if (!Z.ok) throw Error("\uC9C0\uB3C4\uB97C \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.");
  const F = await Z.json();
  if (K?.aborted) throw new DOMException("Map cancelled", "AbortError");
  for (const n of F.layers) n.type === "symbol" && n.layout?.["text-field"] && (n.layout["text-field"] = ["poi", "mountain_peak"].includes(n["source-layer"]) ? "" : ["match", G, "\uC870\uC120\uBBFC\uC8FC\uC8FC\uC758\uC778\uBBFC\uACF5\uD654\uAD6D", "\uBD81\uD55C", G]), n["source-layer"] === "place" && n.id.includes("country") && (n.layout["text-size"] = 12);
  const t = new ae({ container: s, style: F, center: [127.3, 37.4], zoom: 5.5, pitch: 35, minZoom: 3.5, maxZoom: 19, maxPitch: 65, maxBounds: [[112, 20], [148, 51]], attributionControl: { compact: false }, cooperativeGestures: false, transformRequest: (n) => ({ url: n, credentials: "omit" }) });
  t.addControl(new se({ visualizePitch: true }), "top-right"), t.addControl(new ce({ unit: "metric" }), "bottom-left");
  let S = null;
  function y() { return {top:24,bottom:30,left:20,right:44}; }
  function D() {
    !M && s.clientWidth && s.clientHeight && t.setPadding(y());
  }
  let h = "all", b = null, R = null, M = false, T = "", E = false, m = 35, x = a;
  const V = F.layers.filter((n) => n["source-layer"] === "place" && n.type === "symbol").map((n) => n.id), _ = () => {
    M || (M = true, S?.disconnect(), K?.removeEventListener("abort", _), v?.(null, null), R?.dispose(), b?.dispose(), u?.remove(), x = [], t.remove());
  };
  K?.addEventListener("abort", _, { once: true });
  try {
    let q = function(e, o, i = {}) {
      return e.length ? e.length === 1 && e[0].properties.iso_3166_2 === "KR-11" ? (w?.("\uC11C\uC6B8", { kind: "admin", restore: i.fit === false }), b.set(e, { name: "\uC11C\uC6B8", pitch: m, padding: y(), fit: i.fit !== false })) : (b.clear(), w?.(o), oe(t, o === "\uC601\uB0A8\uAD8C" ? ie(e) : e, { pitch: m, padding: y() }), true) : false;
    }, L = function({ flat: e = false } = {}) {
      b.clear(), m = 0, w?.("\uC804\uAD6D");
      const o = t.cameraForBounds(de, { padding: y(), bearing: 0 });
      o && t.easeTo({ ...o, center: [127.7, 35.95], zoom: Math.max(t.getMinZoom(), o.zoom), pitch: m, duration: 700 });
    }, C = function(e, o = {}) {
      if (typeof e != "string") return false;
      const i = e.trim();
      if (["\uC804\uCCB4", "\uC804\uAD6D", "\uB0A8\uBD81\uD55C"].includes(i)) return L(), true;
      const r = J[i], p = i.replace(/특별자치도|특별자치시|특별시|광역시|도$/g, "");
      return q(f.features.filter((d) => {
        const l = d.properties, k = l.iso_3166_2;
        return r ? r.includes(k) : [l.name_ko, l.name, k, P[k]].includes(i) || P[k] === p;
      }), i, o);
    }, X = function(e) {
      h = e === "all" || e === "government" || Object.hasOwn(O, e) ? e : "all";
      const o = h === "unconfirmed" ? "?" : h, i = h === "government" ? ["==", ["get", "government"], true] : ["==", ["get", "team"], o], r = h === "all" ? 1 : ["case", i, 1, 0.17];
      t.setPaintProperty("site-points", "circle-opacity", r), t.setPaintProperty("site-points", "circle-stroke-opacity", r), t.setPaintProperty("site-team", "text-opacity", r), t.setPaintProperty("site-transport-ring", "circle-stroke-opacity", r), t.setPaintProperty("site-transport-label", "text-opacity", r), t.setPaintProperty("site-halo", "circle-opacity", h === "all" ? 0.85 : ["case", i, 0.95, 0.08]), R?.setTeamHighlight?.(h);
    }, A = function(e) {
      T = e, R?.highlight(e), t.setFilter("site-selected-ring", ["==", ["get", "code"], e]);
    }, j = function(e) {
      const o = x.find((g) => g.code === e);
      if (!o) return;
      A(e), z?.(e);
      const i = [o.longitude, o.latitude], r = t.project(i), p = x.filter((g) => g.code !== e && Number.isFinite(g.longitude) && Number.isFinite(g.latitude)).map((g) => {
        const W = t.project([g.longitude, g.latitude]);
        return Math.hypot(W.x - r.x, W.y - r.y);
      }).filter((g) => g > 0.1), d = Math.min(...p), l = Number.isFinite(d) ? t.getZoom() + Math.log2(78 / Math.max(d, 0.1)) : 12, k = Math.min(19, Math.max(12, t.getZoom(), l));
      t.flyTo({ center: i, zoom: k, padding: y(), pitch: m, duration: 650 });
    }, $ = function(e, o, i) {
      w?.(e), t.flyTo({ center: o, zoom: i, padding: y(), pitch: m, duration: 650, essential: false });
    }, Y = function(e) {
      E = e, t.getSource("terrain-dem") || t.addSource("terrain-dem", { type: "raster-dem", tiles: ["https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"], tileSize: 256, encoding: "terrarium", maxzoom: 14, attribution: 'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">AWS Terrain Tiles</a> \xB7 USGS / NOAA' }), t.setTerrain(e ? { source: "terrain-dem", exaggeration: 1 } : null);
    }, H = function(e, { name: o = "\uC990\uACA8\uCC3E\uAE30", maxZoom: i = 14 } = {}) {
      b.clear();
      const r = e.filter((l) => Number.isFinite(l.longitude) && Number.isFinite(l.latitude) && l.longitude >= 124 && l.longitude <= 132 && l.latitude >= 33 && l.latitude <= 39);
      if (!r.length) return L(), w?.(o), false;
      if (w?.(o), r.length === 1) return t.flyTo({ center: [r[0].longitude, r[0].latitude], zoom: i, padding: y(), pitch: m, duration: 650 }), true;
      const p = r.map((l) => l.longitude), d = r.map((l) => l.latitude);
      return t.fitBounds([[Math.min(...p), Math.min(...d)], [Math.max(...p), Math.max(...d)]], { padding: y(), maxZoom: i, pitch: m, duration: 650 }), true;
    }, ee = function(e) {
      e?.lockedRegion === "\uC11C\uC6B8" && C("\uC11C\uC6B8", { fit: false });
      const o = e?.camera || e;
      return !o || !Array.isArray(o.center) || o.center.length !== 2 || ![...o.center, o.zoom, o.pitch, o.bearing].every((i) => typeof i == "number" && Number.isFinite(i)) || o.center[0] < 112 || o.center[0] > 148 || o.center[1] < 20 || o.center[1] > 51 || o.zoom < t.getMinZoom() || o.zoom > t.getMaxZoom() || o.pitch < 0 || o.pitch > 65 || o.bearing < -180 || o.bearing > 180 ? false : (m = o.pitch, t.jumpTo({ padding: y(), center: [...o.center], zoom: o.zoom, pitch: o.pitch, bearing: o.bearing }), true);
    };
    if (await new Promise((e, o) => {
      const i = setTimeout(() => o(Error("\uC9C0\uB3C4\uB97C \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.")), 3e4);
      t.once("load", () => {
        clearTimeout(i), e();
      }), t.once("remove", () => {
        clearTimeout(i), o(new DOMException("Map cancelled", "AbortError"));
      });
    }), M) throw new DOMException("Map cancelled", "AbortError");
    const f = await (await fetch("/workspace-assets/korea-admin1.geojson", { credentials: "omit", signal: K })).json();
    if (M) throw new DOMException("Map cancelled", "AbortError");
    const P = { "KR-11": "\uC11C\uC6B8", "KR-26": "\uBD80\uC0B0", "KR-27": "\uB300\uAD6C", "KR-28": "\uC778\uCC9C", "KR-29": "\uAD11\uC8FC", "KR-30": "\uB300\uC804", "KR-31": "\uC6B8\uC0B0", "KR-50": "\uC138\uC885", "KR-41": "\uACBD\uAE30", "KR-42": "\uAC15\uC6D0", "KR-43": "\uCDA9\uBD81", "KR-44": "\uCDA9\uB0A8", "KR-45": "\uC804\uBD81", "KR-46": "\uC804\uB0A8", "KR-47": "\uACBD\uBD81", "KR-48": "\uACBD\uB0A8", "KR-49": "\uC81C\uC8FC" }, J = { \uC218\uB3C4\uAD8C: ["KR-11", "KR-41", "KR-28"], \uCDA9\uCCAD\uAD8C: ["KR-43", "KR-44", "KR-30", "KR-50"], \uD638\uB0A8\uAD8C: ["KR-45", "KR-46", "KR-29"], \uC601\uB0A8\uAD8C: ["KR-47", "KR-48", "KR-26", "KR-27", "KR-31"], \uAC15\uC6D0\uAD8C: ["KR-42"], \uC81C\uC8FC\uAD8C: ["KR-49"] };
    t.addSource("province-regions", { type: "geojson", data: f }), t.addLayer({ id: "province-hit", type: "fill", source: "province-regions", maxzoom: 9, paint: { "fill-color": "#d9a04f", "fill-opacity": 0.035 } }), t.addLayer({ id: "local-boundaries", type: "line", source: "openmaptiles", "source-layer": "boundary", minzoom: 9, filter: ["all", [">=", ["get", "admin_level"], 6], ["<=", ["get", "admin_level"], 10], ["!=", ["get", "maritime"], 1]], paint: { "line-color": "#72538b", "line-opacity": 0.7, "line-dasharray": [2, 2], "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.6, 14, 1.5] } });
    const Q = t.getStyle().layers.find((e) => e.type === "symbol")?.id;
    t.addLayer({ id: "buildings-3d", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building", minzoom: 14, filter: ["all", ["!=", ["get", "hide_3d"], true], [">", ["coalesce", ["get", "render_height"], 0], 0]], paint: { "fill-extrusion-color": "#9daab3", "fill-extrusion-height": ["coalesce", ["get", "render_height"], 0], "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0], "fill-extrusion-opacity": 0.8 } }, Q);
    const N = document.createElement("canvas");
    N.width = 28, N.height = 28;
    const c = N.getContext("2d");
    if (c.fillStyle = "#5c7253", c.beginPath(), c.moveTo(2, 25), c.lineTo(13, 3), c.lineTo(26, 25), c.closePath(), c.fill(), c.fillStyle = "#e1e6d8", c.beginPath(), c.moveTo(8, 14), c.lineTo(13, 3), c.lineTo(19, 14), c.lineTo(14, 11), c.closePath(), c.fill(), t.addImage("mountain-picture", c.getImageData(0, 0, 28, 28)), t.addLayer({ id: "mountain-pictures", type: "symbol", source: "openmaptiles", "source-layer": "mountain_peak", minzoom: 9, filter: ["==", ["get", "class"], "peak"], layout: { "icon-image": "mountain-picture", "icon-size": 0.65, "icon-padding": 7 } }), t.addSource("korea-islands", { type: "geojson", data: { type: "FeatureCollection", features: [{ type: "Feature", properties: { name: "\uC6B8\uB989\uB3C4" }, geometry: { type: "Point", coordinates: [130.863251, 37.500678] } }, { type: "Feature", properties: { name: "\uB3C5\uB3C4" }, geometry: { type: "Point", coordinates: [131.8695556, 37.2407778] } }] } }), t.addLayer({ id: "korea-island-labels", type: "symbol", source: "korea-islands", maxzoom: 10, layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"], "text-size": 11, "text-offset": [0, 1.1], "text-allow-overlap": true }, paint: { "text-color": "#214b65", "text-halo-color": "#fff", "text-halo-width": 1.5 } }), t.addSource("site-points", { type: "geojson", data: I(a) }), t.addLayer({ id: "site-halo", type: "circle", source: "site-points", paint: { "circle-radius": 19, "circle-color": "#fff", "circle-opacity": 0.85 } }), t.addLayer({ id: "site-transport-ring", type: "circle", source: "site-points", filter: ["match", ["get", "transport"], ["\uCC28\uB7C9 \uC6B0\uC120 \uAC80\uD1A0", "\uCD9C\uC785\uAD6C \uD655\uC778"], true, false], paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 8, 8, 12, 11, 17, 14, 22], "circle-opacity": 0, "circle-stroke-width": 3, "circle-stroke-color": ["match", ["get", "transport"], "\uCC28\uB7C9 \uC6B0\uC120 \uAC80\uD1A0", "#a25c00", "#7051ac"] } }), t.addLayer({ id: "site-selected-ring", type: "circle", source: "site-points", filter: ["==", ["get", "code"], ""], paint: { "circle-radius": 23, "circle-opacity": 0, "circle-stroke-width": 4, "circle-stroke-color": "#ffd15a" } }), t.addLayer({ id: "site-points", type: "circle", source: "site-points", paint: { "circle-radius": 14, "circle-color": ["match", ["get", "team"], ...Object.entries(O).filter(([e]) => e !== "unconfirmed").flat(), O.unconfirmed], "circle-stroke-width": ["case", ["==", ["get", "category"], "government"], 2.5, 1.2], "circle-stroke-color": ["case", ["==", ["get", "category"], "government"], "#126fc1", "#fff"] } }), t.addLayer({ id: "site-team", type: "symbol", source: "site-points", layout: { "text-field": ["get", "team"], "text-font": ["Noto Sans Bold"], "text-size": 12, "text-allow-overlap": true }, paint: { "text-color": "#fff" } }), t.addLayer({ id: "site-inspection-label", type: "symbol", source: "site-points", filter: ["!=", ["get", "inspection"], ""], layout: { "text-field": ["get", "inspection"], "text-font": ["Noto Sans Bold"], "text-size": 12, "text-offset": [0, 2.8], "text-allow-overlap": true }, paint: { "text-color": "#704900", "text-halo-color": "#fff0c7", "text-halo-width": 3 } }), t.addLayer({ id: "site-transport-label", type: "symbol", source: "site-points", minzoom: 9, filter: ["match", ["get", "transport"], ["\uCC28\uB7C9 \uC6B0\uC120 \uAC80\uD1A0", "\uCD9C\uC785\uAD6C \uD655\uC778"], true, false], layout: { "text-field": ["get", "transport"], "text-font": ["Noto Sans Bold"], "text-size": 12, "text-offset": [0, -2.5], "text-allow-overlap": false }, paint: { "text-color": ["match", ["get", "transport"], "\uCC28\uB7C9 \uC6B0\uC120 \uAC80\uD1A0", "#874b00", "#64419c"], "text-halo-color": "#fff", "text-halo-width": 3 } }), b = te(t), R = re({ map: t, Marker: ne, sites: a, onHover: v, onSelect: (e) => j(e) }), u) {
      s.append(u), u.hidden = false, u.style.left = "12px", u.style.top = "12px";
      for (const e of ["click", "dblclick", "mousedown", "touchstart", "wheel", "keydown"]) u.addEventListener(e, (o) => o.stopPropagation());
    }
    S = new ResizeObserver(D), S.observe(s), u && S.observe(u), D(), t.on("mouseenter", "site-points", () => {
      t.getCanvas().style.cursor = "pointer";
    }), t.on("mousemove", "site-points", (e) => {
      const o = e.features?.[0]?.properties.code;
      x.some((i) => i.code === o) && v?.(o, e);
    }), t.on("mouseleave", "site-points", (e) => {
      t.getCanvas().style.cursor = "", v?.(null, e);
    }), t.on("click", (e) => {
      const o = t.queryRenderedFeatures(e.point, { layers: ["site-points"] })[0];
      if (o && x.some((r) => r.code === o.properties.code)) {
        j(o.properties.code);
        return;
      }
      const i = t.queryRenderedFeatures([[e.point.x - 5, e.point.y - 5], [e.point.x + 5, e.point.y + 5]], { layers: V })[0];
      if (i && i.geometry.type === "Point") {
        if (!b.contains(i.geometry.coordinates)) return;
        const r = i.properties, p = r["name:ko"] || r["name:nonlatin"] || r.name, d = r.class;
        if (["\uC11C\uC6B8", "\uC11C\uC6B8\uD2B9\uBCC4\uC2DC", "Seoul"].includes(p)) {
          C("\uC11C\uC6B8");
          return;
        }
        $(p, i.geometry.coordinates, ["quarter", "neighbourhood"].includes(d) ? 16 : d === "borough" ? 13 : d === "city" ? 11 : 9);
        return;
      }
      if (t.getZoom() < 9) {
        const r = t.queryRenderedFeatures(e.point, { layers: ["province-hit"] })[0];
        if (r) {
          const p = f.features.find((d) => d.properties.iso_3166_2 === r.properties.iso_3166_2);
          p && q([p], r.properties.name_ko);
        }
      }
    }), s.setAttribute("aria-busy", "true"), t.on("movestart", () => s.setAttribute("aria-busy", "true")), t.on("idle", () => s.setAttribute("aria-busy", "false"));
    const U = () => B?.(`\uD655\uB300 ${t.getZoom().toFixed(1)} \xB7 \uAE30\uC6B8\uAE30 ${Math.round(t.getPitch())}\xB0`);
    return t.on("moveend", U), U(), t.on("error", (e) => {
      B?.("\uC77C\uBD80 \uC9C0\uB3C4 \uC815\uBCF4\uB97C \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4."), console.warn("Map resource error", e.error?.message || e.error);
    }), { map: t, fitSites: H, setFavoriteView: (e) => R?.setFavoriteView(e), setHighlightedTeam: X, highlight: (e) => A(x.some((o) => o.code === e) ? e : ""), setTerrain: Y, setTilt: (e) => {
      m = e ? 35 : 0, t.easeTo({ pitch: m, duration: 500 });
    }, setSites: (e) => {
      x = e, T && !e.some((o) => o.code === T) && (A(""), v?.(null, null)), t.getSource("site-points").setData(I(e)), R?.setSites(e);
    }, select: j, region: (e, o, i) => $(e, o, i), regionByName: C, reset: L, restoreCamera: ee, dispose: _, state: () => {
      const e = t.getCenter().toArray(), o = t.getZoom(), i = t.getPitch(), r = t.getBearing();
      return { activeCode: T, terrain: E, highlightedTeam: h, viewPreset: "south-v1", lockedRegion: b.state(), center: e, zoom: o, pitch: i, bearing: r, camera: { center: [...e], zoom: o, pitch: i, bearing: r } };
    } };
  } catch (n) {
    throw _(), n;
  }
}
export {
  mountMap
};
