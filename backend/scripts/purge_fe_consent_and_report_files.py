"""기능인제 동의서·평가보고서 PDF 파일만 삭제 (DB 미변경).

대상: storage/functional_eval/signatures/*.pdf
  - consent_{login_id}_*.pdf  (동의서)
  - fe_{STAGE}_*.pdf          (팀장·소장·본사·대표 평가보고서)

DB의 functional_eval_consents / functional_eval_signatures 행은 그대로 둡니다.
다음 서명·동의 시 새 PDF가 생성됩니다. (기존 DB 경로는 깨질 수 있음 — 실운영 전 초기화용)

Usage:
  cd backend && PYTHONPATH=. python scripts/purge_fe_consent_and_report_files.py
  cd backend && PYTHONPATH=. python scripts/purge_fe_consent_and_report_files.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.settings import settings  # noqa: E402


def signature_pdf_dir() -> Path:
    return settings.storage_root / "functional_eval" / "signatures"


def classify_pdf(name: str) -> str:
    lower = name.lower()
    if lower.startswith("consent_"):
        return "consent"
    if lower.startswith("fe_"):
        return "report"
    return "other"


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge FE consent/report PDF files only")
    parser.add_argument("--dry-run", action="store_true", help="List files without deleting")
    args = parser.parse_args()

    sig_dir = signature_pdf_dir()
    if not sig_dir.is_dir():
        print(f"nothing to do: directory missing: {sig_dir}")
        return

    pdfs = sorted(sig_dir.glob("*.pdf"))
    counts = {"consent": 0, "report": 0, "other": 0}
    deleted = 0
    bytes_total = 0

    for pdf in pdfs:
        kind = classify_pdf(pdf.name)
        counts[kind] += 1
        size = pdf.stat().st_size
        bytes_total += size
        action = "would delete" if args.dry_run else "deleted"
        print(f"[{kind}] {action}: {pdf.name} ({size:,} bytes)")
        if not args.dry_run:
            pdf.unlink(missing_ok=True)
            deleted += 1

    mode = "DRY-RUN" if args.dry_run else "DONE"
    print(
        f"\n{mode} dir={sig_dir} "
        f"pdf_total={len(pdfs)} consent={counts['consent']} report={counts['report']} "
        f"other={counts['other']} bytes={bytes_total:,}"
    )
    if not args.dry_run:
        print(f"deleted={deleted} (database untouched)")


if __name__ == "__main__":
    main()
