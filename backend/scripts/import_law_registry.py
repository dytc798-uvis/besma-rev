from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.modules.law_registry.service import (  # noqa: E402
    detect_source_file,
    import_records,
    load_records_from_json,
    load_records_from_postgres,
    load_records_from_sqlite,
    load_records_from_tsv_or_csv,
)


def resolve_source(
    *,
    source_project_root: Path,
    source_file: Path | None,
    source_sqlite_path: Path | None,
    source_db_url: str | None,
) -> tuple[list[dict], list[dict], str]:
    if source_db_url:
        article_records, revision_records = load_records_from_postgres(source_db_url)
        return article_records, revision_records, f"postgres:{source_db_url}"

    if source_sqlite_path:
        article_records, revision_records = load_records_from_sqlite(source_sqlite_path)
        return article_records, revision_records, str(source_sqlite_path)

    candidate_file = source_file or detect_source_file(source_project_root)
    if not candidate_file or not candidate_file.is_file():
        raise FileNotFoundError(
            f"입력 원본을 찾지 못했습니다. --source-file 또는 --source-db-url/--source-sqlite-path를 지정하세요. "
            f"(예시 project root: {source_project_root})"
        )

    suffix = candidate_file.suffix.lower()
    if suffix == ".json":
        article_records, revision_records = load_records_from_json(candidate_file)
    else:
        article_records, revision_records = load_records_from_tsv_or_csv(candidate_file)
    return article_records, revision_records, str(candidate_file)


def main() -> int:
    parser = argparse.ArgumentParser(description="BESMA 법규등록부 최소 import")
    parser.add_argument(
        "--source-project-root",
        type=Path,
        default=Path(r"D:\nas-fts"),
        help="원본 프로젝트 루트 경로 (기본값: D:\\nas-fts)",
    )
    parser.add_argument("--source-file", type=Path, default=None, help="원본 TSV/CSV/JSON 파일 경로")
    parser.add_argument("--source-sqlite-path", type=Path, default=None, help="원본 SQLite DB 경로")
    parser.add_argument("--source-db-url", type=str, default=None, help="원본 PostgreSQL DB URL")
    parser.add_argument("--dry-run", action="store_true", help="쓰기 없이 건수만 확인")
    args = parser.parse_args()

    article_records, revision_records, source_label = resolve_source(
        source_project_root=args.source_project_root,
        source_file=args.source_file,
        source_sqlite_path=args.source_sqlite_path,
        source_db_url=args.source_db_url,
    )
    print(f"[law-registry-import] source={source_label}")
    print(
        "[law-registry-import] article_records="
        f"{len(article_records)} revision_records={len(revision_records)}"
    )

    if args.dry_run:
        return 0

    db = SessionLocal()
    try:
        stats = import_records(
            db,
            article_records=article_records,
            revision_records=revision_records,
        )
        print(
            "[law-registry-import] done "
            f"masters(created={stats.law_masters_created}, updated={stats.law_masters_updated}) "
            f"articles(created={stats.article_items_created}, updated={stats.article_items_updated}) "
            f"revisions(created={stats.revision_histories_created}, updated={stats.revision_histories_updated})"
        )
    except Exception as exc:
        db.rollback()
        print(f"[law-registry-import] failed: {exc}")
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
