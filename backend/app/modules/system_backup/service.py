from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import settings

logger = logging.getLogger(__name__)

SKIP_DIR_NAMES = frozenset(
    {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        ".vercel",
        ".git",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        ".cursor",
    }
)

REPO_INCLUDE_TOP_LEVEL = (
    "backend",
    "frontend",
    "deploy",
    "scripts",
    "docs",
    "database",
    "storage",
)

ROOT_FILES = (
    ".env",
    ".env.example",
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    ".python-version",
)

RESTORE_README = """# BESMA 전체 백업 복원 안내

이 아카이브는 DB·업로드 파일·서버 소스를 한 번에 옮기기 위한 백업입니다.

## 포함 항목
- `database/besma.db` — SQLite 일관 스냅샷
- `storage/` — 문서·이미지 등 업로드 파일
- `backend/`, `frontend/`, `deploy/`, `scripts/`, `docs/` — 저장소 소스(venv/node_modules 제외)
- `.env` — 있으면 루트에 포함
- `accident_nas/` — NAS 경로가 설정된 경우

## 새 서버 복원 (요약)
1. Ubuntu 등에 Python 3.12+, Node 20+ 설치
2. 이 ZIP을 `/home/ubuntu/besma-rev` 등에 풀기
3. `backend/.venv` 생성 후 `pip install -r requirements.txt`
4. `cd backend && alembic upgrade head`
5. `systemctl` 또는 `uvicorn`으로 API 기동 (기존 unit 파일 참고)
6. 프론트는 Vercel 또는 `frontend` 빌드 후 정적 호스팅
7. `.env`의 `BESMA_JWT_SECRET_KEY`, DB 경로, storage 경로 확인

자세한 배포: `deploy/` 폴더 스크립트 참고.
"""


@dataclass
class BackupBuildResult:
    zip_path: Path
    manifest: dict
    file_count: int = 0
    skipped_paths: list[str] = field(default_factory=list)


def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES


def _sqlite_backup(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    src_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(dest.as_posix())
        try:
            src_conn.backup(dst_conn)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _add_file(zf: zipfile.ZipFile, path: Path, arcname: str, manifest_files: list[dict]) -> None:
    zf.write(path, arcname=arcname)
    try:
        stat = path.stat()
        manifest_files.append(
            {
                "path": arcname.replace("\\", "/"),
                "size": stat.st_size,
            }
        )
    except OSError:
        manifest_files.append({"path": arcname.replace("\\", "/"), "size": None})


def _add_tree(
    zf: zipfile.ZipFile,
    root: Path,
    *,
    arc_prefix: str,
    manifest_files: list[dict],
    skipped: list[str],
) -> None:
    if not root.is_dir():
        skipped.append(str(root))
        return
    prefix = arc_prefix.rstrip("/")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        base = Path(dirpath)
        for fname in filenames:
            if fname.endswith((".pyc", ".pyo")):
                continue
            full = base / fname
            if not full.is_file():
                continue
            rel = full.relative_to(root).as_posix()
            arcname = f"{prefix}/{rel}" if prefix else rel
            try:
                _add_file(zf, full, arcname, manifest_files)
            except OSError as exc:
                logger.warning("backup skip file %s: %s", full, exc)
                skipped.append(str(full))


def build_full_backup_zip(*, created_by_login_id: str) -> BackupBuildResult:
    repo_root = settings.sqlite_path.resolve().parent.parent
    manifest_files: list[dict] = []
    skipped: list[str] = []
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    tmp = tempfile.NamedTemporaryFile(prefix="besma-full-backup-", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # DB — 일관 스냅샷
            db_src = settings.sqlite_path.resolve()
            if db_src.is_file():
                with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_tmp:
                    db_tmp_path = Path(db_tmp.name)
                try:
                    _sqlite_backup(db_src, db_tmp_path)
                    _add_file(zf, db_tmp_path, "database/besma.db", manifest_files)
                finally:
                    db_tmp_path.unlink(missing_ok=True)
            else:
                skipped.append(str(db_src))

            # database 폴더 내 기타(마이그레이션 메모 등) — besma.db 제외 중복 방지
            db_dir = repo_root / "database"
            if db_dir.is_dir():
                for item in db_dir.iterdir():
                    if item.name == "besma.db":
                        continue
                    if item.is_file():
                        _add_file(zf, item, f"database/{item.name}", manifest_files)

            # storage
            storage = settings.storage_root.resolve()
            _add_tree(zf, storage, arc_prefix="storage", manifest_files=manifest_files, skipped=skipped)

            # 소스·배포 스크립트
            for name in REPO_INCLUDE_TOP_LEVEL:
                if name in {"database", "storage"}:
                    continue
                _add_tree(zf, repo_root / name, arc_prefix=name, manifest_files=manifest_files, skipped=skipped)

            for fname in ROOT_FILES:
                fpath = repo_root / fname
                if fpath.is_file():
                    _add_file(zf, fpath, fname, manifest_files)

            if settings.accident_nas_root:
                nas = Path(settings.accident_nas_root).expanduser().resolve()
                _add_tree(zf, nas, arc_prefix="accident_nas", manifest_files=manifest_files, skipped=skipped)

            zf.writestr("RESTORE.md", RESTORE_README)

            manifest = {
                "kind": "besma_full_backup",
                "version": 1,
                "created_at": created_at,
                "created_by_login_id": created_by_login_id,
                "repo_root": str(repo_root),
                "components": list(REPO_INCLUDE_TOP_LEVEL)
                + [f for f in ROOT_FILES if (repo_root / f).is_file()]
                + (["accident_nas"] if settings.accident_nas_root else []),
                "file_count": len(manifest_files),
                "skipped_paths": skipped[:200],
                "files_sample": manifest_files[:50],
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        manifest["zip_bytes"] = tmp_path.stat().st_size
        return BackupBuildResult(
            zip_path=tmp_path,
            manifest=manifest,
            file_count=len(manifest_files),
            skipped_paths=skipped,
        )
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
