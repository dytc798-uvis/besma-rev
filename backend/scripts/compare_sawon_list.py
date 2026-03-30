"""Compare two 사원리스트 .xls files in docs/sample/site_import/raw."""
from __future__ import annotations

import hashlib
from pathlib import Path

import xlrd


def read_all_rows(path: Path) -> list[tuple[str, list[tuple]]]:
    wb = xlrd.open_workbook(path, formatting_info=False, ignore_workbook_corruption=True)
    out: list[tuple[str, list[tuple]]] = []
    for si in range(wb.nsheets):
        sh = wb.sheet_by_index(si)
        rows = [tuple(sh.row_values(ri)) for ri in range(sh.nrows)]
        out.append((wb.sheet_names()[si], rows))
    return out


def norm_cell(v: object) -> str:
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if v is None:
        return ""
    return str(v).strip()


def row_key(row: tuple) -> str | None:
    if not row:
        return None
    parts = [norm_cell(c) for c in row[:12]]
    if not any(parts):
        return None
    return "|".join(parts)


def main() -> None:
    raw = Path(__file__).resolve().parents[2] / "docs" / "sample" / "site_import" / "raw"
    new_path = raw / "사원리스트_20260326082818.xls"
    old_path = raw / "사원리스트.xls"
    if not new_path.is_file():
        new_paths = sorted(raw.glob("*20260326082818*.xls"))
        if not new_paths:
            raise SystemExit(f"Missing new file: {new_path.name}")
        new_path = new_paths[0]
    if not old_path.is_file():
        raise SystemExit(f"Missing baseline file: {old_path.name}")

    print(f"OLD: {old_path.name} ({old_path.stat().st_size} bytes)")
    print(f"NEW: {new_path.name} ({new_path.stat().st_size} bytes)")

    def sha_prefix(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

    print(f"SHA256 prefix OLD: {sha_prefix(old_path)}")
    print(f"SHA256 prefix NEW: {sha_prefix(new_path)}")

    old_sheets = read_all_rows(old_path)
    new_sheets = read_all_rows(new_path)
    print(f"Sheets OLD: {[n for n, _ in old_sheets]}")
    print(f"Sheets NEW: {[n for n, _ in new_sheets]}")

    for idx, ((sn_old, rows_old), (sn_new, rows_new)) in enumerate(zip(old_sheets, new_sheets)):
        print(f"\n--- Sheet pair [{idx}] OLD={sn_old!r} NEW={sn_new!r} ---")
        print(f"Row count: {len(rows_old)} -> {len(rows_new)}")

        keys_old = {k for r in rows_old for k in [row_key(r)] if k}
        keys_new = {k for r in rows_new for k in [row_key(r)] if k}
        added = keys_new - keys_old
        removed = keys_old - keys_new
        print(f"Non-empty row keys: OLD={len(keys_old)} NEW={len(keys_new)}")
        print(f"ADDED (new keys): {len(added)}")
        print(f"REMOVED (missing keys): {len(removed)}")

        if added:
            print("Sample ADDED (first 8, first 8 cells):")
            for i, k in enumerate(list(added)[:8]):
                row = next((r for r in rows_new if row_key(r) == k), ())
                print(f"  {i + 1}. {tuple(norm_cell(c) for c in row[:8])}")
        if removed:
            print("Sample REMOVED (first 8, first 8 cells):")
            for i, k in enumerate(list(removed)[:8]):
                row = next((r for r in rows_old if row_key(r) == k), ())
                print(f"  {i + 1}. {tuple(norm_cell(c) for c in row[:8])}")

        # Same keys but different full row (cell edits)
        common = keys_old & keys_new
        changed = 0
        samples: list[tuple[tuple, tuple]] = []
        for k in common:
            ro = next(r for r in rows_old if row_key(r) == k)
            rn = next(r for r in rows_new if row_key(r) == k)
            if ro != rn:
                changed += 1
                if len(samples) < 5:
                    samples.append((ro, rn))
        print(f"SAME key but different row content: {changed}")
        for i, (ro, rn) in enumerate(samples, 1):
            print(f"  Change sample {i} OLD[:10]: {tuple(norm_cell(c) for c in ro[:10])}")
            print(f"  Change sample {i} NEW[:10]: {tuple(norm_cell(c) for c in rn[:10])}")


if __name__ == "__main__":
    main()
