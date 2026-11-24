from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-secret-cambiar-en-produccion"

# Modelos gratuitos (`:free`) de OpenRouter con instrucciones, contexto >= 32k y salida JSON; elegidos el
# 2026-11-24 con `GET https://openrouter.ai/api/v1/models`. Se usan mientras la configuración no fije otros.
DEFAULT_AI_MODEL = "google/gemma-4-31b-it:free"
DEFAULT_AI_FALLBACK_MODELS = ["google/gemma-4-26b-a4b-it:free", "inclusionai/ling-3.2-flash:free"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg://pulso:pulso@db:5432/pulso"
    test_database_url: str = ""

    jwt_secret: str  # obligatorio: sin valor por defecto
    jwt_expire_hours: int = 12

    registration_mode: Literal["open", "invite"] = "open"
    invite_code: str = ""

    cors_origins: list[str] = [
        "http://tauri.localhost",
        "tauri://localhost",
        "http://localhost:1420",
    ]

    rrhh_root: Path = Path("/data/rrhh")
    # Instaladores que ofrece la página pública "/" (se usa el .msi de versión más alta).
    downloads_dir: Path = Path(__file__).resolve().parent.parent / "downloads"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    worker_rate_per_minute: int = 15
    server_scan_interval_s: int = 300

    company_name_default: str = "Compañía Minera Las Bravas"

    # Borrado total desde la app (Ctrl+Alt+B). Pensado para la versión de prueba: poner en false en producción.
    allow_wipe: bool = True

    @field_validator("jwt_secret")
    @classmethod
    def _check_jwt_secret(cls, v: str) -> str:
        if v == _DEV_SECRET or len(v) < 32:
            raise ValueError(
                "JWT_SECRET debe tener al menos 32 caracteres y no puede ser el valor de ejemplo. "
                'Genere uno con: python -c "import secrets;print(secrets.token_urlsafe(48))"'
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
