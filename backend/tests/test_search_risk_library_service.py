"""search_risk_library: 대량 적재 시에도 전량 .all() 하지 않도록 SQL 후보 제한."""

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.risk_library.models import RiskLibraryItem, RiskLibraryItemRevision, RiskLibraryKeyword
from app.modules.search.service import search_risk_library


def _setup_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _add_item(db, *, work_category: str, risk_factor: str, countermeasure: str, risk_r: int = 5):
    item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    db.add(item)
    db.flush()
    rev = RiskLibraryItemRevision(
        item_id=item.id,
        revision_no=1,
        is_current=True,
        effective_from=date.today(),
        effective_to=None,
        work_category=work_category,
        trade_type="테스트",
        process="미기재",
        risk_factor=risk_factor,
        risk_cause="미기재",
        countermeasure=countermeasure,
        risk_f=1,
        risk_s=1,
        risk_r=risk_r,
        revised_by_user_id=None,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    db.add(rev)
    db.flush()
    return rev


def test_search_risk_library_browse_uses_sql_pagination():
    db = _setup_db()
    for i in range(5):
        _add_item(db, work_category=f"wc{i}", risk_factor=f"rf{i}", countermeasure="cm")

    out = search_risk_library(db, query="", mode="quick", limit=2, offset=0)
    assert out["total"] == 5
    assert len(out["results"]) == 2
    assert out["results"][0]["score"] == 0.0

    out2 = search_risk_library(db, query="", mode="quick", limit=2, offset=2)
    assert len(out2["results"]) == 2
    assert out2["results"][0]["risk_revision_id"] != out["results"][0]["risk_revision_id"]


def test_search_risk_library_browse_deduplicates_before_count_and_pagination():
    db = _setup_db()
    first = _add_item(
        db,
        work_category="고소작업",
        risk_factor="사다리 전도에 의한 추락",
        countermeasure="안전발판 사용, 전도방지 조치, 안전대 착용",
        risk_r=15,
    )
    _add_item(
        db,
        work_category="고소작업",
        risk_factor="사다리 전도에 의한 추락",
        countermeasure="안전발판 사용, 전도방지 조치, 안전대 착용",
        risk_r=15,
    )
    _add_item(db, work_category="전기작업", risk_factor="감전", countermeasure="절연보호구", risk_r=8)
    db.commit()

    out = search_risk_library(db, query="", mode="quick", limit=1, offset=0)
    assert out["total"] == 2
    assert len(out["results"]) == 1
    assert out["results"][0]["risk_revision_id"] == first.id

    out2 = search_risk_library(db, query="", mode="quick", limit=1, offset=1)
    assert out2["total"] == 2
    assert len(out2["results"]) == 1
    assert out2["results"][0]["risk_revision_id"] != first.id


def test_search_risk_library_token_prefilter_and_score():
    db = _setup_db()
    rev_a = _add_item(db, work_category="배관공사", risk_factor="감전 위험", countermeasure="절연", risk_r=9)
    _add_item(db, work_category="토목", risk_factor="낙하", countermeasure="안전모", risk_r=3)
    db.add(RiskLibraryKeyword(risk_revision_id=rev_a.id, keyword="감전", weight=1.0))
    db.commit()

    out = search_risk_library(db, query="감전", mode="quick", limit=10, offset=0)
    assert out["total"] >= 1
    assert any(r["risk_revision_id"] == rev_a.id for r in out["results"])
    assert out["results"][0]["matched_tokens"]

