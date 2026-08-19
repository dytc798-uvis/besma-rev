"""search_risk_library: 대량 적재 시에도 전량 .all() 하지 않도록 SQL 후보 제한."""

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.risk_library.models import (
    RiskLibraryContractor,
    RiskLibraryItem,
    RiskLibraryItemContractor,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)
from app.modules.search.service import convert_risk_score, search_risk_library
from app.modules.risk_library.service import list_risk_library_entries


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


def _add_item(
    db,
    *,
    work_category: str,
    risk_factor: str,
    countermeasure: str,
    risk_r: int = 5,
    risk_f: int = 1,
    risk_s: int = 1,
    is_common: bool = True,
):
    item = RiskLibraryItem(
        source_scope="HQ_STANDARD",
        owner_site_id=None,
        is_common=is_common,
        is_active=True,
    )
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
        risk_f=risk_f,
        risk_s=risk_s,
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


def test_search_risk_library_scopes_items_and_converts_contractor_method():
    db = _setup_db()
    common_revision = _add_item(
        db,
        work_category="공통작업",
        risk_factor="공통 위험",
        countermeasure="공통 대책",
        is_common=True,
    )
    daewoo = RiskLibraryContractor(
        contractor_key="대우건설",
        contractor_name="대우건설",
        evaluation_method="도급사 4×3",
        is_active=True,
    )
    lotte = RiskLibraryContractor(
        contractor_key="롯데건설",
        contractor_name="롯데건설",
        evaluation_method="회사 4×5",
        is_active=True,
    )
    db.add_all([daewoo, lotte])
    db.flush()
    daewoo_revision = _add_item(
        db,
        work_category="대우작업",
        risk_factor="대우 위험",
        countermeasure="대우 대책",
        risk_r=20,
        risk_f=4,
        risk_s=5,
        is_common=False,
    )
    lotte_revision = _add_item(
        db,
        work_category="롯데작업",
        risk_factor="롯데 위험",
        countermeasure="롯데 대책",
        is_common=False,
    )
    db.add_all(
        [
            RiskLibraryItemContractor(
                risk_item_id=daewoo_revision.item_id,
                contractor_id=daewoo.id,
            ),
            RiskLibraryItemContractor(
                risk_item_id=lotte_revision.item_id,
                contractor_id=lotte.id,
            ),
        ]
    )
    db.commit()

    out = search_risk_library(
        db,
        query="",
        mode="quick",
        contractor_name="(주) 대우건설",
        limit=20,
    )
    result_ids = {row["risk_item_id"] for row in out["results"]}
    assert daewoo_revision.item_id in result_ids
    assert lotte_revision.item_id not in result_ids
    assert out["total"] == 2
    assert out["evaluation_method"] == "도급사 4×3"
    converted = next(row for row in out["results"] if row["risk_item_id"] == daewoo_revision.item_id)
    assert (converted["display_f"], converted["display_s"], converted["display_r"]) == (4, 3, 12)
    assert converted["risk_grade"] == "기준확인"

    plain_library = list_risk_library_entries(
        db,
        contractor_name="(주) 대우건설",
        limit=20,
    )
    plain_item_ids = {row["risk_item_id"] for row in plain_library["items"]}
    assert daewoo_revision.item_id in plain_item_ids
    assert lotte_revision.item_id not in plain_item_ids

    unassigned_site = search_risk_library(
        db,
        query="",
        mode="quick",
        contractor_scope_required=True,
        limit=20,
    )
    assert {row["risk_item_id"] for row in unassigned_site["results"]} == {
        common_revision.item_id
    }

    unassigned_plain_library = list_risk_library_entries(
        db,
        contractor_scope_required=True,
        limit=20,
    )
    assert {
        row["risk_item_id"] for row in unassigned_plain_library["items"]
    } == {common_revision.item_id}


def test_company_risk_levels_follow_btms_procedure_six_bands():
    cases = [
        ((1, 3), "무시"),
        ((2, 2), "미미"),
        ((2, 4), "경미"),
        ((3, 3), "상당"),
        ((3, 5), "중대"),
        ((4, 4), "허용불가"),
    ]
    for (frequency, severity), expected in cases:
        converted = convert_risk_score(
            frequency,
            severity,
            evaluation_method="회사 4×5",
        )
        assert converted["risk_grade"] == expected

