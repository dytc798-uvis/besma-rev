"""Normalize duplicated scripted C18 approval comments with a full DB backup.

The operation is deliberately narrow:
- only the Cheongna C18 site is considered;
- only exact comments emitted by the two C18 backfill/repair scripts qualify;
- only comments duplicated at least twice qualify;
- no approval, reply, timestamp, author, or status row is added or removed;
- matching document review-history comments are updated in the same transaction.

The ten recent evidence overrides were transcribed from the dated source PDFs in
the Samsung recognition submission folder. Ambiguous documents intentionally use
short acknowledgements instead of inferred hazards.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import backfill_c18_approval_comments as backfill
import repair_c18_corrupted_approval_comments as repair


CONFIRM_TOKEN = "NORMALIZE_C18_DUPLICATE_APPROVAL_COMMENTS"


@dataclass(frozen=True)
class EvidenceOverride:
    approval_history_id: int
    document_id: int
    document_type: str
    work_date: str
    comment: str
    basis: str


EVIDENCE_OVERRIDES: tuple[EvidenceOverride, ...] = (
    EvidenceOverride(
        362,
        357,
        "DAILY_TBM",
        "2026-07-10",
        "확인했습니다. 고소작업대 전도·낙하 방지와 중량물 운반 시 2인 1조·대차 사용을 지켜 주세요.",
        "TBM 원본: 고소작업대 전도·낙하, 중량물 인력운반 근골격계 위험 및 2인 1조·대차 사용 대책 확인",
    ),
    EvidenceOverride(
        363,
        358,
        "DAILY_RISK_ASSESSMENT",
        "2026-07-10",
        "위험성평가 확인했습니다. 감사합니다.",
        "수기 판독 신뢰도 부족: 구체 위험요인 미추정",
    ),
    EvidenceOverride(
        364,
        359,
        "DAILY_SAFETY_MEETING_LOG",
        "2026-07-10",
        "확인했습니다. 고소작업대 내부 정리정돈 상태를 작업 전에 확인해 주세요.",
        "안전회의 원본 요청사항: 고소작업대 내부 정리정돈 철저",
    ),
    EvidenceOverride(
        365,
        360,
        "SUPERVISOR_CHECKLIST",
        "2026-07-10",
        "확인했습니다. 고소작업대 사용 전 점검과 작업구간 구획설정, 안전통로 확보를 유지해 주세요.",
        "관리감독자 점검 원본: 사용 전 점검, 구획설정 및 안전통로 확보 대책 확인",
    ),
    EvidenceOverride(
        366,
        361,
        "SITE_MANAGER_CHECKLIST",
        "2026-07-10",
        "확인했습니다. 고소작업대 작업 전 점검, 구획설정과 유도자 배치를 계속 확인해 주세요.",
        "소장점검 원본: 작업 전 점검, 구획설정·유도자 배치 대책 확인",
    ),
    EvidenceOverride(
        368,
        363,
        "DAILY_TBM",
        "2026-07-11",
        "TBM 확인했습니다. 작업구간 정리정돈과 추락·낙하 방지대책을 작업 전에 재확인해 주세요.",
        "TBM 원본: 전도·낙하 위험과 작업구간 정리 및 안전조치 내용 확인",
    ),
    EvidenceOverride(
        369,
        364,
        "SITE_MANAGER_CHECKLIST",
        "2026-07-11",
        "점검표 확인했습니다. 고소작업대 작업 전 점검과 구획설정·유도자 배치 상태를 유지해 주세요.",
        "소장점검 원본: 고소작업대 협착·충돌 위험, 점검·구획설정·유도자 배치 대책 확인",
    ),
    EvidenceOverride(
        370,
        365,
        "SUPERVISOR_CHECKLIST",
        "2026-07-11",
        "확인했습니다. 고소작업대 사용 전 점검, 작업구간 구획설정과 과상승 방지조치를 계속 확인해 주세요.",
        "관리감독자 점검 원본: 전도·낙하 위험, 사용 전 점검·구획설정·과상승 방지 대책 확인",
    ),
    EvidenceOverride(
        371,
        366,
        "DAILY_SAFETY_MEETING_LOG",
        "2026-07-11",
        "확인했습니다. 공도구와 작업구간 정리정돈을 철저히 해 주세요.",
        "안전회의 원본 요청사항: 공도구 정리정돈 철저",
    ),
    EvidenceOverride(
        372,
        367,
        "DAILY_RISK_ASSESSMENT",
        "2026-07-11",
        "문서 확인했습니다. 감사합니다.",
        "수기 판독 신뢰도 부족: 구체 위험요인 미추정",
    ),
)


TYPE_LABELS = {
    "DAILY_TBM": "TBM",
    "DAILY_RISK_ASSESSMENT": "위험성평가",
    "ADHOC_RISK_ASSESSMENT": "수시위험성평가",
    "DAILY_SAFETY_MEETING_LOG": "안전회의",
    "SUPERVISOR_CHECKLIST": "관리감독자 점검표",
    "SITE_MANAGER_CHECKLIST": "소장점검표",
    "SAFETY_MANAGER_DAILY_LOG": "안전관리자 일지",
    "EMERGENCY_DRILL_REPORT": "비상훈련 보고서",
    "MSDS_EDUCATION": "MSDS 교육자료",
    "REGULAR_EDUCATION": "정기교육 자료",
    "SPECIAL_EDUCATION": "특별교육 자료",
    "AUTO_WORKER_OPINION_LOG": "근로자 의견자료",
    "DAILY_DOC": "문서",
}

SHORT_PATTERNS = (
    "{label} 확인했습니다.",
    "{label} 내용 확인했습니다.",
    "{label} 검토했습니다.",
    "{label} 확인했습니다. 감사합니다.",
    "{label} 검토 완료했습니다.",
    "확인했습니다. {label} 내용 이상 없습니다.",
    "수고하셨습니다. {label} 확인했습니다.",
    "확인하였습니다. 감사합니다.",
)


def _flatten(values: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(values, str):
        result.add(values.strip())
    elif isinstance(values, dict):
        for item in values.values():
            result.update(_flatten(item))
    else:
        for item in values:
            result.update(_flatten(item))
    return result


def scripted_templates() -> set[str]:
    return {
        value
        for value in (
            _flatten(backfill.GENERAL_COMMENTS)
            | _flatten(backfill.RAIN_COMMENTS)
            | _flatten(repair.GENERAL_HQ_COMMENTS_BY_TYPE)
            | _flatten(repair.FALLBACK_HQ_COMMENTS)
            | _flatten(repair.RAIN_HQ_COMMENTS_BY_TYPE)
            | _flatten(repair.FALLBACK_RAIN_HQ_COMMENTS)
        )
        if value
    }


def _short_comment(document_type: str, approval_history_id: int) -> str:
    label = TYPE_LABELS.get(document_type, "문서")
    pattern = SHORT_PATTERNS[approval_history_id % len(SHORT_PATTERNS)]
    return pattern.format(label=label)


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def build_plan(db: sqlite3.Connection, site_code: str) -> tuple[list[dict], dict]:
    db.row_factory = sqlite3.Row
    templates = sorted(scripted_templates())
    placeholders = ",".join("?" for _ in templates)
    site = db.execute("SELECT id, site_name FROM sites WHERE site_code = ?", (site_code,)).fetchone()
    if not site:
        raise RuntimeError(f"site not found: {site_code}")
    site_id = int(site["id"])
    duplicate_comments = {
        str(row["comment"]).strip()
        for row in db.execute(
            f"""
            SELECT TRIM(h.comment) AS comment, COUNT(*) AS n
            FROM approval_histories h
            JOIN documents d ON d.id = h.document_id
            WHERE d.site_id = ? AND TRIM(h.comment) IN ({placeholders})
            GROUP BY TRIM(h.comment)
            HAVING COUNT(*) > 1
            """,
            (site_id, *templates),
        ).fetchall()
    }
    if not duplicate_comments:
        return [], {"site_id": site_id, "site_name": site["site_name"], "duplicated_templates": 0}
    duplicate_placeholders = ",".join("?" for _ in duplicate_comments)
    rows = db.execute(
        f"""
        SELECT h.id AS approval_history_id, h.document_id, h.action_type, h.action_at,
               h.action_by_user_id, h.comment AS old_comment,
               d.document_type, d.period_start, d.current_status
        FROM approval_histories h
        JOIN documents d ON d.id = h.document_id
        WHERE d.site_id = ?
          AND TRIM(h.comment) IN ({duplicate_placeholders})
          AND h.action_type IN ('APPROVE', 'REJECT')
        ORDER BY h.action_at, h.id
        """,
        (site_id, *sorted(duplicate_comments)),
    ).fetchall()
    overrides = {row.approval_history_id: row for row in EVIDENCE_OVERRIDES}
    plan: list[dict] = []
    for row in rows:
        approval_id = int(row["approval_history_id"])
        override = overrides.get(approval_id)
        if override:
            actual = (int(row["document_id"]), row["document_type"], str(row["period_start"]))
            expected = (override.document_id, override.document_type, override.work_date)
            if actual != expected:
                raise RuntimeError(f"evidence target mismatch for approval {approval_id}: {actual} != {expected}")
            new_comment = override.comment
            reason = "recent_pdf_evidence" if "신뢰도 부족" not in override.basis else "recent_pdf_generic"
            basis = override.basis
        else:
            new_comment = _short_comment(str(row["document_type"]), approval_id)
            reason = "duplicate_scripted_template"
            basis = "동일 자동 생성 승인 문구가 반복되어 짧은 확인 문구로 정리"
        review_rows = db.execute(
            """
            SELECT id
            FROM document_review_histories
            WHERE document_id = ? AND action_type = ? AND action_at = ? AND comment = ?
            ORDER BY id
            """,
            (row["document_id"], row["action_type"], row["action_at"], row["old_comment"]),
        ).fetchall()
        if len(review_rows) > 1:
            raise RuntimeError(f"multiple matching review histories for approval {approval_id}")
        plan.append(
            {
                **dict(row),
                "review_history_id": int(review_rows[0]["id"]) if review_rows else None,
                "new_comment": new_comment,
                "reason": reason,
                "basis": basis,
            }
        )
    meta = {
        "site_id": site_id,
        "site_name": site["site_name"],
        "duplicated_templates": len(duplicate_comments),
        "scripted_template_count": len(templates),
    }
    return plan, meta


def apply_plan(db: sqlite3.Connection, plan: list[dict]) -> None:
    before_counts = {
        "approval_histories": db.execute("SELECT COUNT(*) FROM approval_histories").fetchone()[0],
        "document_review_histories": db.execute("SELECT COUNT(*) FROM document_review_histories").fetchone()[0],
        "document_comments": db.execute("SELECT COUNT(*) FROM document_comments").fetchone()[0],
    }
    db.execute("BEGIN IMMEDIATE")
    try:
        for item in plan:
            cursor = db.execute(
                "UPDATE approval_histories SET comment = ? WHERE id = ? AND comment = ?",
                (item["new_comment"], item["approval_history_id"], item["old_comment"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"approval changed concurrently: {item['approval_history_id']}")
            if item["review_history_id"] is not None:
                cursor = db.execute(
                    "UPDATE document_review_histories SET comment = ? WHERE id = ? AND comment = ?",
                    (item["new_comment"], item["review_history_id"], item["old_comment"]),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"review changed concurrently: {item['review_history_id']}")
        after_counts = {
            "approval_histories": db.execute("SELECT COUNT(*) FROM approval_histories").fetchone()[0],
            "document_review_histories": db.execute("SELECT COUNT(*) FROM document_review_histories").fetchone()[0],
            "document_comments": db.execute("SELECT COUNT(*) FROM document_comments").fetchone()[0],
        }
        if before_counts != after_counts:
            raise RuntimeError(f"row counts changed: {before_counts} != {after_counts}")
        for item in plan:
            value = db.execute(
                "SELECT comment FROM approval_histories WHERE id = ?", (item["approval_history_id"],)
            ).fetchone()[0]
            if value != item["new_comment"]:
                raise RuntimeError(f"approval verification failed: {item['approval_history_id']}")
        db.commit()
    except Exception:
        db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/home/ubuntu/besma-rev/database/besma.db"))
    parser.add_argument("--site-code", default="24025")
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path("/home/ubuntu/besma-ops-backups/c18-approval-comment-normalization"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")

    db = sqlite3.connect(args.db, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        plan, meta = build_plan(db, args.site_code)
        reason_counts: dict[str, int] = {}
        for item in plan:
            reason_counts[item["reason"]] = reason_counts.get(item["reason"], 0) + 1
        print(
            json.dumps(
                {
                    **meta,
                    "mode": "apply" if args.apply else "dry-run",
                    "planned_updates": len(plan),
                    "reason_counts": reason_counts,
                    "review_history_updates": sum(item["review_history_id"] is not None for item in plan),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        for item in plan[-15:]:
            print(
                f"approval={item['approval_history_id']} doc={item['document_id']} "
                f"{item['document_type']} {item['period_start']} reason={item['reason']}\n"
                f"  old={item['old_comment']}\n  new={item['new_comment']}"
            )
        if not args.apply:
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_comment_normalization_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_comment_normalization_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        apply_plan(db, plan)
        manifest = {
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": str(args.db),
            "backup_db": str(backup_path),
            "meta": meta,
            "updates": plan,
            "evidence_overrides": [asdict(row) for row in EVIDENCE_OVERRIDES],
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        print(f"applied_updates={len(plan)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
