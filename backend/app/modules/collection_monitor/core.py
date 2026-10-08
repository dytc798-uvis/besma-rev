from __future__ import annotations

import calendar
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

VERSION = "collection-monitor-1.0.0"
GOV_CODES = {"24028", "25037", "25040", "25059", "25063", "26004", "26024", "26052"}
CATEGORIES = {
    "inspection": ("안전 점검", "1. 안전 점검"),
    "legal-training": ("법적교육", "2. 법적교육(특별,정기 등)"),
    "risk": ("위험성평가", "3. 위험성평가"),
    "opinions": ("근로자 의견 청취", "4. 근로자 의견 청취"),
    "site-training": ("현장안전보건 교육", "5. 현장안전보건 교육"),
    "safety-cost": ("산업안전보건관리비", "6. 산업안전보건관리비"),
    "nonconformity": ("부적합사항관리대장", "7. 부적합관리대장 취합"),
}
GOV_CATEGORY = {
    **{k: "risk" for k in ("GOV_RISK_INITIAL", "GOV_RISK_MONTHLY", "GOV_RISK_REGULAR", "GOV_RISK_MINUTES", "GOV_RISK_IMPROVEMENT")},
    **{k: "legal-training" for k in ("GOV_SITE_ORGANIZATION", "GOV_MANAGER_APPOINTMENT", "GOV_SAFETY_MANAGER_APPOINTMENT", "GOV_SUPERVISOR_DESIGNATION", "GOV_EMERGENCY_MANUAL", "GOV_EMERGENCY_ROLES", "GOV_HEALTH_EXAM")},
    **{k: "site-training" for k in ("GOV_EMERGENCY_DRILL", "GOV_TBM_MONTHLY", "GOV_REGULAR_EDUCATION", "GOV_SPECIAL_EDUCATION", "GOV_SUPERVISOR_EDUCATION")},
    **{k: "opinions" for k in ("GOV_OPINION_CHANNEL", "GOV_OPINION_IMPROVEMENT", "GOV_WORKER_OPINION_LEDGER")},
    "GOV_SAFETY_COST_MONTHLY": "safety-cost", "GOV_THEME_INSPECTION": "inspection",
    "GOV_NONCONFORMITY_LEDGER": "nonconformity",
}


def now():
    return datetime.now(timezone.utc).isoformat()

def is_evidence(row):
    return not any(word in row['filename'] for word in ('공정표','서명지','사진대지','포상','선정평가'))


def readonly(path):
    c = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA query_only=ON")
    return c


