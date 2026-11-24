import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.config import get_settings
from app.db import get_db
from app.deps import CurrentUser, client_ip
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash válido de una contraseña cualquiera: se verifica contra él cuando el email no existe
# para que el tiempo de respuesta no delate qué cuentas existen.
_DUMMY_HASH = hash_password("contraseña-inexistente")

DbDep = Annotated[Session, Depends(get_db)]


def _token_out(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/register", status_code=201, response_model=TokenOut, response_model_by_alias=True)
def register(body: RegisterIn, request: Request, db: DbDep):
    settings = get_settings()
    if settings.registration_mode == "invite":
        expected = settings.invite_code
        given = body.invite_code or ""
        if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
            raise HTTPException(status_code=403, detail="Código de invitación inválido")
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
    user = User(
        full_name=body.full_name.strip(),
        email=body.email,
        password_hash=hash_password(body.password),
        job_title=body.job_title.strip(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # carrera entre dos registros con el mismo email
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email") from None
    log_action(
        db, actor=user, action="auth.register", entity_type="user", entity_id=user.id,
        summary=f"Se registró la cuenta de {user.full_name} ({user.email})", ip=client_ip(request),
    )
    db.commit()
    return _token_out(user)


@router.post("/login", response_model=TokenOut, response_model_by_alias=True)
def login(body: LoginIn, request: Request, db: DbDep):
    user = db.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not user.is_active or not password_ok:
        log_action(
            db, actor=user if user is not None else "", action="auth.login_failed", entity_type="user",
            entity_id=user.id if user is not None else None,
            summary=f"Ingreso fallido para {body.email}", ip=client_ip(request),
        )
        db.commit()  # la bitácora se guarda aunque la respuesta sea un error
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    user.last_login_at = datetime.now(UTC)
    log_action(
        db, actor=user, action="auth.login", entity_type="user", entity_id=user.id,
        summary=f"{user.full_name} ingresó al sistema", ip=client_ip(request),
    )
    db.commit()
    return _token_out(user)


@router.get("/me", response_model=UserOut, response_model_by_alias=True)
def me(user: CurrentUser):
    return user
