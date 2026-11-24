from typing import Annotated

from pydantic import AfterValidator, Field

from app.schemas.common import CamelModel


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    local, sep, domain = value.partition("@")
    if not sep or not local or "." not in domain or " " in value or "@" in domain:
        raise ValueError("Email inválido")
    return value


Email = Annotated[str, Field(max_length=320), AfterValidator(_normalize_email)]


class UserOut(CamelModel):
    id: str
    full_name: str
    email: str
    job_title: str
    is_active: bool


class RegisterIn(CamelModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: Email
    password: str = Field(min_length=8, max_length=128)
    job_title: str = Field(default="", max_length=200)
    invite_code: str | None = None


class LoginIn(CamelModel):
    email: Email
    password: str = Field(max_length=128)


class TokenOut(CamelModel):
    access_token: str
    user: UserOut
