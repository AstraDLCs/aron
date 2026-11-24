from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg://pulso:pulso@db:5432/pulso"
    test_database_url: str = ""

    jwt_secret: str = "dev-secret-cambiar-en-produccion"
    jwt_expire_hours: int = 12

    registration_mode: str = "open"
    invite_code: str = ""

    cors_origins: list[str] = [
        "http://tauri.localhost",
        "tauri://localhost",
        "http://localhost:1420",
    ]

    rrhh_root: Path = Path("/data/rrhh")

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    worker_rate_per_minute: int = 15
    server_scan_interval_s: int = 300

    company_name_default: str = "Compañía Minera Las Bravas"


@lru_cache
def get_settings() -> Settings:
    return Settings()
