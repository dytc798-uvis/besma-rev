from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.datetime_utils import utc_now
from app.core.database import SessionLocal, init_db
from app.core.enums import Role, UIType
from app.modules.document_settings.models import (
    DocumentRequirement,
    DocumentTypeMaster,
    SubmissionCycle,
)
from app.modules.approvals.models import ApprovalHistory
from app.modules.document_generation.models import DocumentInstance
from app.modules.document_submissions.models import DocumentReviewHistory
from app.modules.documents.models import Document, DocumentUploadHistory
from app.modules.risk_library.models import (
    DailyWorkPlan,
    DailyWorkPlanDistribution,
    DailyWorkPlanDistributionWorker,
    DailyWorkPlanItem,
    DailyWorkPlanItemRiskRef,
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Employment, Person


# 우선 노출 데모 현장 (SITE002 파일럿/C18 → 1순위, SITE001 화성 기아 → 2순위). 서울/부산 데모 현장은 제거됨.
SITE_NAME_PRIORITY_1 = "[6.현대엔지니어링] AutoLand 화성 기아 LW 프로젝트 일반전기공사(도장)"
SITE_NAME_PRIORITY_2 = "[1.대우건설] 청라C18BL 오피스텔 신축공사"


def seed_sites(db: Session) -> None:
    coords = {
        "SITE001": (37.199, 126.825),  # 화성 인근
        "SITE002": (37.535, 126.632),  # 청라 인근
    }
    if db.query(Site).count() > 0:
        for s in db.query(Site).all():
            if s.site_code == "SITE001":
                s.site_name = SITE_NAME_PRIORITY_1
                s.client_name = "현대엔지니어링"
                s.contractor_name = None
                s.description = "AutoLand 화성 기아 LW 프로젝트 일반전기공사(도장)"
                s.manager_name = "박명식"
                lat, lng = coords["SITE001"]
                s.latitude = lat
                s.longitude = lng
                s.allowed_radius_m = 500
            elif s.site_code == "SITE002":
                s.site_name = SITE_NAME_PRIORITY_2
                s.client_name = None
                s.contractor_name = "대우건설"
                s.description = "청라 C18BL 오피스텔 신축공사"
                s.manager_name = "양규성"
                lat, lng = coords["SITE002"]
                s.latitude = lat
                s.longitude = lng
                s.allowed_radius_m = 500
            elif s.latitude is None and s.site_code in coords:
                lat, lng = coords[s.site_code]
                s.latitude = lat
                s.longitude = lng
                s.allowed_radius_m = 500
        db.commit()
        return

    sites = [
        Site(
            site_code="SITE001",
            site_name=SITE_NAME_PRIORITY_1,
            client_name="현대엔지니어링",
            contractor_name=None,
            start_date=date(2025, 1, 1),
            status="ACTIVE",
            manager_name="박명식",
            description="AutoLand 화성 기아 LW 프로젝트 일반전기공사(도장)",
            latitude=coords["SITE001"][0],
            longitude=coords["SITE001"][1],
            allowed_radius_m=500,
        ),
        Site(
            site_code="SITE002",
            site_name=SITE_NAME_PRIORITY_2,
            client_name=None,
            contractor_name="대우건설",
            start_date=date(2025, 3, 1),
            status="ACTIVE",
            manager_name="양규성",
            description="청라 C18BL 오피스텔 신축공사",
            latitude=coords["SITE002"][0],
            longitude=coords["SITE002"][1],
            allowed_radius_m=500,
        ),
    ]
    db.add_all(sites)
    db.commit()


def seed_users(db: Session) -> None:
    site1 = db.query(Site).filter(Site.site_code == "SITE001").first()
    site2 = db.query(Site).filter(Site.site_code == "SITE002").first()
    preferred_c18_site = (
        db.query(Site)
        .filter(
            (Site.site_name.contains("C18BL")) | (Site.site_name.contains("청라C18")),
            Site.address.isnot(None),
            Site.address != "",
        )
        .order_by(Site.id.asc())
        .first()
    )
    site2_for_assignment = preferred_c18_site or site2

    password_plain = "P@ssw0rd!"

    # 기존 DB를 재사용하는 경우에도 로그인 가능하도록 "샘플 계정은 upsert" 한다.
    # (MVP에서 마이그레이션 체계가 없기 때문에, 이전 해시 포맷이 남아 500이 나지 않도록 보정)
    # worker 로그인 데모 계정을 위해 person/employment를 보장한다.
    worker_person_1 = db.query(Person).filter(Person.phone_mobile == "01090000001").first()
    if worker_person_1 is None:
        worker_person_1 = Person(name="근로자1", phone_mobile="01090000001")
        db.add(worker_person_1)
        db.flush()
        db.add(
            Employment(
                person_id=worker_person_1.id,
                source_type="employee",
                employee_code="W001",
                site_code=site2_for_assignment.site_code if site2_for_assignment else None,
                is_active=True,
            )
        )

    worker_person_2 = db.query(Person).filter(Person.phone_mobile == "01090000002").first()
    if worker_person_2 is None:
        worker_person_2 = Person(name="근로자2", phone_mobile="01090000002")
        db.add(worker_person_2)
        db.flush()
        db.add(
            Employment(
                person_id=worker_person_2.id,
                source_type="employee",
                employee_code="W002",
                site_code=site1.site_code if site1 else None,
                is_active=True,
            )
        )

    desired = [
        dict(
            name="본사안전1",
            login_id="hqsafe1",
            department="안전보건실",
            role=Role.HQ_SAFE,  # 기본 role 유지 (관리자 분리는 다음 단계에서 정책 확정 후 적용 가능)
            ui_type=UIType.HQ_SAFE,
            site_id=None,
        ),
        dict(
            name="본사안전2",
            login_id="hqsafe2",
            department="안전보건실",
            role=Role.HQ_SAFE,
            ui_type=UIType.HQ_SAFE,
            site_id=None,
        ),
        dict(
            name="양규성",
            login_id="site01",
            department="현장",
            role=Role.SITE,
            ui_type=UIType.SITE,
            site_id=site2_for_assignment.id if site2_for_assignment else None,
        ),
        dict(
            name="박명식",
            login_id="site02",
            department="현장",
            role=Role.SITE,
            ui_type=UIType.SITE,
            site_id=site2_for_assignment.id if site2_for_assignment else None,
        ),
        dict(
            name="본사타부서1",
            login_id="hqother1",
            department="경영지원",
            role=Role.HQ_OTHER,
            ui_type=UIType.HQ_OTHER,
            site_id=None,
            person_id=None,
        ),
        dict(
            name=worker_person_1.name,
            login_id="worker01",
            department="현장근로",
            role=Role.WORKER,
            ui_type=UIType.SITE,
            site_id=site2_for_assignment.id if site2_for_assignment else None,
            person_id=worker_person_1.id,
        ),
        dict(
            name=worker_person_2.name,
            login_id="worker02",
            department="현장근로",
            role=Role.WORKER,
            ui_type=UIType.SITE,
            site_id=site1.id if site1 else None,
            person_id=worker_person_2.id,
        ),
    ]

    for u in desired:
        existing = db.query(User).filter(User.login_id == u["login_id"]).first()
        if existing:
            existing.name = u["name"]
            existing.department = u["department"]
            existing.role = u["role"]
            existing.ui_type = u["ui_type"]
            existing.site_id = u["site_id"]
            existing.person_id = u.get("person_id")
            existing.is_active = True
        else:
            db.add(
                User(
                    name=u["name"],
                    login_id=u["login_id"],
                    password_hash=get_password_hash(password_plain),
                    department=u["department"],
                    role=u["role"],
                    ui_type=u["ui_type"],
                    site_id=u["site_id"],
                    person_id=u.get("person_id"),
                    is_active=True,
                    must_change_password=True,
                )
            )
    db.commit()


def _seed_risk_keywords(db: Session) -> None:
    """Add keywords to all risk revisions that don't have any yet."""
    stopwords = {
        "작업",
        "공사",
        "구간",
        "주변",
        "시",
        "및",
        "의한",
        "사용",
        "후",
        "중",
        "점검",
        "확인",
        "필요",
    }
    revisions = db.query(RiskLibraryItemRevision).filter(RiskLibraryItemRevision.is_current.is_(True)).all()
    for rev in revisions:
        existing = db.query(RiskLibraryKeyword).filter(RiskLibraryKeyword.risk_revision_id == rev.id).count()
        if existing > 0:
            continue
        fields = " ".join(filter(None, [
            rev.work_category, rev.trade_type, rev.risk_factor, rev.risk_cause, rev.countermeasure,
        ])).lower()
        seen = set()
        tokens = []
        for token in fields.split():
            token = token.strip(".,·()（）/、")
            if len(token) < 2 or token in seen or token in stopwords:
                continue
            seen.add(token)
            tokens.append(token)
            weight = 2.0 if token in (rev.risk_factor or "").lower() else 1.0
            db.add(RiskLibraryKeyword(
                risk_revision_id=rev.id,
                keyword=token,
                weight=weight,
            ))
        for idx in range(len(tokens) - 1):
            left = tokens[idx]
            right = tokens[idx + 1]
            if right in {"배관", "배선", "설치", "검토"}:
                phrase = f"{left} {right}"
                if phrase in seen:
                    continue
                seen.add(phrase)
                weight = 2.5 if phrase in (rev.risk_factor or "").lower() else 1.5
                db.add(RiskLibraryKeyword(
                    risk_revision_id=rev.id,
                    keyword=phrase,
                    weight=weight,
                ))
    db.commit()


def _seed_default_pipe_risks(db: Session) -> None:
    # If source-of-truth Excel import already populated source metadata,
    # do not append fallback samples on startup.
    imported_rows_exist = (
        db.query(RiskLibraryItemRevision.id)
        .filter(
            RiskLibraryItemRevision.source_file.isnot(None),
            RiskLibraryItemRevision.source_row.isnot(None),
        )
        .first()
        is not None
    )
    if imported_rows_exist:
        _seed_risk_keywords(db)
        return

    default_pipe_rows = [
        {
            "work_category": "배관공사",
            "trade_type": "천장슬라브 배관",
            "risk_factor": "천장슬라브 배관 작업 중 낙하·전도",
            "risk_cause": "상부 자재 취급 및 작업발판 불안정",
            "countermeasure": "작업발판 점검, 자재 고정, 2인 1조 작업",
            "risk_f": 2,
            "risk_s": 4,
            "risk_r": 8,
        },
        {
            "work_category": "배관공사",
            "trade_type": "벽체 배관",
            "risk_factor": "벽체 배관 작업 중 협착·타격",
            "risk_cause": "배관 고정 및 절단 작업 중 손 끼임",
            "countermeasure": "절단 공구 점검, 보호구 착용, 협착 방지 자세 유지",
            "risk_f": 2,
            "risk_s": 4,
            "risk_r": 8,
        },
        {
            "work_category": "배관공사",
            "trade_type": "전선관 배관",
            "risk_factor": "전선관 배관 작업 중 비산물·베임",
            "risk_cause": "절단 및 가공 중 비산물 발생",
            "countermeasure": "보안경·장갑 착용, 절단 공구 덮개 확인",
            "risk_f": 2,
            "risk_s": 3,
            "risk_r": 6,
        },
    ]

    for row in default_pipe_rows:
        exists = (
            db.query(RiskLibraryItemRevision)
            .filter(
                RiskLibraryItemRevision.is_current.is_(True),
                RiskLibraryItemRevision.trade_type == row["trade_type"],
                RiskLibraryItemRevision.risk_factor == row["risk_factor"],
            )
            .first()
        )
        if exists is not None:
            continue

        item = RiskLibraryItem(source_scope="GLOBAL", is_active=True)
        db.add(item)
        db.flush()
        db.add(
            RiskLibraryItemRevision(
                item_id=item.id,
                revision_no=1,
                is_current=True,
                effective_from=date(2025, 1, 1),
                work_category=row["work_category"],
                trade_type=row["trade_type"],
                risk_factor=row["risk_factor"],
                risk_cause=row["risk_cause"],
                countermeasure=row["countermeasure"],
                risk_f=row["risk_f"],
                risk_s=row["risk_s"],
                risk_r=row["risk_r"],
            )
        )
        db.flush()

    db.commit()
    _seed_risk_keywords(db)


def seed_sample_daily_work_plan(db: Session) -> None:
    """Seed a complete daily work plan with items, risks, distribution, and worker assignment."""
    site = db.query(Site).filter(Site.site_code == "SITE002").first()
    if site is None:
        return

    author = db.query(User).filter(User.login_id == "site01").first()
    if author is None:
        return

    worker_user = db.query(User).filter(User.login_id == "worker01").first()
    if worker_user is None or worker_user.person_id is None:
        return

    today = date.today()

    existing_plan = (
        db.query(DailyWorkPlan)
        .filter(DailyWorkPlan.site_id == site.id, DailyWorkPlan.work_date == today)
        .first()
    )

    if existing_plan and db.query(DailyWorkPlanItem).filter(DailyWorkPlanItem.plan_id == existing_plan.id).count() > 0:
        return

    if existing_plan is None:
        existing_plan = DailyWorkPlan(
            site_id=site.id,
            work_date=today,
            author_user_id=author.id,
            status="DRAFT",
        )
        db.add(existing_plan)
        db.flush()

    plan = existing_plan

    risk_data = [
        {
            "work_category": "전기공사",
            "trade_type": "배선공사",
            "risk_factor": "충전부 접촉에 의한 감전",
            "risk_cause": "활선 작업 시 절연장갑 미착용",
            "countermeasure": "절연장갑, 절연화 착용 및 검전기로 활선 여부 확인 후 작업",
            "risk_f": 3, "risk_s": 4, "risk_r": 12,
        },
        {
            "work_category": "전기공사",
            "trade_type": "배선공사",
            "risk_factor": "전선 피복 손상에 의한 누전·화재",
            "risk_cause": "전선 포설 시 날카로운 부위 접촉",
            "countermeasure": "전선 보호관 사용, 피복 손상 여부 수시 점검",
            "risk_f": 2, "risk_s": 3, "risk_r": 6,
        },
        {
            "work_category": "전기공사",
            "trade_type": "배전반 설치",
            "risk_factor": "중량물 취급 시 협착·끼임",
            "risk_cause": "배전반 인양 중 로프 파단 또는 신호 미전달",
            "countermeasure": "2인 1조 작업, 인양 로프 사전 점검, 신호수 배치",
            "risk_f": 2, "risk_s": 4, "risk_r": 8,
        },
        {
            "work_category": "고소작업",
            "trade_type": "조명설치",
            "risk_factor": "사다리 전도에 의한 추락",
            "risk_cause": "사다리 고정 불량, 3점 지지 미준수",
            "countermeasure": "안전발판 사용, 전도방지 조치, 안전대 착용",
            "risk_f": 3, "risk_s": 5, "risk_r": 15,
        },
        {
            "work_category": "고소작업",
            "trade_type": "조명설치",
            "risk_factor": "공구·자재 낙하에 의한 타격",
            "risk_cause": "높은 곳에서 공구 미고정 상태로 작업",
            "countermeasure": "공구 안전줄 연결, 낙하물 방지망 설치, 안전모 착용",
            "risk_f": 2, "risk_s": 4, "risk_r": 8,
        },
    ]

    risk_revisions = []
    for rd in risk_data:
        item = RiskLibraryItem(source_scope="GLOBAL", is_active=True)
        db.add(item)
        db.flush()
        rev = RiskLibraryItemRevision(
            item_id=item.id,
            revision_no=1,
            is_current=True,
            effective_from=date(2025, 1, 1),
            work_category=rd["work_category"],
            trade_type=rd["trade_type"],
            risk_factor=rd["risk_factor"],
            risk_cause=rd["risk_cause"],
            countermeasure=rd["countermeasure"],
            risk_f=rd["risk_f"],
            risk_s=rd["risk_s"],
            risk_r=rd["risk_r"],
        )
        db.add(rev)
        db.flush()
        risk_revisions.append((item, rev))

    _seed_risk_keywords(db)

    item1 = DailyWorkPlanItem(
        plan_id=plan.id,
        work_name="배선공사",
        work_description="1층 사무실 전기배선 포설 및 결선 작업",
        team_label="전기A팀",
    )
    db.add(item1)
    db.flush()

    for idx in range(3):
        ri, rev = risk_revisions[idx]
        db.add(DailyWorkPlanItemRiskRef(
            plan_item_id=item1.id,
            risk_item_id=ri.id,
            risk_revision_id=rev.id,
            link_type="ADOPTED",
            is_selected=True,
            source_rule="KEYWORD_MATCH",
            score=0.9 - idx * 0.1,
            display_order=idx + 1,
        ))

    item2 = DailyWorkPlanItem(
        plan_id=plan.id,
        work_name="조명기구 설치",
        work_description="2층 복도 LED 조명기구 설치 (고소작업 포함)",
        team_label="전기B팀",
    )
    db.add(item2)
    db.flush()

    for idx in range(3, 5):
        ri, rev = risk_revisions[idx]
        db.add(DailyWorkPlanItemRiskRef(
            plan_item_id=item2.id,
            risk_item_id=ri.id,
            risk_revision_id=rev.id,
            link_type="ADOPTED",
            is_selected=True,
            source_rule="KEYWORD_MATCH",
            score=0.85 - (idx - 3) * 0.1,
            display_order=idx - 2,
        ))

    db.flush()

    existing_dist = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.plan_id == plan.id)
        .first()
    )
    if existing_dist is None:
        existing_dist = DailyWorkPlanDistribution(
            plan_id=plan.id,
            site_id=site.id,
            target_date=today,
            visible_from=utc_now() - timedelta(hours=1),
            distributed_by_user_id=author.id,
            distributed_at=utc_now(),
            status="VISIBLE",
        )
        db.add(existing_dist)
        db.flush()

    existing_dw = (
        db.query(DailyWorkPlanDistributionWorker)
        .filter(
            DailyWorkPlanDistributionWorker.distribution_id == existing_dist.id,
            DailyWorkPlanDistributionWorker.person_id == worker_user.person_id,
        )
        .first()
    )
    if existing_dw is None:
        import secrets
        db.add(DailyWorkPlanDistributionWorker(
            distribution_id=existing_dist.id,
            person_id=worker_user.person_id,
            access_token=secrets.token_urlsafe(16),
            ack_status="PENDING",
        ))

    db.commit()


