from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

ALGORITHM = "HS256"
_hasher = PasswordHash.recommended()


class InvalidToken(Exception):
    """El token falta, está mal firmado, vencido o no tiene el formato esperado."""


def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, h: str) -> bool:
    return _hasher.verify(pw, h)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(hours=settings.jwt_expire_hours)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise InvalidToken("sub inválido")
    return sub
