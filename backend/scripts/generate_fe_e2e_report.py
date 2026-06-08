"""기능인제 E2E 시뮬레이션 결과 → HTML 보고서 생성.

Usage:
  cd backend && PYTHONPATH=. python scripts/generate_fe_e2e_report.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = BACKEND_ROOT.parent / "docs" / "reports" / "functional-eval-e2e"
JSON_PATH = REPORT_DIR / "simulation-result.json"
HTML_PATH = REPORT_DIR / "index.html"
SCREENSHOTS_DIR = REPORT_DIR / "screenshots"


def _esc(obj) -> str:
    return html.escape(json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, str) else obj)


def main() -> None:
    if not JSON_PATH.exists():
        print(f"missing {JSON_PATH}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    shots = sorted(SCREENSHOTS_DIR.glob("*.png")) if SCREENSHOTS_DIR.exists() else []
    shot_blocks = ""
    for p in shots:
        rel = f"screenshots/{p.name}"
        title = p.stem.replace("_", " ")
        shot_blocks += f"""
        <figure class="shot">
          <figcaption>{html.escape(title)}</figcaption>
          <img src="{html.escape(rel)}" alt="{html.escape(title)}" loading="lazy" />
        </figure>"""

    issues = data.get("issues") or []
    known = data.get("known_issues") or []
    issue_rows = ""
    for i in issues + [k for k in known if k.get("status") != "fixed"]:
        sev = i.get("severity", "info")
        issue_rows += f"<tr class='sev-{html.escape(sev)}'><td>{html.escape(str(i.get('step','')))}</td><td>{html.escape(sev)}</td><td>{html.escape(i.get('message',''))}</td><td>{html.escape(i.get('note',''))}</td></tr>"

    steps = data.get("steps") or []
    step_rows = ""
    for s in steps:
        step_rows += f"<tr><td>{html.escape(str(s.get('step','')))}</td><td><pre>{_esc(s)}</pre></td></tr>"

    accounts = data.get("accounts") or {}
    acct_rows = ""
    for role, info in accounts.items():
        acct_rows += f"<tr><td>{html.escape(role)}</td><td><code>{html.escape(info.get('login_id',''))}</code></td><td><code>{html.escape(info.get('password',''))}</code></td></tr>"

    sim_pass = data.get("simulation_passed", data.get("passed", False))
    open_known = [k for k in known if k.get("status") != "fixed"]
    status_cls = "pass" if sim_pass else "fail"
    status_txt = "API 시뮬레이션 통과" if sim_pass else "API 시뮬레이션 실패"
    if open_known:
        status_txt += f" · 배포 전 권고 {len(open_known)}건"

    page = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>기능인제 E2E 검증 보고서</title>
  <style>
    :root {{ font-family: "Segoe UI", system-ui, sans-serif; color: #0f172a; background: #f8fafc; }}
    body {{ margin: 0; padding: 24px; max-width: 1100px; margin-inline: auto; }}
    h1 {{ margin: 0 0 8px; font-size: 1.6rem; }}
    .meta {{ color: #64748b; font-size: 14px; margin-bottom: 20px; }}
    .badge {{ display: inline-block; padding: 6px 12px; border-radius: 999px; font-weight: 700; font-size: 13px; }}
    .badge.pass {{ background: #dcfce7; color: #166534; }}
    .badge.fail {{ background: #fee2e2; color: #991b1b; }}
    section {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 18px; margin-bottom: 16px; }}
    h2 {{ margin: 0 0 12px; font-size: 1.1rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; background: #f8fafc; padding: 8px; border-radius: 8px; }}
    code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
    .shots {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
    .shot {{ margin: 0; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; background: #fff; }}
    .shot figcaption {{ padding: 8px 10px; font-size: 13px; font-weight: 600; background: #fff7ed; color: #9a3412; }}
    .shot img {{ width: 100%; display: block; }}
    .flow {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
    .flow span {{ background: #eff6ff; color: #1d4ed8; padding: 6px 10px; border-radius: 8px; font-size: 13px; }}
    .flow span.arrow {{ background: transparent; color: #94a3b8; padding: 0 2px; }}
    tr.sev-critical td {{ background: #fef2f2; }}
    tr.sev-error td {{ background: #fff7ed; }}
    .urls a {{ display: block; margin: 4px 0; }}
  </style>
</head>
<body>
  <h1>기능인제(인사고과) E2E 검증 보고서</h1>
  <p class="meta">생성: {html.escape(str(data.get('generated_at','')))} · API: {html.escape(str(data.get('base_url','')))} · 현장 {html.escape(str(data.get('site_code','')))}</p>
  <p><span class="badge {status_cls}">{status_txt}</span></p>

  <section>
    <h2>검증 흐름</h2>
    <div class="flow">
      <span>① 팀장 팀원 평가</span><span class="arrow">→</span>
      <span>② 소장 직영 평가·현장 승인</span><span class="arrow">→</span>
      <span>③ 안전보건실 승인</span><span class="arrow">→</span>
      <span>④ 대표이사 최종 승인</span>
    </div>
  </section>

  <section>
    <h2>로컬 확인 URL</h2>
    <div class="urls">
      <a href="http://127.0.0.1:5174/login" target="_blank">로그인 — http://127.0.0.1:5174/login</a>
      <a href="http://127.0.0.1:5174/site/functional-eval" target="_blank">현장 기능인제 — http://127.0.0.1:5174/site/functional-eval</a>
      <a href="http://127.0.0.1:5174/hq-safe/functional-eval" target="_blank">본사 기능인제 — http://127.0.0.1:5174/hq-safe/functional-eval</a>
      <a href="http://127.0.0.1:8765/docs/reports/functional-eval-e2e/index.html" target="_blank">이 보고서 — http://127.0.0.1:8765/docs/reports/functional-eval-e2e/index.html</a>
    </div>
  </section>

  <section>
    <h2>테스트 계정 (청라 C18 · 24025)</h2>
    <table>
      <thead><tr><th>역할</th><th>로그인 ID</th><th>비밀번호</th></tr></thead>
      <tbody>{acct_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>발견 이슈 / 병목</h2>
    <table>
      <thead><tr><th>단계</th><th>심각도</th><th>내용</th><th>비고</th></tr></thead>
      <tbody>{issue_rows or "<tr><td colspan='4'>없음</td></tr>"}</tbody>
    </table>
  </section>

  <section>
    <h2>API 시뮬레이션 단계</h2>
    <table>
      <thead><tr><th>단계</th><th>결과</th></tr></thead>
      <tbody>{step_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>화면 캡처</h2>
    <div class="shots">{shot_blocks or "<p>캡처 없음</p>"}</div>
  </section>
</body>
</html>"""

    HTML_PATH.write_text(page, encoding="utf-8")
    print(f"wrote {HTML_PATH}")


if __name__ == "__main__":
    main()
