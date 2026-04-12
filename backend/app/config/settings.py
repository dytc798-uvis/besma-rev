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
    backend_port: int = 8000

    sqlite_path: Path = BASE_DIR / "database" / "besma.db"

    jwt_secret_key: str = Field("change-me-in-.env", env="BESMA_JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    storage_root: Path = BASE_DIR / "storage"
    documents_dir_name: str = "documents"
    images_dir_name: str = "images"
    document_explorer_base_dir: Path = BASE_DIR / "docs" / "base"
    upload_max_part_size_bytes: int = Field(default=30 * 1024 * 1024, validation_alias="BESMA_UPLOAD_MAX_PART_SIZE_BYTES")
    document_upload_max_bytes: int = Field(default=10 * 1024 * 1024, validation_alias="BESMA_DOCUMENT_UPLOAD_MAX_BYTES")
    weather_cache_ttl_minutes: int = Field(default=20, validation_alias="BESMA_WEATHER_CACHE_TTL_MINUTES")
    weather_http_timeout_seconds: float = Field(default=5.0, validation_alias="BESMA_WEATHER_HTTP_TIMEOUT_SECONDS")
    weather_hq_name: str | None = Field(default=None, validation_alias="BESMA_HQ_WEATHER_NAME")
    weather_hq_lat: float | None = Field(default=None, validation_alias="BESMA_HQ_WEATHER_LAT")
    weather_hq_lon: float | None = Field(default=None, validation_alias="BESMA_HQ_WEATHER_LON")
    weather_hq_site_limit: int = Field(default=5, validation_alias="BESMA_HQ_WEATHER_SITE_LIMIT")

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
