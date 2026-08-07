from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "BESMA Local MVP"
    env: Literal["local", "dev", "prod"] = "local"
    test_persona_mode: bool = Field(default=False, validation_alias="BESMA_TEST_PERSONA_MODE")
    test_gps_radius_m: int = Field(default=5, validation_alias="BESMA_TEST_GPS_RADIUS_M")

    backend_host: str = "127.0.0.1"
    backend_port: int = 8001

    sqlite_path: Path = BASE_DIR / "database" / "besma.db"

    jwt_secret_key: str = Field("change-me-in-.env", env="BESMA_JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    # 모바일 촬영 업무는 매번 재로그인하지 않도록 기본 세션을 7일 유지한다.
    access_token_expire_minutes: int = Field(
        default=60 * 24 * 7,
        validation_alias="BESMA_ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    storage_root: Path = BASE_DIR / "storage"
    safety_ledger_nas_root: Path | None = Field(
        default=None,
        validation_alias="BESMA_SAFETY_LEDGER_NAS_ROOT",
    )
    safety_ledger_card_template_path: Path | None = Field(
        default=None,
        validation_alias="BESMA_SAFETY_LEDGER_CARD_TEMPLATE_PATH",
    )
    safety_ledger_jo_card_template_path: Path | None = Field(
        default=None,
        validation_alias="BESMA_SAFETY_LEDGER_JO_CARD_TEMPLATE_PATH",
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    safety_ledger_vision_model: str = Field(
        default="gpt-5.6-terra",
        validation_alias="BESMA_SAFETY_LEDGER_VISION_MODEL",
    )
    safety_ledger_vision_timeout_seconds: float = Field(
        default=45.0,
        validation_alias="BESMA_SAFETY_LEDGER_VISION_TIMEOUT_SECONDS",
    )
    accident_nas_root: Path | None = Field(default=None, validation_alias="BESMA_ACCIDENT_NAS_ROOT")
    documents_dir_name: str = "documents"
    images_dir_name: str = "images"
    document_explorer_base_dir: Path = BASE_DIR / "docs" / "base"
    upload_max_part_size_bytes: int = Field(default=30 * 1024 * 1024, validation_alias="BESMA_UPLOAD_MAX_PART_SIZE_BYTES")
    document_upload_max_bytes: int = Field(default=10 * 1024 * 1024, validation_alias="BESMA_DOCUMENT_UPLOAD_MAX_BYTES")
    document_upload_reject_max_bytes: int = Field(
        default=20 * 1024 * 1024,
        validation_alias="BESMA_DOCUMENT_UPLOAD_REJECT_MAX_BYTES",
    )

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://192.168.219.51:5174",
        "http://118.36.137.127:5174",
        "https://besma.co.kr",
        "https://www.besma.co.kr",
    ]
    cors_origin_regex: str = r"(^https?://192\.168\.\d+\.\d+:5174$)|(^https://.*\.vercel\.app$)"

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
