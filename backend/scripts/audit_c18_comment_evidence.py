"""Match C18 submission PDFs to uploaded documents and audit extractable evidence.

This script is read-only. It never edits the source PDFs or the BESMA database.
Only PDFs whose filename/folder date and document type match an existing C18
document are included. Scanned/image-only files are reported but not treated as
text evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ADHOC_RISK_ASSESSMENT", re.compile(r"수시위험성|수시위평", re.I)),
    ("SITE_MANAGER_CHECKLIST", re.compile(r"현장소장점검|소장점검|현장소장", re.I)),
    ("SUPERVISOR_CHECKLIST", re.compile(r"관리감독자점검|관리감독자", re.I)),
    (
        "SAFETY_MANAGER_DAILY_LOG",
        re.compile(r"안전관리자.*(?:업무|일일|점검).*일지|안전담당자.*일지", re.I),
    ),
    ("DAILY_SAFETY_MEETING_LOG", re.compile(r"안전회의|작업안전회의", re.I)),
    ("DAILY_TBM", re.compile(r"TBM", re.I)),
    ("DAILY_RISK_ASSESSMENT", re.compile(r"일일위험성|위험성평가|위평", re.I)),
)

DATE_RE = re.compile(r"(?<!\d)26[.\-_]?(0[1-9]|1[0-2])[.\-_]?([0-3]\d)(?!\d)")
RISK_RE = re.compile(
    r"추락|감전|미끄|낙하|끼임|화재|전도|붕괴|충돌|보호구|안전대|"
    r"작업발판|통로|개구부|사다리|고소|양중|굴착|배선|누전|우천|폭염"
)


def _classify(name: str) -> str | None:
    for code, pattern in TYPE_PATTERNS:
        if pattern.search(name):
            return code
    return None


def _work_date(path: Path) -> str | None:
    for value in (path.name, *reversed(path.parts)):
        match = DATE_RE.search(value)
        if match:
            return f"2026-{match.group(1)}-{match.group(2)}"
    return None


def _extract_text(path: Path) -> tuple[str, int]:
    pdf = fitz.open(path)
    try:
        text = "\n".join(page.get_text("text") for page in pdf)
        return re.sub(r"\s+", " ", text).strip(), len(pdf)
    finally:
        pdf.close()


def _evidence_snippets(text: str) -> list[str]:
    snippets: list[str] = []
    for segment in re.split(r"(?<=[.。])\s+|\n+", text):
        value = re.sub(r"\s+", " ", segment).strip()
        if RISK_RE.search(value) and 12 <= len(value) <= 220 and value not in snippets:
            snippets.append(value)
    return snippets


def _path_preference(path: str) -> int:
    value = path.replace("/", "\\")
    if "\\16. 유해위험요인 관리(점검일지)" in value:
        return 30
    if "\\15. 유해위험요인 관리(수시위평)" in value:
        return 30
    if "\\99 현장서류 (구분 전)" in value:
        return 10
    return 20


def _recent_unique_matches(matches: list[dict], limit: int) -> list[dict]:
    selected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    ranked = sorted(
        matches,
        key=lambda row: (row["work_date"], _path_preference(row["path"]), row["text_chars"]),
        reverse=True,
    )
    for row in ranked:
        key = (row["document_type"], row["work_date"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _ocr_pdf(path: Path, *, dpi: int = 220) -> dict:
    pdf = fitz.open(path)
    page_results: list[dict] = []
    try:
        for page_index, page in enumerate(pdf):
            pixmap = page.get_pixmap(dpi=dpi, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            data = pytesseract.image_to_data(
                image,
                lang="kor+eng",
                config="--oem 3 --psm 6",
                output_type=pytesseract.Output.DICT,
            )
            tokens: list[str] = []
            confidences: list[float] = []
            for token, raw_confidence in zip(data["text"], data["conf"], strict=False):
                value = re.sub(r"\s+", " ", token).strip()
                try:
                    confidence = float(raw_confidence)
                except (TypeError, ValueError):
                    confidence = -1
                if value:
                    tokens.append(value)
                if confidence >= 0 and value:
                    confidences.append(confidence)
            text = " ".join(tokens)
            page_results.append(
                {
                    "page": page_index + 1,
                    "text": text,
                    "mean_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0.0,
                    "hangul_chars": len(re.findall(r"[가-힣]", text)),
                    "evidence": _evidence_snippets(text)[:5],
                }
            )
    finally:
        pdf.close()
    combined = " ".join(page["text"] for page in page_results)
    evidence = _evidence_snippets(combined)[:8]
    useful_pages = [page for page in page_results if page["text"]]
    weighted_confidence = (
        round(sum(page["mean_confidence"] for page in useful_pages) / len(useful_pages), 1)
        if useful_pages
        else 0.0
    )
    return {
        "pages": page_results,
        "mean_confidence": weighted_confidence,
        "text_chars": len(combined),
        "hangul_chars": len(re.findall(r"[가-힣]", combined)),
        "evidence": evidence,
        "reliable_evidence": weighted_confidence >= 55 and len(evidence) > 0,
    }


def build_report(root: Path, db_path: Path, site_id: int) -> dict:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    seen_hashes: set[str] = set()
    matches: list[dict] = []
    try:
        for path in root.rglob("*.pdf"):
            if "폐기예정" in path.parts:
                continue
            document_type = _classify(path.name)
            work_date = _work_date(path)
            if not document_type or not work_date:
                continue
            documents = db.execute(
                """
                SELECT id, file_name, uploaded_at
                FROM documents
                WHERE site_id = ? AND document_type = ? AND period_start = ?
                ORDER BY id
                """,
                (site_id, document_type, work_date),
            ).fetchall()
            if not documents:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            try:
                text, pages = _extract_text(path)
                error = None
            except Exception as exc:  # pragma: no cover - operational diagnostics
                text, pages, error = "", 0, str(exc)
            hangul_count = len(re.findall(r"[가-힣]", text))
            reliable_text = len(text) >= 300 and hangul_count >= 80
            matches.append(
                {
                    "document_type": document_type,
                    "work_date": work_date,
                    "path": str(path),
                    "sha256": digest,
                    "pages": pages,
                    "text_chars": len(text),
                    "hangul_chars": hangul_count,
                    "reliable_text": reliable_text,
                    "document_ids": [int(row["id"]) for row in documents],
                    "evidence": _evidence_snippets(text)[:5] if reliable_text else [],
                    "error": error,
                }
            )
    finally:
        db.close()

    type_summary = {}
    for document_type in sorted({row["document_type"] for row in matches}):
        rows = [row for row in matches if row["document_type"] == document_type]
        type_summary[document_type] = {
            "unique_files": len(rows),
            "matched_dates": len({row["work_date"] for row in rows}),
            "reliable_text_files": sum(bool(row["reliable_text"]) for row in rows),
            "image_only_or_short": sum(row["text_chars"] < 20 for row in rows),
            "median_text_chars": int(statistics.median(row["text_chars"] for row in rows)),
        }
    return {"matched_unique_files": len(matches), "type_summary": type_summary, "matches": matches}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--site-id", type=int, default=8)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--ocr-recent", type=int, default=0)
    parser.add_argument(
        "--tesseract-cmd",
        type=Path,
        default=Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    )
    args = parser.parse_args()
    report = build_report(args.root, args.db, args.site_id)
    print(json.dumps({k: v for k, v in report.items() if k != "matches"}, ensure_ascii=False, indent=2))
    evidence_rows = [row for row in report["matches"] if row["evidence"]]
    print("\nEVIDENCE SAMPLES")
    for row in sorted(evidence_rows, key=lambda item: item["work_date"], reverse=True)[:15]:
        print(
            f"{row['work_date']} {row['document_type']} doc={row['document_ids'][0]} "
            f"chars={row['text_chars']} | {' / '.join(row['evidence'])[:450]}"
        )
    if args.ocr_recent:
        pytesseract.pytesseract.tesseract_cmd = str(args.tesseract_cmd)
        print(f"\nOCR RECENT {args.ocr_recent}")
        ocr_rows = []
        for row in _recent_unique_matches(report["matches"], args.ocr_recent):
            ocr = _ocr_pdf(Path(row["path"]))
            row["ocr"] = ocr
            ocr_rows.append(row)
            evidence_text = " / ".join(ocr["evidence"])[:500] or "(위험요인 문구 미확인)"
            print(
                f"{row['work_date']} {row['document_type']} doc={row['document_ids'][0]} "
                f"confidence={ocr['mean_confidence']} reliable={ocr['reliable_evidence']} | {evidence_text}"
            )
        report["ocr_recent"] = ocr_rows
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
