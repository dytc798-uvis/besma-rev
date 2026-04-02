from datetime import date

from pydantic import BaseModel, Field


class TbmMonthlySiteSummary(BaseModel):
    site_id: int
    site_name: str

    # 분모(생성 기준): 해당 월에 존재하는 DailyWorkPlan.work_date distinct 개수
    generated_days: int

    # 완료: 해당 일에 distribution_worker의 end_signed_at이 모든 worker에 대해 존재
    completed_days: int

    # 배포됨: 해당 일에 DailyWorkPlanDistribution 존재(하나 이상)
    distributed_days: int

    # 확인됨: 해당 일에 DailyWorkPlanConfirmation 존재(하나 이상)
    confirmed_days: int

    # 누락: 완료 기준을 만족하지 못한 날 (미배포 + 미서명 포함)
    missing_days: int

    completion_rate_pct: float


class TbmMonthlyMonitoringResponse(BaseModel):
    year: int
    month: int
    year_month: str
    start_date: date
    end_date: date

    sites: list[TbmMonthlySiteSummary] = Field(default_factory=list)


class TbmDailyWorkRow(BaseModel):
    work_date: date

    distributed: bool
    confirmed: bool
    confirmation_count: int
    distribution_count: int

    worker_total: int
    worker_completed: int

    completed: bool
    missing: bool


class TbmDailyMonitoringResponse(BaseModel):
    site_id: int
    site_name: str

    year: int
    month: int
    year_month: str

    start_date: date
    end_date: date

    summary: TbmMonthlySiteSummary
    days: list[TbmDailyWorkRow] = Field(default_factory=list)

