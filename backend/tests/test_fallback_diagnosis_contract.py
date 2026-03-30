from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import sqlite3

from scripts.diagnose_document_instances_fallback_candidates import candidate_reasons


def test_candidate_rules_positive_cycle_null_and_single_day():
    cols = {"cycle_code", "period_start", "period_end", "status_reason"}
    row = {
        "cycle_code": None,
        "period_start": "2026-03-17",
        "period_end": "2026-03-17",
        "status_reason": "MASTER_DEFAULT",
    }
    rs = candidate_reasons(row, cols)
    assert "cycle_code_is_null" in rs
    assert "period_is_single_day" in rs


def test_candidate_rules_negative_not_strong_enough():
    cols = {"cycle_code", "period_start", "period_end", "status_reason"}
    row = {
        "cycle_code": "DAILY",
        "period_start": "2026-03-17",
        "period_end": "2026-03-17",
        "status_reason": "MASTER_DEFAULT",
    }
    rs = candidate_reasons(row, cols)
    assert rs == []


def test_cli_exit_code_3_when_candidates_exist(tmp_path: Path):
    db = tmp_path / "diag.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            """
            CREATE TABLE document_instances (
              id INTEGER PRIMARY KEY,
              site_id INTEGER,
              document_type_code TEXT,
              period_start TEXT,
              period_end TEXT,
              status TEXT,
              status_reason TEXT,
              cycle_code TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO document_instances
              (site_id, document_type_code, period_start, period_end, status, status_reason, cycle_code)
            VALUES
              (1, 'X', '2026-03-17', '2026-03-17', 'SKIPPED', 'MASTER_DEFAULT', NULL)
            """
        )
        conn.commit()
    finally:
        conn.close()

    report_dir = tmp_path / "reports"
    p = subprocess.run(
        [
            sys.executable,
            "scripts/diagnose_document_instances_fallback_candidates.py",
            "--db-path",
            str(db),
            "--report-dir",
            str(report_dir),
            "--limit",
            "1",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert p.returncode == 3


def test_cli_exit_code_0_when_no_candidates(tmp_path: Path):
    db = tmp_path / "diag.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            """
            CREATE TABLE document_instances (
              id INTEGER PRIMARY KEY,
              site_id INTEGER,
              document_type_code TEXT,
              period_start TEXT,
              period_end TEXT,
              status TEXT,
              status_reason TEXT,
              cycle_code TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO document_instances
              (site_id, document_type_code, period_start, period_end, status, status_reason, cycle_code)
            VALUES
              (1, 'X', '2026-03-17', '2026-03-18', 'SKIPPED', 'MASTER_DEFAULT', 'DAILY')
            """
        )
        conn.commit()
    finally:
        conn.close()

    report_dir = tmp_path / "reports"
    p = subprocess.run(
        [
            sys.executable,
            "scripts/diagnose_document_instances_fallback_candidates.py",
            "--db-path",
            str(db),
            "--report-dir",
            str(report_dir),
            "--limit",
            "1",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0