def run_seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_sites(db)
        seed_users(db)
        seed_document_cycle_masters(db)
        seed_document_type_masters(db)
        seed_document_requirements(db)
        reset_demo_documents(db)
        _seed_default_pipe_risks(db)
        seed_sample_daily_work_plan(db)
    finally:
        db.close()


def seed_document_cycle_masters(db: Session) -> None:
    if db.query(SubmissionCycle).count() > 0:
        return

    cycles = [
        SubmissionCycle(code="DAILY", name="일간", sort_order=10, is_auto_generatable=True),
        SubmissionCycle(code="WEEKLY", name="주간", sort_order=20, is_auto_generatable=True),
        SubmissionCycle(code="MONTHLY", name="월간", sort_order=30, is_auto_generatable=True),
        SubmissionCycle(code="QUARTERLY", name="분기", sort_order=40, is_auto_generatable=True),
        SubmissionCycle(code="HALF_YEARLY", name="반기", sort_order=50, is_auto_generatable=True),
        SubmissionCycle(code="YEARLY", name="연간", sort_order=60, is_auto_generatable=True),
        SubmissionCycle(code="ADHOC", name="수시", sort_order=90, is_auto_generatable=False),
    ]
    db.add_all(cycles)
    db.commit()


def seed_document_type_masters(db: Session) -> None:
    adhoc = db.query(SubmissionCycle).filter(SubmissionCycle.code == "ADHOC").first()
    daily = db.query(SubmissionCycle).filter(SubmissionCycle.code == "DAILY").first()

    if not adhoc or not daily:
        return

    types = [
        DocumentTypeMaster(
            code="LEGAL_DOC",
            name="법정서류",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            generation_value=None,
            due_offset_days=None,
            is_required_default=False,
            sort_order=10,
        ),
        DocumentTypeMaster(
            code="DAILY_DOC",
            name="일상점검",
            default_cycle_id=daily.id,
            generation_rule="DAILY",
            generation_value=None,
            due_offset_days=0,
            is_required_default=True,
            sort_order=20,
        ),
        DocumentTypeMaster(
            code="INSPECTION",
            name="점검",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            generation_value=None,
            due_offset_days=None,
            is_required_default=False,
            sort_order=30,
        ),
        DocumentTypeMaster(
            code="OPINION_RELATED",
            name="의견 관련",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            generation_value=None,
            due_offset_days=None,
            is_required_default=False,
            sort_order=40,
        ),
        DocumentTypeMaster(
            code="BUDGET",
            name="예산",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            generation_value=None,
            due_offset_days=None,
            is_required_default=False,
            sort_order=50,
        ),
        DocumentTypeMaster(
            code="ACCIDENT",
            name="사고",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            generation_value=None,
            due_offset_days=None,
            is_required_default=False,
            sort_order=60,
        ),
        DocumentTypeMaster(
            code="ETC",
            name="기타",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            generation_value=None,
            due_offset_days=None,
            is_required_default=False,
            sort_order=70,
        ),
    ]

    for t in types:
        existing = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.code == t.code).first()
        if existing is None:
            db.add(t)
            continue

        existing.name = t.name
        existing.default_cycle_id = t.default_cycle_id
        existing.generation_rule = t.generation_rule
        existing.generation_value = t.generation_value
        existing.due_offset_days = t.due_offset_days
        existing.is_required_default = t.is_required_default
        existing.sort_order = t.sort_order
        existing.is_active = True

    db.commit()


