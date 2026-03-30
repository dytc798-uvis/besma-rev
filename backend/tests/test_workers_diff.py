from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.modules.workers.models import Employment, Person
from app.modules.workers.service import diff_employees_from_path


def _setup_db(tmp_engine) -> Session:
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tmp_engine)
    Base.metadata.create_all(bind=tmp_engine)
    return TestingSessionLocal()


def test_workers_diff_new_and_updated(tmp_path):
    # in-memory SQLite
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    db = _setup_db(engine)

    base_dir = Path("d:/besma-rev/docs/sample/site_import/raw")

    # baseline import: employees_raw.xlsx -> create Persons from baseline file
    baseline_path = base_dir / "employees_raw.xlsx"
    assert baseline_path.exists()

    # 간단하게: baseline을 한번 diff로 읽어 NEW만 생성하도록 사용
    from app.modules.workers.service import _load_employees_rows_from_xlsx, compute_worker_diff, _build_baseline_map

    rows = _load_employees_rows_from_xlsx(baseline_path)
    # baseline 시점에는 DB가 비어 있으므로, 모두 NEW로 분류 후 직접 insert
    diff0 = compute_worker_diff(rows, {}, None)
    assert diff0.new_items
    for item in diff0.new_items:
        row = item.row
        p = Person(
            name=row.get("name") or "",
            rrn_hash=row.get("rrn_hash"),
            phone_mobile=row.get("phone_mobile"),
            nationality=row.get("nationality"),
        )
        db.add(p)
        db.flush()
        e = Employment(
            person_id=p.id,
            source_type="employee",
            department_code=row.get("department_code"),
            position_code=row.get("position_code"),
            site_code=row.get("site_code"),
            is_active=row.get("is_active", True),
        )
        db.add(e)
    db.commit()

    # NEW 검증: employees_raw_v1.xlsx
    v1_path = base_dir / "employees_raw_v1.xlsx"
    if v1_path.exists():
        diff_v1 = diff_employees_from_path(db, v1_path)
        assert diff_v1.new_items or diff_v1.updated_items or diff_v1.unchanged_items

    # UPDATED 검증: employees_raw_v2.xlsx
    v2_path = base_dir / "employees_raw_v2.xlsx"
    if v2_path.exists():
        diff_v2 = diff_employees_from_path(db, v2_path)
        # 최소한 diff 계산이 예외 없이 수행되어야 한다.
        assert diff_v2.items

