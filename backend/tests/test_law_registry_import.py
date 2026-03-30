from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.law_registry.models import LawArticleItem, LawMaster
from app.modules.law_registry.service import import_records, load_records_from_tsv_or_csv


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_import_records_from_tsv_is_idempotent(tmp_path: Path):
    source_file = tmp_path / "law_registry.tsv"
    source_file.write_text(
        "\n".join(
            [
                "순번\t법규명\t관련조항\t주요내용\t해당부서\t실행내용\t대응대책\t벌칙 및 과태료",
                "1\t산업안전보건법\t제5조\t안전조치 요약\t안전보건팀\t점검 실시\t교육 강화\t벌금",
                "2\t산업안전보건법\t제10조\t교육 요약\t교육팀\t교육 시행\t교육일지 보관\t과태료",
            ]
        ),
        encoding="utf-8",
    )

    article_records, revision_records = load_records_from_tsv_or_csv(source_file)
    db = _setup_db()

    first = import_records(db, article_records=article_records, revision_records=revision_records)
    second = import_records(db, article_records=article_records, revision_records=revision_records)

    assert first.law_masters_created == 1
    assert first.article_items_created == 2
    assert second.law_masters_created == 0
    assert second.article_items_created == 0
    assert db.query(LawMaster).count() == 1
    assert db.query(LawArticleItem).count() == 2
