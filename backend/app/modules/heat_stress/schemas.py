from datetime import datetime

from pydantic import BaseModel, Field, field_validator


ACTION_CODES = {
    "WATER",
    "SHADE_COOLING",
    "VENTILATION",
    "REST",
    "WORK_TIME_ADJUSTMENT",
    "COOLING_GEAR",
    "WORK_STOP",
    "HEALTH_MONITORING",
    "NOT_IMPLEMENTED",
    "OTHER",
}


class HeatStressCreate(BaseModel):
    measured_at: datetime
    work_location: str = Field(min_length=1, max_length=200)
    work_process: str | None = Field(default=None, max_length=200)
    measurement_source: str
    air_temperature_c: float = Field(ge=-20, le=60)
    relative_humidity_pct: float = Field(ge=0, le=100)
    actual_actions: list[str] = Field(default_factory=list, max_length=12)
    action_notes: str | None = Field(default=None, max_length=2000)
    recorder_signature_data: str

    @field_validator("measurement_source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"ON_SITE", "KMA_REFERENCE"}:
            raise ValueError("measurement_source must be ON_SITE or KMA_REFERENCE")
        return value

    @field_validator("actual_actions")
    @classmethod
    def validate_actions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(v.strip().upper() for v in values if v.strip()))
        invalid = set(normalized) - ACTION_CODES
        if invalid:
            raise ValueError(f"invalid action codes: {', '.join(sorted(invalid))}")
        return normalized


class HeatStressConfirm(BaseModel):
    confirmer_name: str = Field(min_length=1, max_length=100)
    confirmer_title: str = Field(min_length=1, max_length=100)
    confirmer_signature_data: str