def state(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    c = sqlite3.connect(root / "collection.sqlite3", timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS copies(id TEXT PRIMARY KEY, relative_path TEXT NOT NULL,
      filename TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, category TEXT NOT NULL,
      month TEXT NOT NULL, period TEXT NOT NULL, site_id INTEGER, team TEXT,
      observed_at TEXT NOT NULL, classified_by INTEGER, classified_at TEXT);
    CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, month TEXT NOT NULL,
      observed_at TEXT NOT NULL, categories_json TEXT NOT NULL, error_count INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS scan_items(scan_id INTEGER NOT NULL, copy_id TEXT NOT NULL,
      PRIMARY KEY(scan_id, copy_id));
    CREATE TABLE IF NOT EXISTS mirrors(key TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
      relative_path TEXT NOT NULL, saved_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor_id INTEGER,
      action TEXT NOT NULL, copy_id TEXT, before_json TEXT, after_json TEXT, occurred_at TEXT NOT NULL);
    """)
    return c


def parse_month(value):
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", value):
        raise ValueError("INVALID_MONTH")
    y, m = map(int, value.split("-"))
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def period_key(frequency, day):
    d = date.fromisoformat(str(day)[:10])
    if frequency == "HALF_YEARLY":
        return f"{d.year}-H{1 if d.month <= 6 else 2}"
    if frequency in {"EVENT", "ADHOC"}:
        return "once"
    if frequency == "WEEKLY":
        first=d.replace(day=1)
        return f"{d:%Y-%m}-W{(d.day - 1 + first.weekday())//7 + 1}"
    return f"{d:%Y-%m}"


def sites(main, month):
    start, end = parse_month(month)
    result = []
    for row in main.execute("SELECT id,site_code,site_name,start_date,end_date,status FROM sites ORDER BY site_code"):
        s = dict(row)
        match = re.match(r"^\[(?:준공-)?([1-6])\.", s["site_name"])
        gov = s["site_code"] in GOV_CODES
        if not re.fullmatch(r"\d{5}", s["site_code"]) or not (match or gov):
            continue
        s.update(team="관급" if gov else match[1] + "팀", channel="BESMA" if gov else "NAVERWORKS",
                 active=not ((s["end_date"] and s["end_date"] < start.isoformat()) or
                             (s["start_date"] and s["start_date"] > end.isoformat()) or
                             s["site_name"].startswith("[준공")),
                 period_confirmed=bool(s["start_date"] and s["end_date"]))
        result.append(s)
    return result


def government_documents(main):
    codes = ",".join("?" for _ in GOV_CODES)
    return [dict(r) for r in main.execute(f"""
      SELECT d.id,d.instance_id,d.site_id,s.site_code,s.site_name,d.version_no,d.current_status,
      d.file_name,d.file_size,d.file_path,d.original_file_path,d.period_start,d.period_end,
      d.uploaded_at,COALESCE(i.document_type_code,d.document_type) AS code
      FROM documents d JOIN sites s ON s.id=d.site_id
      LEFT JOIN document_instances i ON i.id=d.instance_id
      WHERE s.site_code IN ({codes}) AND d.file_path IS NOT NULL
      ORDER BY d.id""", sorted(GOV_CODES)) if r["code"] in GOV_CATEGORY]


def overview(main_path, root, month):
    start, end = parse_month(month)
    with readonly(main_path) as main, state(root) as c:
        all_sites = sites(main, month)
        definitions = {"NAS_" + k: {"code": "NAS_" + k, "title": v[0], "frequency": "WEEKLY" if k == "nonconformity" else "MONTHLY", "channel": "NAVERWORKS", "category": k} for k,v in CATEGORIES.items()}
        gov_reqs = {}
        for r in main.execute("SELECT site_id,code,title,frequency FROM document_requirements WHERE is_enabled=1 AND is_required=1 AND code LIKE 'GOV_%'"):
            if r["code"] in GOV_CATEGORY:
                definitions[r["code"]] = {"code": r["code"], "title": r["title"].removeprefix("관급 "), "frequency": r["frequency"], "channel": "BESMA", "category": GOV_CATEGORY[r["code"]]}
                gov_reqs.setdefault(r["site_id"], []).append(r["code"])
        scan = c.execute("SELECT * FROM scans WHERE month=? ORDER BY id DESC LIMIT 1", (month,)).fetchone()
        scanned = json.loads(scan["categories_json"]) if scan else []
        copies = [dict(r) for r in c.execute("SELECT * FROM copies WHERE month=? AND id IN (SELECT copy_id FROM scan_items WHERE scan_id=?)", (month,scan['id'] if scan else 0)) if is_evidence(r)]
        docs = government_documents(main)
        rows = []
        today = date.today()
        cutoff = min(end, today) if start <= today else start
        for s in all_sites:
            keys = gov_reqs.get(s["id"], []) if s["channel"] == "BESMA" else ["NAS_" + k for k in CATEGORIES]
            cells = []
            for key in keys:
                definition = definitions[key]
                if definition["frequency"] == "WEEKLY":
                    expected = [f"{month}-W{w}" for w in range(1, (cutoff.day-1+start.weekday())//7+2)]
                else:
                    expected = [period_key(definition["frequency"], start)]
                if s["channel"] == "BESMA":
                    evidence = [d for d in docs if d["site_id"] == s["id"] and d["code"] == key]
                    received=set()
                    for d in evidence:
                        if definition["frequency"]=="WEEKLY" and d["period_start"] and d["period_end"]:
                            a=date.fromisoformat(d["period_start"][:10]);b=date.fromisoformat(d["period_end"][:10])
                            if a<=end and b>=start:received.add(period_key("WEEKLY",max(a,start)))
                        else:received.add(period_key(definition["frequency"],d["period_start"] or d["uploaded_at"] or start))
                    known = True
                else:
                    evidence = [d for d in copies if d["site_id"] == s["id"] and d["category"] == definition["category"]]
                    received = {d["period"] for d in evidence}
                    pending = [d for d in copies if d["category"] == definition["category"] and (d["site_id"] is None or not d["period"])]
                    known = definition["category"] in scanned and not pending
                count = len(set(expected) & received)
                cells.append({**definition, "expected": len(expected) if s["active"] else 0,
                  "received": count if s["active"] else 0, "known": known,
                  "missing_periods": [p for p in expected if p not in received],
                  "evidence_count": len(evidence), "latest_instance_id":evidence[-1].get("instance_id") if evidence else None,
                  "latest_document_id":evidence[-1].get("id") if evidence and s["channel"]=="BESMA" else None,
                  "status": "NOT_REQUIRED" if not s["active"] else "SUBMITTED" if count == len(expected) else "NOT_SUBMITTED" if known else "UNCONFIRMED"})
            target = sum(x["expected"] for x in cells)
            done = sum(x["received"] for x in cells)
            rows.append({**s, "cells": cells, "required": target, "received": done,
                "rate": round(100*done/target,1) if target and all(x["known"] for x in cells) else None})
        summaries = []
        for key, definition in definitions.items():
            cells = [c for row in rows for c in row["cells"] if c["code"] == key and c["expected"]]
            total = sum(x["expected"] for x in cells)
            done = sum(x["received"] for x in cells)
            summaries.append({**definition, "required": total, "received": done,
                "rate": round(100*done/total,1) if total and all(x["known"] for x in cells) else None})
        unmapped = [r for r in copies if r["site_id"] is None or not r["period"]]
        return {"version": VERSION, "month": month, "sites": rows, "documents": summaries,
            "unmapped_count": len(unmapped), "scan": dict(scan) if scan else None,
            "mirror_count": c.execute("SELECT COUNT(*) FROM mirrors").fetchone()[0]}


def ingest(main_path, root, manifest, blobs):
    # Validated monthly copies only. No source path escapes, overwrites or deletion.
    parse_month(manifest["month"])
    if not set(manifest["complete_categories"]) <= set(CATEGORIES):
        raise ValueError("INVALID_CATEGORY")
    with readonly(main_path) as main, state(root) as c:
        ids = {r[0] for r in main.execute("SELECT id FROM sites")}
        records = manifest["files"]
        if len(records) > 10000:
            raise ValueError("TOO_MANY_FILES")
        verified = []
        for r in records:
            rel = r["relative_path"].replace("\\", "/")
            if rel.startswith("/") or ":" in rel or ".." in rel.split("/") or r["category"] not in CATEGORIES:
                raise ValueError("INVALID_SOURCE_PATH")
            if r.get("site_id") is not None and r["site_id"] not in ids:
                raise ValueError("INVALID_SITE")
            sha = r["sha256"]
            if not re.fullmatch("[0-9a-f]{64}", sha) or not 0 < r["size"] <= 100*1024*1024:
                raise ValueError("INVALID_CONTENT")
            p = Path(blobs) / sha
            if not p.exists(): p = Path(root) / "objects" / sha
            if p.is_symlink() or not p.is_file() or p.stat().st_size != r["size"] or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                raise ValueError("CONTENT_HASH_MISMATCH")
            verified.append((r, p))
        for r,p in verified:
            dest = Path(root) / "objects" / r["sha256"]
            dest.parent.mkdir(exist_ok=True, mode=0o750)
            if not dest.exists():
                with dest.open("xb") as f:
                    f.write(p.read_bytes())
                dest.chmod(0o640)
            elif hashlib.sha256(dest.read_bytes()).hexdigest() != r["sha256"]:
                raise ValueError("EXISTING_OBJECT_MISMATCH")
            ident = hashlib.sha256((r["relative_path"] + "\0" + r["sha256"]).encode()).hexdigest()
            c.execute("INSERT OR IGNORE INTO copies VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (ident,r["relative_path"],r["filename"],r["sha256"],r["size"],r["category"],manifest["month"],r["period"],r.get("site_id"),r.get("team"),now(),None,None))
            if r.get('site_id') is not None:
                c.execute('UPDATE copies SET site_id=?,period=? WHERE id=? AND site_id IS NULL AND classified_by IS NULL',(r['site_id'],r['period'],ident))
        cursor = c.execute("INSERT INTO scans(month,observed_at,categories_json,error_count) VALUES(?,?,?,?)", (manifest["month"],now(),json.dumps(manifest["complete_categories"]),manifest["error_count"]))
        for r,p in verified:
            ident = hashlib.sha256((r["relative_path"] + "\0" + r["sha256"]).encode()).hexdigest()
            c.execute("INSERT INTO scan_items VALUES(?,?)", (cursor.lastrowid,ident))
        c.commit()
        return {"files": len(verified), "scan_id": cursor.lastrowid}
