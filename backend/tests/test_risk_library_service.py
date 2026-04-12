from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.risk_library.models import (
    DailyWorkPlan,
    DailyWorkPlanItem,
    DailyWorkPlanItemRiskRef,
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)
from app.modules.risk_library.service import (
    adopt_risks_for_plan_item_by_revision_ids,
    hq_finalize_risk_ref,
    list_risk_refs_for_plan_item,
    recommend_risks_for_work_item,
    site_approve_risk_ref,
)
from app.modules.sites.models import Site
from app.modules.users.models import User


def _setup_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # FK 대상 테이블 등록
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.risk_library import models as risk_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _add_revision(
    db,
    *,
    work_category: str,
    trade_type: str,
    risk_factor: str,
    risk_cause: str = "미기재",
    countermeasure: str = "기본대책",
    keywords: list[tuple[str, float]] | None = None,
):
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
        trade_type=trade_type,
        risk_factor=risk_factor,
        risk_cause=risk_cause,
        countermeasure=countermeasure,
        risk_f=3,
        risk_s=4,
        risk_r=12,
        revised_by_user_id=None,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    db.add(rev)
    db.flush()
    for keyword, weight in keywords or []:
        db.add(RiskLibraryKeyword(risk_revision_id=rev.id, keyword=keyword, weight=weight))
    db.commit()
    return rev


