from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CoupangDocumentUpsert(BaseModel):
    title: str = Field(default="쿠팡 일일 작업계획", min_length=1, max_length=160)
    work_date: date
    floor: str = Field(default="4F", max_length=40)
    workplace: str = Field(default="", max_length=200)
    work_description: str = Field(default="", max_length=2000)
    hazard: str = Field(default="안전고리 미체결로 인한 추락 위험", max_length=1000)
    control: str = Field(default="적정 안전고리 체결 및 관리감독자 확인", max_length=1000)
    contractor_name: str = Field(default="부현전기", max_length=100)
    manager_name: str = Field(default="", max_length=100)
    worker_count: int = Field(default=0, ge=0, le=9999)
    notes: str = Field(default="", max_length=4000)
    drawing: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "title",
        "floor",
        "workplace",
        "work_description",
        "hazard",
        "control",
        "contractor_name",
        "manager_name",
        "notes",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

