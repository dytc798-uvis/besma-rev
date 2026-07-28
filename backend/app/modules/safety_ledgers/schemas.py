from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class VehicleLogReview(BaseModel):
    driven_on: date
    driver_name: str = Field(min_length=1, max_length=80)
    odometer_km: int | None = Field(default=None, ge=0, le=9_999_999)
    trip_km: float | None = Field(default=None, ge=0, le=100_000)
    use_type: str = Field(default="6.업무용(왕복)", max_length=50)
    purpose: str | None = Field(default=None, max_length=500)
    confirm: bool = False

    @field_validator("driver_name", "use_type")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()


class CardExpenseReview(BaseModel):
    used_at: datetime | None = None
    site_name: str | None = Field(default=None, max_length=200)
    merchant: str | None = Field(default=None, max_length=200)
    amount: int | None = Field(default=None, ge=0, le=1_000_000_000)
    description: str | None = Field(default=None, max_length=500)
    card_last4: str | None = None
    note: str | None = Field(default=None, max_length=500)
    confirm: bool = False

    @field_validator("card_last4")
    @classmethod
    def normalize_last4(cls, value: str | None) -> str | None:
        digits = "".join(ch for ch in (value or "") if ch.isdigit())
        if not digits:
            return None
        if len(digits) != 4:
            raise ValueError("카드번호는 마지막 4자리만 입력해 주세요.")
        return digits


class CardAccountUpdate(BaseModel):
    card_number: str = Field(min_length=4, max_length=30)

    @field_validator("card_number")
    @classmethod
    def normalize_card_number(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) not in {4, 16}:
            raise ValueError("카드번호 16자리 또는 마지막 4자리를 입력해 주세요.")
        return digits


class VehicleDriversUpdate(BaseModel):
    driver_names: list[str] = Field(min_length=1, max_length=4)

    @field_validator("driver_names")
    @classmethod
    def normalize_driver_names(cls, values: list[str]) -> list[str]:
        names = [value.strip() for value in values if value.strip()]
        if len(names) < 1 or len(names) > 4:
            raise ValueError("운전자는 1명 이상 4명 이하로 입력해 주세요.")
        if len(names) != len(set(names)):
            raise ValueError("같은 운전자를 중복 등록할 수 없습니다.")
        return names
