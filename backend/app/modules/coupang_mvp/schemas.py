from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CoupangWorkItem(BaseModel):
    floor: str = Field(default="", max_length=40)
    workplace: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=500)
    people: int = Field(default=0, ge=0, le=9999)


class CoupangDocumentUpsert(BaseModel):
    target_site_id: int = Field(default=101, ge=1)
    title: str = Field(default="쿠팡 일일 작업계획", min_length=1, max_length=160)
    work_date: date
    progress_rate: float = Field(default=0, ge=0, le=100)
    start_time: str = Field(default="07:00", max_length=10)
    end_time: str = Field(default="17:00", max_length=10)
    floor: str = Field(default="4F", max_length=40)
    workplace: str = Field(default="", max_length=200)
    work_description: str = Field(default="", max_length=2000)
    hazard: str = Field(default="안전고리 미체결로 인한 추락 위험", max_length=1000)
    control: str = Field(default="적정 안전고리 체결 및 관리감독자 확인", max_length=1000)
    contractor_name: str = Field(default="부현전기", max_length=100)
    manager_name: str = Field(default="", max_length=100)
    worker_count: int = Field(default=0, ge=0, le=9999)
    total_count: int = Field(default=0, ge=0, le=9999)
    manager_count: int = Field(default=0, ge=0, le=9999)
    signal_count: int = Field(default=0, ge=0, le=9999)
    fire_watch_count: int = Field(default=0, ge=0, le=9999)
    extra_time: str = Field(default="", max_length=40)
    extra_people: int = Field(default=0, ge=0, le=9999)
    extra_work: str = Field(default="", max_length=500)
    forklift_used: int = Field(default=0, ge=0, le=999)
    forklift_owned: int = Field(default=0, ge=0, le=999)
    lift_used: int = Field(default=0, ge=0, le=999)
    lift_owned: int = Field(default=0, ge=0, le=999)
    overtime: str = Field(default="무", max_length=20)
    fire_work: str = Field(default="무", max_length=20)
    contacts: str = Field(default="", max_length=2000)
    foreign_worker_count: int = Field(default=0, ge=0, le=9999)
    raw_plan_text: str = Field(default="", max_length=15000)
    today_jobs: list[CoupangWorkItem] = Field(default_factory=list, max_length=10)
    notes: str = Field(default="", max_length=4000)
    drawing: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "title",
        "start_time",
        "end_time",
        "floor",
        "workplace",
        "work_description",
        "hazard",
        "control",
        "contractor_name",
        "manager_name",
        "extra_time",
        "extra_work",
        "overtime",
        "fire_work",
        "contacts",
        "raw_plan_text",
        "notes",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class CoupangWorkbookExportRequest(BaseModel):
    drawing_png: str | None = Field(default=None, max_length=16_500_000)