def test_recommend_risks_for_work_item_keyword_match():
    db = _setup_db()

    item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    db.add(item)
    db.flush()
    rev = RiskLibraryItemRevision(
        item_id=item.id,
        revision_no=1,
        is_current=True,
        effective_from=date.today(),
        effective_to=None,
        work_category="철근",
        trade_type="트레이",
        risk_factor="사다리 작업 중 추락",
        risk_cause="발판 불안정",
        countermeasure="2인1조/발판고정",
        risk_f=3,
        risk_s=4,
        risk_r=12,
        revised_by_user_id=None,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    db.add(rev)
    db.flush()
    db.add(RiskLibraryKeyword(risk_revision_id=rev.id, keyword="트레이", weight=1.5))
    db.add(RiskLibraryKeyword(risk_revision_id=rev.id, keyword="추락", weight=2.0))
    db.commit()

    result = recommend_risks_for_work_item(
        db,
        work_name="트레이 설치",
        work_description="추락 방지 점검 필요",
        top_n=5,
    )

    assert result
    assert result[0]["risk_revision_id"] == rev.id
    assert result[0]["score"] >= 3.5
    assert any(hit["keyword"] == "트레이" for hit in result[0]["matched_keywords"])


def test_recommend_risks_suppresses_office_work_physical_overrecommendation():
    db = _setup_db()

    _add_revision(
        db,
        work_category="전기공사",
        trade_type="배선공사",
        risk_factor="충전부 접촉에 의한 감전",
        keywords=[("작업", 1.0)],
    )
    _add_revision(
        db,
        work_category="설치공사",
        trade_type="중량물 설치",
        risk_factor="중량물 취급 시 협착·끼임",
        keywords=[("작업", 1.0)],
    )
    _add_revision(
        db,
        work_category="고소작업",
        trade_type="조명설치",
        risk_factor="공구·자재 낙하에 의한 타격",
        keywords=[("작업", 1.0)],
    )

    result = recommend_risks_for_work_item(
        db,
        work_name="도면 및 서류 검토 작업",
        work_description="도면 및 서류 검토 작업",
        top_n=5,
    )

    assert result == []


def test_recommend_risks_falls_back_for_pipe_work_without_keywords():
    db = _setup_db()

    _add_revision(
        db,
        work_category="배관공사",
        trade_type="천장슬라브 배관",
        risk_factor="천장슬라브 배관 작업 중 낙하·전도",
        keywords=[],
    )
    _add_revision(
        db,
        work_category="배관공사",
        trade_type="벽체 배관",
        risk_factor="벽체 배관 작업 중 협착·타격",
        keywords=[],
    )

    cases = [
        "헬스케어센터 지하3층 천장슬라브 배관",
        "7002동 지상1층 벽체 배관",
        "7010동 및 주변 지하5층 천장슬라브 배관",
    ]

    for text in cases:
        result = recommend_risks_for_work_item(
            db,
            work_name=text,
            work_description=text,
            top_n=5,
        )
        assert result
        assert any(
            ("배관" in (row["risk_factor"] or "")) or ("배관" in (row["trade_type"] or ""))
            for row in result
        )


def test_adopt_risks_dedupes_identical_hazard_and_countermeasure():
    db = _setup_db()

    site = Site(site_code="S-RISK-1", site_name="risk dedupe site")
    user = User(
        id=1,
        name="u",
        login_id="u1",
        password_hash="x",
        site_id=None,
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        must_change_password=False,
    )
    db.add_all([site, user])
    db.flush()

    plan = DailyWorkPlan(site_id=site.id, work_date=date.today(), author_user_id=user.id)
    db.add(plan)
    db.flush()
    item = DailyWorkPlanItem(plan_id=plan.id, work_name="테스트 작업", work_description="dedupe")
    db.add(item)
    db.flush()

    def make_revision(risk_factor: str, countermeasure: str) -> RiskLibraryItemRevision:
        ri = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
        db.add(ri)
        db.flush()
        rev = RiskLibraryItemRevision(
            item_id=ri.id,
            revision_no=1,
            is_current=True,
            effective_from=date.today(),
            effective_to=None,
            work_category="테스트",
            trade_type="테스트",
            risk_factor=risk_factor,
            risk_cause="미기재",
            countermeasure=countermeasure,
            risk_f=1,
            risk_s=1,
            risk_r=1,
            revised_by_user_id=None,
            revised_at=datetime.utcnow(),
            revision_note=None,
        )
        db.add(rev)
        db.flush()
        return rev

    rev_a = make_revision("동일위험", "동일대책")
    rev_b = make_revision("동일위험", "동일대책")

    adopt_risks_for_plan_item_by_revision_ids(db, plan_item_id=item.id, risk_revision_ids=[rev_a.id])
    adopt_risks_for_plan_item_by_revision_ids(db, plan_item_id=item.id, risk_revision_ids=[rev_b.id])

    refs = db.query(DailyWorkPlanItemRiskRef).filter(DailyWorkPlanItemRiskRef.plan_item_id == item.id).all()
    assert len(refs) == 1
    assert refs[0].risk_revision_id == rev_a.id
    assert refs[0].is_selected is True


def test_risk_ref_requires_site_then_hq_approval_for_final_reflection():
    db = _setup_db()

    site = Site(site_code="S-RISK-2", site_name="risk approval site")
    site_user = User(
        id=1,
        name="site-user",
        login_id="site_u1",
        password_hash="x",
        site_id=site.id,
        role=Role.SITE,
        ui_type=UIType.SITE,
        must_change_password=False,
    )
    hq_user = User(
        id=2,
        name="hq-user",
        login_id="hq_u1",
        password_hash="x",
        site_id=None,
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        must_change_password=False,
    )
    db.add(site)
    db.flush()
    site_user.site_id = site.id
    db.add_all([site_user, hq_user])
    db.flush()

    plan = DailyWorkPlan(site_id=site.id, work_date=date.today(), author_user_id=site_user.id)
    db.add(plan)
    db.flush()
    item = DailyWorkPlanItem(plan_id=plan.id, work_name="승인 테스트", work_description="approval flow")
    db.add(item)
    db.flush()

    rev = _add_revision(
        db,
        work_category="테스트",
        trade_type="테스트",
        risk_factor="추락",
        countermeasure="안전난간 설치",
    )

    adopt_risks_for_plan_item_by_revision_ids(db, plan_item_id=item.id, risk_revision_ids=[rev.id])
    rows = list_risk_refs_for_plan_item(db, plan_item_id=item.id)
    assert len(rows) == 1
    assert rows[0]["site_approved"] is False
    assert rows[0]["hq_final_approved"] is False
    assert rows[0]["is_reflected_to_final_db"] is False

    ref_id = rows[0]["id"]

    try:
        hq_finalize_risk_ref(db, ref_id=ref_id, approved_by_user_id=hq_user.id)
        assert False, "HQ final approval should require prior SITE approval"
    except ValueError as exc:
        assert str(exc) == "site_approval_required"

    site_row = site_approve_risk_ref(db, ref_id=ref_id, approved_by_user_id=site_user.id)
    assert site_row["site_approved"] is True
    assert site_row["hq_final_approved"] is False
    assert site_row["is_reflected_to_final_db"] is False

    hq_row = hq_finalize_risk_ref(db, ref_id=ref_id, approved_by_user_id=hq_user.id)
    assert hq_row["site_approved"] is True
    assert hq_row["hq_final_approved"] is True
    assert hq_row["is_reflected_to_final_db"] is True

