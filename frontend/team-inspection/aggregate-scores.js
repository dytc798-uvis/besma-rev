var e = (O, g) => {
  let v = document.createElement(O);
  return g != null && (v.textContent = g), v;
};
function nt({ api: O, session: g, host: v }) {
  if (!v) return { dispose() {
  } };
  let I = true, z = 0, R = null, o = null, T = false, w = /* @__PURE__ */ new Set(), h = e("button", "비상훈련 현황");
  h.type = "button", h.className = "secondary training-open", h.id = "training-monitor-open", h.setAttribute("aria-haspopup", "dialog"), v.append(h);
  let b = e("dialog"), X = e("style"), P = e("div"), W = e("h2", "비상훈련 모니터링"), _ = e("input"), C = e("button", "새로고침"), S = e("button", "엑셀 저장"), M = e("button", "닫기"), N = e("p"), V = e("p", "주황색은 공사기간입니다. 미취합은 평가기간 종료 후 X로 표시합니다."), D = e("div");
  b.className = "training-monitor-dialog", b.setAttribute("aria-label", "비상훈련 모니터링"), P.className = "training-monitor-tools", D.className = "training-monitor-content", _.type = "search", _.placeholder = "현장 검색", _.setAttribute("aria-label", "비상훈련 현장 검색");
  for (let t of [C, S, M]) t.type = "button";
  P.append(W, _, C, S, M), b.append(X, P, N, V, D), document.body.append(b), X.textContent = "body:has(#workspace[hidden]) .training-open{display:none}.training-monitor-dialog{box-sizing:border-box;width:calc(100vw - 24px);max-width:1450px;height:90vh;max-height:95vh;border:1px solid #777;padding:16px;background:#fff;color:#222}.training-monitor-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.training-monitor-tools h2{margin:0 auto 0 0;font-size:21px}.training-monitor-tools button,.training-monitor-tools input{box-sizing:border-box;min-height:40px;font-size:14px;padding:8px}.training-monitor-dialog p{font-size:13px;line-height:1.5;margin:10px 0}.training-monitor-content{overflow:auto;max-height:calc(90vh - 180px)}.training-monitor-content table{display:table!important;width:100%;min-width:1450px;table-layout:fixed;border-collapse:collapse}.training-monitor-content thead{display:table-header-group!important;position:sticky;top:0;z-index:2;background:#eee}.training-monitor-content tbody{display:table-row-group!important}.training-monitor-content tr{display:table-row!important}.training-monitor-content th,.training-monitor-content td{display:table-cell!important;border:1px solid #ccc;padding:9px 7px;text-align:center;font-size:14px;white-space:nowrap}.training-monitor-content thead tr:first-child th:first-child,.training-monitor-content tbody td:first-child{text-align:left;white-space:normal}.training-site-col{width:300px}.training-date-col{width:90px}.training-state-col{width:95px}.training-in-period{background:#fce4d6}.training-out-period{background:#ededed}.training-site-link{border:0!important;background:transparent!important;color:#222!important;text-align:left;text-decoration:underline;cursor:pointer;padding:0!important;font:inherit!important}.training-needs{font-weight:700}.training-remarks{white-space:pre-wrap!important;text-align:left!important;font-size:13px!important}.training-file-open{max-width:100%;white-space:normal;text-align:left;overflow-wrap:anywhere}.training-file-view{max-width:1000px}.training-file-download{display:inline-block;margin:12px 0}.training-grade-link{border:0;background:transparent;color:inherit;font:inherit;font-weight:700;text-decoration:underline;text-underline-offset:3px;cursor:pointer;min-height:36px;min-width:64px;padding:4px}.training-grade-link:focus-visible{outline:2px solid #333;outline-offset:2px}.training-detail{box-sizing:border-box}.training-detail::backdrop{background:rgba(0,0,0,.35)}.training-detail p{white-space:pre-wrap;overflow-wrap:anywhere}.training-detail{max-width:720px;width:calc(100vw - 40px);max-height:85vh;overflow:auto;color:#222;background:white;border:1px solid #777;padding:20px}.training-detail h3{font-size:16px}.training-detail p{line-height:1.6;font-size:14px}.training-detail button{min-height:40px}@media(max-width:650px){.training-monitor-dialog{width:calc(100vw - 8px);height:95vh;padding:10px}.training-monitor-tools h2{width:100%}.training-monitor-content{max-height:calc(95vh - 250px)}.training-monitor-tools input{width:100%}.training-monitor-content table{min-width:1230px}.training-site-col{width:180px}.training-date-col{width:85px}.training-state-col{width:80px}}";
  function m(t) {
    w.add(t), t.addEventListener("close", () => {
      w.delete(t), t.remove();
    }, { once: true }), document.body.append(t), t.showModal();
  }
  function q(t, a, l) {
    for (let n of a.periods[l]?.files || []) {
      let i = e("p"), r = e("button", n.filename);
      r.type = "button", r.className = "training-file-open", r.disabled = !n.can_open, r.onclick = () => d(a, l, n), i.append(r), n.caption && i.append(e("small", " · " + n.caption)), n.can_open || i.append(e("small", " · 열람 권한 확인 필요")), t.append(i);
    }
  }
  function K(t, a) {
    g();
    let l = o.periods.filter((c) => (!a || c === a) && (t.periods[c]?.files || []).length), n = l.flatMap((c) => t.periods[c].files.map((f) => ({ period: c, file: f })));
    if (n.length === 1 && n[0].file.can_open) {
      d(t, n[0].period, n[0].file);
      return;
    }
    let i = e("dialog"), r = e("button", "닫기");
    i.className = "training-detail training-files", i.setAttribute("aria-label", t.site + " 일지 확인"), r.type = "button", r.onclick = () => i.close(), i.append(r, e("h2", t.site)), n.length || i.append(e("p", "등록된 일지가 없습니다."));
    for (let c of l) i.append(e("h3", o.period_labels[o.periods.indexOf(c)])), q(i, t, c);
    m(i);
  }
  function G(t, a, l) {
    if (!(a.periods[l]?.files || []).length) return;
    let n = e("button", "파일 확인하기");
    n.type = "button", n.onclick = () => K(a, l), t.append(n);
  }
  async function d(t, a, l) {
    if (g(), !l.can_open || !t.public_id) return;
    let n = e("dialog"), i = e("button", "닫기"), r = e("p", "파일을 불러오고 있습니다.");
    n.className = "training-detail training-file-view", n.setAttribute("aria-label", l.filename + " 파일 보기"), i.type = "button", i.onclick = () => n.close(), n.append(i, e("h2", l.filename), r);
    let c = null;
    n.addEventListener("close", () => {
      c && URL.revokeObjectURL(c);
    }), m(n);
    try {
      let f = await O("/safety-features/half-year-reviews/emergency-training/files/" + encodeURIComponent(t.public_id) + "/" + encodeURIComponent(l.id) + "?" + new URLSearchParams({ period: a }));
      if (g(), !I || !n.open) return;
      let B = Uint8Array.from(atob(f.content_base64), (y) => y.charCodeAt(0)), L = ["application/pdf", "image/jpeg", "image/png"].includes(f.content_type) ? f.content_type : "application/octet-stream";
      if (c = URL.createObjectURL(new Blob([B], { type: L })), r.textContent = "", L === "application/pdf") {
        let y = e("iframe");
        y.src = c, y.title = f.filename, y.referrerPolicy = "no-referrer", y.style.cssText = "width:100%;height:65vh;border:1px solid #ccc", n.append(y);
      } else if (L.startsWith("image/")) {
        let y = e("img");
        y.src = c, y.alt = f.filename, y.style.cssText = "display:block;max-width:100%;height:auto", n.append(y);
      } else r.textContent = "이 형식은 파일을 받아 확인해 주세요.";
      let j = e("a", "파일 받기");
      j.href = c, j.download = f.filename, j.className = "training-file-download", n.append(j);
    } catch (f) {
      n.open && (r.textContent = f.message || "파일을 불러오지 못했습니다.");
    }
  }
  function u(t, a) {
    g();
    let l = t.periods[a];
    if (l?.suitability !== "부적합") return;
    let n = e("dialog"), i = e("button", "닫기");
    n.className = "training-detail training-nonconformity", n.setAttribute("aria-label", t.site + " " + o.period_labels[o.periods.indexOf(a)] + " 부적합 사유"), i.type = "button", i.onclick = () => n.close(), n.append(i, e("h2", t.site), e("h3", o.period_labels[o.periods.indexOf(a)] + " · 부적합"), e("p", l.simple_reason || "부적합 사유 미기재")), G(n, t, a), m(n);
  }
  function U(t) {
    g();
    let a = e("dialog"), l = e("button", "닫기");
    a.className = "training-detail training-status", a.setAttribute("aria-label", t.site + " 비상훈련 현황"), l.type = "button", l.onclick = () => a.close(), a.append(l, e("h2", t.site));
    let n = 0;
    for (let i of o.periods) {
      if (!i.startsWith("2026")) continue;
      let r = t.periods[i], c = [r.conducted === "O" ? "실시" : r.conducted === "X" ? "미실시" : "", ["적합", "부적합"].includes(r.suitability) ? r.suitability : ""].filter(Boolean);
      !c.length && !(r.files || []).length || (n++, a.append(e("h3", o.period_labels[o.periods.indexOf(i)]), e("p", c.join(" · ") || "자료 접수")), r.suitability === "부적합" && r.simple_reason && !(r.simple_reason === "미실시" && r.conducted === "X") && a.append(e("p", r.simple_reason)), G(a, t, i));
    }
    n || a.append(e("p", "아직 취합된 일지가 없습니다.")), m(a);
  }
  function F() {
    if (!o) return;
    D.replaceChildren();
    let t = o.items.filter((p) => p.site.toLocaleLowerCase("ko").includes(_.value.trim().toLocaleLowerCase("ko"))), a = e("table"), l = e("thead"), n = e("tr"), i = e("tr"), r = e("tbody"), c = e("th", "현장명");
    c.rowSpan = 2;
    let f = e("colgroup"), B = e("col");
    B.className = "training-site-col", f.append(B);
    for (let p = 0; p < 2; p++) {
      let x = e("col");
      x.className = "training-date-col", f.append(x);
    }
    for (let p = 0; p < 6; p++) {
      let x = e("col");
      x.className = "training-state-col", f.append(x);
    }
    let L = e("col");
    L.style.width = "260px", f.append(L);
    let j = e("col");
    j.style.width = "140px", f.append(j), a.append(f), n.append(c);
    for (let p of ["착공일", "준공일"]) {
      let x = e("th", p);
      x.rowSpan = 2, n.append(x);
    }
    for (let [p, x] of o.period_labels.entries()) {
      let J = e("th", x);
      J.colSpan = p < 2 ? 1 : 2, n.append(J), i.append(e("th", "실시")), p >= 2 && i.append(e("th", "적합성"));
    }
    let y = e("th", "비고");
    y.rowSpan = 2, n.append(y);
    let tt = e("th", "파일 확인");
    tt.rowSpan = 2, n.append(tt), l.append(n, i);
    for (let p of t) {
      let x = e("tr"), J = e("td"), Y = e("button", p.site);
      Y.className = "training-site-link", Y.type = "button", Y.onclick = () => U(p), J.append(Y), x.append(J);
      for (let k of ["start_date", "completion_date"]) {
        let E = e("td", p[k]?.slice(2).replaceAll("-", "/") || "—");
        E.title = p.date_source || "확인된 공사기간 없음", x.append(E);
      }
      for (let k of o.periods) {
        let E = p.periods[k];
        for (let Z of k.startsWith("2025") ? ["conducted"] : ["conducted", "suitability"]) {
          let Q = e("td");
          if (Z === "suitability" && E[Z] === "부적합") {
            let H = e("button", "부적합");
            H.type = "button", H.className = "training-grade-link", H.setAttribute("aria-label", p.site + " " + o.period_labels[o.periods.indexOf(k)] + " 부적합 사유 보기"), H.setAttribute("aria-haspopup", "dialog"), H.onclick = () => u(p, k), Q.append(H);
          } else Q.textContent = E[Z];
          ["X", "부적합"].includes(E[Z]) && (Q.className = "training-needs"), Q.classList.add(E.in_schedule ? "training-in-period" : "training-out-period"), x.append(Q);
        }
      }
      let et = e("td", p.remarks || "");
      et.className = "training-remarks", x.append(et);
      let $ = e("td");
      if (Object.values(p.periods).some((k) => (k.files || []).length)) {
        let k = e("button", "파일 확인하기");
        k.type = "button", k.className = "training-files-link", k.setAttribute("aria-label", p.site + " 파일 확인하기"), k.onclick = () => K(p), $.append(k);
      } else $.textContent = "파일 없음";
      x.append($), r.append(x);
    }
    a.append(l, r), D.append(a), t.length || D.append(e("p", "검색 결과가 없습니다.")), S.disabled = !o.can_export, N.textContent = (o.current_target == null ? o.scope + " " + t.length + "곳" : "현재 반기평가 " + o.current_target + "곳 · 과거 포함 " + t.length + "곳") + " · " + new Date(o.as_of).toLocaleString("ko-KR") + " 확인 · 화면을 열어둔 동안 30초마다 갱신";
  }
  async function A() {
    g();
    let t = ++z;
    C.disabled = true;
    try {
      let a = await O("/safety-features/half-year-reviews/emergency-training");
      if (g(), !I || !b.open || t !== z) return;
      o = a, F();
      let l = new URLSearchParams(location.search);
      if (!T && l.get("training_files") === "1") {
        T = true;
        let n = o.items.find((i) => i.id === l.get("training_site"));
        n && K(n);
      }
    } catch (a) {
      I && b.open && t === z && (N.textContent = "갱신 실패: " + (a.message || "다시 확인해 주세요.") + (o ? " · 표시된 표는 직전 확인 자료입니다." : ""));
    } finally {
      I && t === z && (C.disabled = false);
    }
  }
  return h.onclick = () => {
    g(), b.open || b.showModal(), A(), clearInterval(R), R = setInterval(() => {
      b.open && !document.hidden && A();
    }, 3e4);
  }, C.onclick = A, _.oninput = F, M.onclick = () => b.close(), b.addEventListener("close", () => {
    for (let t of [...w]) t.close(), t.remove();
    w.clear(), clearInterval(R), R = null, z++, C.disabled = false;
  }), S.onclick = async () => {
    g(), S.disabled = true;
    try {
      let t = await O("/safety-features/half-year-reviews/emergency-training/export");
      if (g(), !I) return;
      let a = Uint8Array.from(atob(t.content_base64), (i) => i.charCodeAt(0)), l = URL.createObjectURL(new Blob([a], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })), n = e("a");
      n.href = l, n.download = t.filename, n.click(), setTimeout(() => URL.revokeObjectURL(l), 1e3);
    } catch (t) {
      N.textContent = t.message || "엑셀을 저장하지 못했습니다.";
    } finally {
      I && (S.disabled = !o?.can_export);
    }
  }, new URLSearchParams(location.search).get("view") === "emergency-training" && setTimeout(() => {
    I && h.click();
  }, 0), { dispose() {
    I = false, z++;
    for (let t of [...w]) t.close(), t.remove();
    w.clear(), clearInterval(R), b.close(), b.remove(), h.remove();
  } };
}
var s = (O, g) => {
  let v = document.createElement(O);
  return g != null && (v.textContent = g), v;
};
function rt({ api: O, session: g, host: v }) {
  let I = nt({ api: O, session: g, host: v });
  if (!v) return { dispose() {
  } };
  let z = true, R = 0, o = null, T = "annual", w = s("button", "종합점수 현황");
  w.type = "button", w.id = "aggregate-scores-open", w.className = "secondary", w.setAttribute("aria-haspopup", "dialog"), v.append(w);
  let h = s("dialog"), b = s("style"), X = s("div"), P = s("h2", "2026 종합점수 현황"), W = s("button", "닫기"), _ = s("button", "새로고침"), C = s("button", "연간 순위"), S = s("button", "하반기 점수"), M = s("p"), N = s("div");
  h.className = "aggregate-scores-dialog", h.setAttribute("aria-label", "종합점수 현황"), X.className = "aggregate-tools", N.className = "aggregate-content";
  for (let d of [W, _, C, S]) d.type = "button";
  X.append(P, C, S, _, W), h.append(b, X, M, N), document.body.append(h), b.textContent = "body:has(#workspace[hidden]) #aggregate-scores-open{display:none}.aggregate-scores-dialog{box-sizing:border-box;width:calc(100vw - 28px);max-width:none;height:90vh;max-height:94vh;padding:16px;border:1px solid #66788b;border-radius:10px;color:#172b3d;background:white}.aggregate-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.aggregate-tools h2{margin:0 auto 0 0;font-size:21px}.aggregate-tools button{min-height:42px;padding:8px 12px}.aggregate-tools [aria-pressed=true]{background:#164b65;color:white}.aggregate-content{overflow:auto;max-height:calc(90vh - 170px)}.aggregate-content table{display:table!important;width:100%;border-collapse:collapse;min-width:920px}.aggregate-content thead{display:table-header-group!important;position:sticky;top:0;background:#eef3f7;z-index:1}.aggregate-content tbody{display:table-row-group!important}.aggregate-content tr{display:table-row!important}.aggregate-content th,.aggregate-content td{display:table-cell!important;border-bottom:1px solid #d6dfe6;padding:10px 8px;font-size:14px;text-align:right;white-space:nowrap}.aggregate-content th:nth-child(2),.aggregate-content td:nth-child(2),.aggregate-content th:last-child,.aggregate-content td:last-child{text-align:left}.aggregate-content tbody tr:nth-child(even){background:#f7f9fb}.aggregate-pending{color:#9a2253;font-weight:600}.aggregate-scores-dialog p{margin:12px 0;line-height:1.5}@media(max-width:650px){.aggregate-scores-dialog{width:calc(100vw - 8px);padding:10px;height:95vh}.aggregate-tools h2{width:100%;font-size:19px}.aggregate-tools button{font-size:12px;padding:6px}.aggregate-content{max-height:calc(95vh - 230px)}}";
  let V = (d) => {
    let u = s("span", d);
    return u.className = "aggregate-state " + (d === "점수 확정" ? "confirmed" : d === "평가 완료" ? "completed" : d === "평가 중" ? "progress" : "other"), u;
  }, D = (d) => {
    let u = s("td");
    if (!d || !d.items.some((t) => t.value != null)) return u.textContent = "—", u;
    let U = s("details"), F = s("summary", "+" + m(d.bonus) + " / −" + m(d.deduction)), A = s("ul");
    U.className = "annual-adjustment";
    for (let t of d.items) {
      let a = s("li", t.label + ": " + (t.value == null ? "—" : (t.kind === "가점" ? "+" : "−") + m(t.value)));
      A.append(a);
    }
    return U.append(F, A), u.append(U), u;
  };
  b.textContent += ".aggregate-state{display:inline-block;padding:4px 8px;border-radius:5px;font-weight:700}.aggregate-state.progress{background:#fff0c2;color:#754600}.aggregate-state.completed{background:#dfedff;color:#164b7d}.aggregate-state.confirmed{background:#dff3e5;color:#185d32}.aggregate-state.other{background:#edf0f3;color:#485562}.aggregate-state.unsigned{background:#ffe3ef;color:#8c174b;margin-left:5px}.annual-adjustment summary{cursor:pointer;color:#154e75}.annual-adjustment ul{text-align:left;margin:8px 0;padding-left:18px;font-size:12px;line-height:1.6}";
  const draftRankingBadges = row => { const wrap=s("span"); wrap.append(V(row.state)); if(row.signature_state==="서명전"){ const label=s("span","서명전"); label.className="aggregate-state unsigned"; wrap.append(label); } return wrap; };
  let m = (d) => d == null ? "—" : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(d);
  function q() {
    if (!o) return;
    if (C.disabled = !o.annual, C.setAttribute("aria-pressed", String(T === "annual")), S.setAttribute("aria-pressed", String(T !== "annual")), T === "annual" && o.annual) {
      K();
      return;
    }
    let d = o.counts;
    M.textContent = (o.scope || "전체 현장") + " " + d.sites + "곳 · 점수 집계 " + (d.total_scored ?? d.graded) + "곳 · 작성 중 점수 포함" + (o.monthly_as_of ? " / 월간자료 " + o.monthly_as_of + " 기준 (" + o.monthly_period + ")" : ""), N.replaceChildren();
    let u = s("table"), U = s("thead"), F = s("tr"), A = s("tbody"), t = ["순위", "현장", "반기평가 40", "월간보고 10", "소장평가 20", "관리감독자 10", "법령점검 20", "종합점수", "평가 상태"];
    for (let n of t) F.append(s("th", n));
    U.append(F);
    let a = "rank", l = [...o.items].sort((n, i) => (n[a] == null) - (i[a] == null) || (n[a] ?? 0) - (i[a] ?? 0) || n.site.localeCompare(i.site, "ko"));
    for (let n of l) {
      let i = s("tr"), r = n.scores, c = r.total, f = n.state, B = [n[a] ?? "—", n.site, m(r.report), m(r.monthly), m(r.manager), m(r.supervisor), m(r.law), m(c), f];
      for (let L = 0; L < B.length; L++) {
        let j = s("td", String(B[L]));
        L === B.length - 1 && j.replaceChildren(draftRankingBadges(n)), L === 3 && n.monthly && (j.title = "제출 확인 " + n.monthly.received + "/" + n.monthly.required), i.append(j);
      }
      A.append(i);
    }
    u.append(U, A), N.append(u);
  }
  function K() {
    let d = o.annual;
    M.textContent = (o.scope || "전체 현장") + " " + d.counts.sites + "곳 · 순위 집계 " + d.counts.ranked + "곳 / " + d.method_label + " · 작성 중 점수 포함 · 서명전 점수는 현장 의견에 따라 변경될 수 있습니다.", N.replaceChildren();
    let u = s("table"), U = s("thead"), F = s("tr"), A = s("tbody");
    for (let t of ["순위", "현장", "상반기", "하반기", "반기 평균", "연간 가감점", "연간 종합점수", "평가 상태", "평가 반기"]) {
      let a = s("th", t);
      (t === "상반기" || t === "하반기") && (a.title = "가감점을 제외한 평가점수"), F.append(a);
    }
    U.append(F);
    for (let t of d.items) {
      let a = s("tr");
      for (let n of [t.rank ?? "—", t.site, m(t.first_half), m(t.second_half), m(t.base_average)]) a.append(s("td", String(n)));
      a.append(D(t.adjustments), s("td", m(t.annual_score)));
      let l = s("td");
      l.append(draftRankingBadges(t)), a.append(l, s("td", t.periods === 2 ? "상·하반기" : t.periods === 1 ? t.first_half != null ? "상반기" : "하반기" : "미평가")), A.append(a);
    }
    u.append(U, A), N.append(u);
  }
  async function G() {
    g();
    let d = ++R;
    _.disabled = true, M.textContent = "점수를 확인하고 있습니다.";
    try {
      let u = await O("/safety-features/half-year-reviews/aggregate-scores?period=2026-H2");
      if (g(), !z || d !== R) return;
      o = u, q();
    } catch (u) {
      z && d === R && (M.textContent = u.message || "점수를 불러오지 못했습니다. 새로고침을 눌러 주세요.", N.replaceChildren());
    } finally {
      z && d === R && (_.disabled = false);
    }
  }
  return w.onclick = () => {
    g(), h.open || h.showModal(), G();
  }, C.onclick = () => {
    T = "annual", q();
  }, S.onclick = () => {
    T = "half", q();
  }, W.onclick = () => h.close(), _.onclick = G, { dispose() {
    I.dispose(), z = false, R++, h.close(), h.remove(), w.remove();
  } };
}
export { rt as mountAggregateScores };