def seed_document_requirements(db: Session) -> None:
    sites = db.query(Site).all()
    if not sites:
        return

    dt_by_code = {
        row.code: row
        for row in db.query(DocumentTypeMaster).all()
    }
    if not dt_by_code:
        return

    defs = [
        ("DAILY_TBM", "TBM", "DAILY", "당일 작업 시작 전 작성", "DAILY_DOC"),
        ("DAILY_RISK_ASSESSMENT", "일일위험성평가", "DAILY", "당일 작업 시작 전 작성", "DAILY_DOC"),
        ("DAILY_SAFETY_MEETING_LOG", "일일안전회의일지", "DAILY", "당일 안전회의 후 작성", "DAILY_DOC"),
        ("ADHOC_RISK_ASSESSMENT", "수시위험성평가", "ADHOC", "작업변경/위험요인 발생 시 작성", "INSPECTION"),
        ("AUTO_WORKER_OPINION_LOG", "근로자의견청취대장(자동생성)", "ROLLING", "의견 등록 시 자동 생성", "OPINION_RELATED"),
        ("SUPERVISOR_CHECKLIST", "관리감독자 점검표", "WEEKLY", "주 1회 점검 후 작성", "INSPECTION"),
        ("EMERGENCY_DRILL_REPORT", "비상사태훈련보고서", "ADHOC", "비상훈련 실시 후 작성", "ACCIDENT"),
        ("REGULAR_EDUCATION", "정기교육", "MONTHLY", "월 1회 교육 후 작성", "DAILY_DOC"),
        ("SPECIAL_EDUCATION", "특별교육", "ADHOC", "특별교육 실시 후 작성", "DAILY_DOC"),
        ("MSDS_EDUCATION", "MSDS교육", "MONTHLY", "월 1회 또는 물질변경 시 작성", "DAILY_DOC"),
        ("LEGAL_COMPLIANCE_EVALUATION", "법규준수이행평가", "MONTHLY", "월 1회 평가 후 작성", "INSPECTION"),
        ("NONCONFORMITY_ACTION_REPORT", "부적합 조치보고서", "ADHOC", "부적합 발생 시 조치 후 작성", "INSPECTION"),
    ]
    desired_codes = {code for code, _, _, _, _ in defs}

    for site in sites:
        # 시드 기준 목록에 없는 기존 요구사항은 정리한다.
        db.query(DocumentRequirement).filter(
            DocumentRequirement.site_id == site.id,
            ~DocumentRequirement.code.in_(desired_codes),
        ).delete(synchronize_session=False)

        for idx, (code, title, frequency, due_rule_text, doc_type_code) in enumerate(defs, start=1):
            dt = dt_by_code.get(doc_type_code)
            if dt is None:
                continue
            obj = (
                db.query(DocumentRequirement)
                .filter(
                    DocumentRequirement.site_id == site.id,
                    DocumentRequirement.code == code,
                )
                .first()
            )
            if obj is None:
                obj = DocumentRequirement(
                    site_id=site.id,
                    document_type_id=dt.id,
                    code=code,
                    title=title,
                    frequency=frequency,
                    is_required=True,
                    is_enabled=True,
                    display_order=idx,
                    due_rule_text=due_rule_text,
                    note=None,
                )
                db.add(obj)
                continue

            obj.document_type_id = dt.id
            obj.title = title
            obj.frequency = frequency
            obj.is_required = True
            obj.is_enabled = True
            obj.display_order = idx
            obj.due_rule_text = due_rule_text

    db.commit()


def reset_demo_documents(db: Session) -> None:
    """공개 시연용 기본 상태: 문서 업로드 전에는 전 현장이 0%에서 시작한다."""
    db.query(ApprovalHistory).delete(synchronize_session=False)
    db.query(DocumentReviewHistory).delete(synchronize_session=False)
    db.query(DocumentUploadHistory).delete(synchronize_session=False)
    db.query(Document).delete(synchronize_session=False)
    db.query(DocumentInstance).delete(synchronize_session=False)
    db.commit()


if __name__ == "__main__":
    run_seed()

