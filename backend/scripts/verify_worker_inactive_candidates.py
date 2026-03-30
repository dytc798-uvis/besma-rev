from __future__ import annotations

from pathlib import Path

import openpyxl
from sqlalchemy.orm import Session

from app.config.settings import BASE_DIR
from app.core.database import SessionLocal, init_db
from app.modules.workers.models import WorkerInactiveCandidate
from app.modules.workers.service import diff_employees_from_path, import_employees_from_path


def _make_missing_copy(src: Path, dst: Path, remove_row_indices: list[int]) -> None:
    wb = openpyxl.load_workbook(src)
    sh = wb[wb.sheetnames[0]]
    # 데이터 시작이 2행이므로, 호출 측에서 2 이상 인덱스만 전달한다고 가정
    # 큰 인덱스부터 지워야 앞쪽 인덱스가 틀어지지 않는다.
    for idx in sorted(remove_row_indices, reverse=True):
        sh.delete_rows(idx)
    dst.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dst)


def main() -> None:
    init_db()
    db: Session = SessionLocal()

    employees_path = BASE_DIR / "docs" / "sample" / "site_import" / "raw" / "employees_raw.xlsx"
    assert employees_path.exists(), f"employees_raw.xlsx not found at {employees_path}"

    print("=== 1) baseline import ===")
    batch = import_employees_from_path(db, employees_path)
    print("baseline batch:", batch.id, batch.total_rows, batch.created_rows, batch.updated_rows)

    # 2명 제거한 임시 파일 생성 (3,4행 삭제: 첫 두 명)
    tmp_dir = BASE_DIR / "tmp_worker_missing"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    missing_path = tmp_dir / "employees_missing_2rows.xlsx"
    _make_missing_copy(employees_path, missing_path, remove_row_indices=[4, 3])

    print("=== 2) diff with 2-row missing ===")
    diff1 = diff_employees_from_path(db, missing_path)
    print("missing_count after diff1:", diff1.missing_count)

    cands = db.query(WorkerInactiveCandidate).all()
    print(
        "candidates after diff1:",
        [(c.rrn_hash, c.status, c.missing_streak) for c in cands],
    )

    # 재등장 케이스: 원본 파일로 다시 diff
    print("=== 3) diff with full file (reappearance) ===")
    diff2 = diff_employees_from_path(db, employees_path)
    print("missing_count after diff2:", diff2.missing_count)
    cands2 = db.query(WorkerInactiveCandidate).all()
    print(
        "candidates after diff2:",
        [(c.rrn_hash, c.status, c.missing_streak) for c in cands2],
    )

    # 반복 누락: 같은 missing 파일로 연속 diff 두 번
    print("=== 4) repeated missing diff ===")
    diff3a = diff_employees_from_path(db, missing_path)
    diff3b = diff_employees_from_path(db, missing_path)
    print("missing_count after diff3a:", diff3a.missing_count)
    print("missing_count after diff3b:", diff3b.missing_count)
    cands3 = db.query(WorkerInactiveCandidate).all()
    print(
        "candidates after diff3b:",
        [(c.rrn_hash, c.status, c.missing_streak) for c in cands3],
    )


if __name__ == "__main__":
    main()

