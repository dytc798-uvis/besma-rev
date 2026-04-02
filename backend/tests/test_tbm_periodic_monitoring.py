from datetime import date, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.documents.routes import router as documents_router
from app.modules.risk_library.models import (
    DailyWorkPlan,
    DailyWorkPlanConfirmation,
    DailyWorkPlanDistribution,
    DailyWorkPlanDistributionWorker,
)
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Employment, Person


def test_tbm_periodic_monitoring_monthly_and_daily(tmp_path):
    db_file = tmp_path / "test_tbm_periodic_monitoring.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 테이블 등록
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.risk_library import models as risk_library_models  # noqa: F401
    from app.modules.users import models as users_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    site = Site(site_code="S-TBM-001", site_name="TBM 모니터링 테스트 현장")
    db.add(site)
    db.flush()
    site_id = site.id

    hq_user = User(
        id=1,
        name="hq-safe",
        login_id="hq_safe_monitor",
        password_hash="x",
        site_id=site_id,
        role=Role.HQ_SAFE,
    )
    db.add(hq_user)
    hq_user_id = hq_user.id

    # distribution_worker -> person FK 만족을 위해 Person / Employment 최소 구성
    person1 = Person(name="worker-1", phone_mobile="01011112222")
    person2 = Person(name="worker-2", phone_mobile="01033334444")
    db.add_all([person1, person2])
    db.flush()

    # employment_id는 nullable이지만, FK/스키마 일관성을 위해 생성
    employment1 = Employment(
        person_id=person1.id,
        source_type="employee",
        site_code=site.site_code,
        is_active=True,
        hire_date=date(2026, 3, 1),
        termination_date=None,
    )
    employment2 = Employment(
        person_id=person2.id,
        source_type="employee",
        site_code=site.site_code,
        is_active=True,
        hire_date=date(2026, 3, 1),
        termination_date=None,
    )
    db.add_all([employment1, employment2])
    db.flush()

    # 월 대상: 2026-04 (2개 work_date)
    plan_day1 = DailyWorkPlan(
        site_id=site_id,
        work_date=date(2026, 4, 1),
        author_user_id=hq_user.id,
        status="DRAFT",
    )
    plan_day2 = DailyWorkPlan(
        site_id=site_id,
        work_date=date(2026, 4, 2),
        author_user_id=hq_user.id,
        status="DRAFT",
    )
    db.add_all([plan_day1, plan_day2])
    db.flush()

    now = datetime.utcnow()

    dist_day1 = DailyWorkPlanDistribution(
        plan_id=plan_day1.id,
        site_id=site_id,
        target_date=date(2026, 4, 1),
        visible_from=now,
        distributed_by_user_id=hq_user.id,
        distributed_at=now,
    )
    dist_day2 = DailyWorkPlanDistribution(
        plan_id=plan_day2.id,
        site_id=site_id,
        target_date=date(2026, 4, 2),
        visible_from=now,
        distributed_by_user_id=hq_user.id,
        distributed_at=now,
    )
    db.add_all([dist_day1, dist_day2])
    db.flush()

    # Day1: 2명 모두 end_signed_at 존재 => 완료
    w1_day1 = DailyWorkPlanDistributionWorker(
        distribution_id=dist_day1.id,
        person_id=person1.id,
        employment_id=employment1.id,
        access_token="token-day1-1",
        ack_status="COMPLETED",
        end_signed_at=now,
    )
    w2_day1 = DailyWorkPlanDistributionWorker(
        distribution_id=dist_day1.id,
        person_id=person2.id,
        employment_id=employment2.id,
        access_token="token-day1-2",
        ack_status="COMPLETED",
        end_signed_at=now,
    )

    # Day2: 한 명 end_signed_at 누락 => 미완료/누락
    w1_day2 = DailyWorkPlanDistributionWorker(
        distribution_id=dist_day2.id,
        person_id=person1.id,
        employment_id=employment1.id,
        access_token="token-day2-1",
        ack_status="START_SIGNED",
        end_signed_at=None,
    )
    w2_day2 = DailyWorkPlanDistributionWorker(
        distribution_id=dist_day2.id,
        person_id=person2.id,
        employment_id=employment2.id,
        access_token="token-day2-2",
        ack_status="COMPLETED",
        end_signed_at=now,
    )
    db.add_all([w1_day1, w2_day1, w1_day2, w2_day2])

    # Day1: 확인됨(confirmation 존재), Day2: 확인 없음
    conf_day1 = DailyWorkPlanConfirmation(
        plan_id=plan_day1.id,
        confirmed_by_user_id=hq_user.id,
        confirmed_at=now,
    )
    db.add(conf_day1)

    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(documents_router)

    def override_get_db():
        local_db = TestingSessionLocal()
        try:
            yield local_db
        finally:
            local_db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=hq_user_id,
        role=Role.HQ_SAFE,
        site_id=site_id,
    )

    client = TestClient(app)

    month_res = client.get(
        "/documents/periodic-monitoring/tbm/monthly",
        params={"year_month": "2026-04", "site_id": site_id},
    )
    assert month_res.status_code == 200
    month_json = month_res.json()
    assert month_json["year_month"] == "2026-04"
    assert len(month_json["sites"]) == 1

    s = month_json["sites"][0]
    assert s["generated_days"] == 2
    assert s["completed_days"] == 1
    assert s["distributed_days"] == 2
    assert s["confirmed_days"] == 1
    assert s["missing_days"] == 1
    assert s["completion_rate_pct"] == 50.0

    daily_res = client.get(
        "/documents/periodic-monitoring/tbm/daily",
        params={"year_month": "2026-04", "site_id": site_id},
    )
    assert daily_res.status_code == 200
    daily_json = daily_res.json()
    assert daily_json["site_id"] == site_id
    assert daily_json["summary"]["generated_days"] == 2
    assert len(daily_json["days"]) == 2

    day1 = daily_json["days"][0]
    assert day1["work_date"] == "2026-04-01"
    assert day1["distributed"] is True
    assert day1["confirmed"] is True
    assert day1["completed"] is True
    assert day1["missing"] is False

    day2 = daily_json["days"][1]
    assert day2["work_date"] == "2026-04-02"
    assert day2["distributed"] is True
    assert day2["confirmed"] is False
    assert day2["completed"] is False
    assert day2["missing"] is True

