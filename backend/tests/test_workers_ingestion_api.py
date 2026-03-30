from pathlib import Path
import json

import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_db, get_current_user_with_bypass
from app.core.database import Base
from app.main import app
from app.modules.users.models import User
from app.modules.workers.models import Employment


RAW_DIR = Path("d:/besma-rev/docs/sample/site_import/raw")


def _setup_test_client(tmp_path: Path, *, role: str = "HQ_SAFE", ui_type: str = "HQ_SAFE"):
    db_file = tmp_path / "workers_ingestion_api.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    user = User(
        name="HQ User",
        login_id="hquser",
        password_hash="hashed",
        role=role,
        ui_type=ui_type,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    def override_get_db():
        local = TestingSessionLocal()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: user
    return TestClient(app), TestingSessionLocal


def _teardown_overrides():
    app.dependency_overrides = {}


def test_workers_diff_success_has_ingestion(tmp_path):
    client, _ = _setup_test_client(tmp_path)
    try:
        file_path = RAW_DIR / "employees_raw.xlsx"
        with file_path.open("rb") as fp:
            res = client.post(
                "/workers/diff/employees",
                files={"file": ("employees_raw.xlsx", fp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        assert res.status_code == 200
        data = res.json()
        assert "ingestion" in data
        assert data["ingestion"]["row_count"] > 0
        assert data["ingestion"]["header_valid"] is True
    finally:
        _teardown_overrides()


def test_workers_diff_failure_has_ingestion_failures(tmp_path):
    client, _ = _setup_test_client(tmp_path)
    try:
        corrupted = next(RAW_DIR.glob("*20260320152536*"))
        with corrupted.open("rb") as fp:
            res = client.post(
                "/workers/diff/employees",
                files={"file": (corrupted.name, fp, "application/vnd.ms-excel")},
            )
        assert res.status_code == 400
        data = res.json()
        assert "ingestion" in data
        assert len(data["ingestion"]["failures"]) > 0
        first = data["ingestion"]["failures"][0]
        assert "stage" in first and "parser" in first and "message" in first
    finally:
        _teardown_overrides()


def test_workers_diff_failure_masks_sensitive_details(tmp_path):
    client, _ = _setup_test_client(tmp_path)
    try:
        corrupted = next(RAW_DIR.glob("*20260320152536*"))
        with corrupted.open("rb") as fp:
            res = client.post(
                "/workers/diff/employees",
                files={"file": (corrupted.name, fp, "application/vnd.ms-excel")},
            )
        assert res.status_code == 400
        payload = json.dumps(res.json(), ensure_ascii=False)
        assert "Traceback" not in payload
        assert "File \"" not in payload
        assert "D:\\" not in payload
    finally:
        _teardown_overrides()


def test_workers_diff_header_fail_keeps_db_unchanged(tmp_path):
    client, Session = _setup_test_client(tmp_path)
    try:
        # 필수 컬럼이 없는 xlsx 생성
        bad = tmp_path / "bad_header.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["컬럼A", "컬럼B"])
        ws.append(["x", "y"])
        wb.save(bad)

        before = Session().query(Employment).count()
        with bad.open("rb") as fp:
            res = client.post(
                "/workers/diff/employees",
                files={"file": ("bad_header.xlsx", fp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        after = Session().query(Employment).count()

        assert res.status_code == 400
        data = res.json()
        assert data["ingestion"]["header_valid"] is False
        assert "헤더" in data["detail"]
        assert before == after
    finally:
        _teardown_overrides()


def _write_minimal_sawon_xlsx(path: Path) -> None:
    """사원리스트 그리드(_employee_row_to_dict)에 맞는 최소 xlsx."""
    wb = openpyxl.Workbook()
    ws = wb.active
    hdr = ["성   명", "입사일", "고용", "부서", "사원코드", "직위"] + [""] * 15
    assert len(hdr) == 21
    row: list[object] = ["테스트인원", None, None, "04", "99999", "대리", "900101", "2345678"]
    row.extend([None] * (21 - len(row)))
    row[13] = "KR"
    row[18] = "010"
    row[19] = "1111"
    row[20] = "2222"
    ws.append(hdr)
    ws.append(row)
    wb.save(path)


def test_import_sawon_list_success(tmp_path):
    client, _ = _setup_test_client(tmp_path)
    try:
        sawon_path = tmp_path / "sawon_test.xlsx"
        _write_minimal_sawon_xlsx(sawon_path)
        with sawon_path.open("rb") as fp:
            res = client.post(
                "/workers/import/sawon-list",
                files={
                    "file": (
                        "sawon_test.xlsx",
                        fp,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                },
            )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["total_rows"] >= 1
        assert "ingestion" in data
        assert data.get("source_type") == "sawon_list_upload"
    finally:
        _teardown_overrides()


def test_import_sawon_list_forbidden_for_site_role(tmp_path):
    client, _ = _setup_test_client(tmp_path, role="SITE", ui_type="SITE")
    try:
        dummy = tmp_path / "nope.xls"
        dummy.write_bytes(b"0")
        with dummy.open("rb") as fp:
            res = client.post(
                "/workers/import/sawon-list",
                files={"file": ("nope.xls", fp, "application/vnd.ms-excel")},
            )
        assert res.status_code == 403
    finally:
        _teardown_overrides()

