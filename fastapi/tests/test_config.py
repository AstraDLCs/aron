import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)


def test_jwt_secret_is_required():
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("secret", ["corto", "dev-secret-cambiar-en-produccion", "a" * 31])
def test_weak_jwt_secret_rejected(secret):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(jwt_secret=secret)


def test_strong_jwt_secret_accepted():
    assert Settings(jwt_secret="a" * 32).jwt_secret == "a" * 32


def test_registration_mode_is_restricted():
    with pytest.raises(ValidationError):
        Settings(jwt_secret="a" * 32, registration_mode="abierto")
