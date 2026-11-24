from sqlalchemy import select

from app.cli import main
from app.models.audit import AuditLog
from app.models.user import User

REGISTER = {"fullName": "Ana Torres", "email": "Ana@Mina.pe", "password": "clave-segura-1", "jobTitle": "Jefe de RR.HH."}


def _actions(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def test_register_returns_token_and_logs(client, db):
    r = client.post("/api/auth/register", json=REGISTER)
    assert r.status_code == 201
    body = r.json()
    assert body["accessToken"]
    assert body["user"]["email"] == "ana@mina.pe"
    assert body["user"]["fullName"] == "Ana Torres"
    assert body["user"]["isActive"] is True
    assert "passwordHash" not in body["user"]
    logs = _actions(db, "auth.register")
    assert len(logs) == 1
    assert logs[0].user_id == body["user"]["id"]
    assert logs[0].user_name == "Ana Torres"
    assert logs[0].entity_type == "user"
    # el token recién emitido sirve
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['accessToken']}"})
    assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]


def test_register_duplicate_email_case_insensitive(client):
    assert client.post("/api/auth/register", json=REGISTER).status_code == 201
    r = client.post("/api/auth/register", json={**REGISTER, "email": "ana@mina.pe"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Ya existe una cuenta con ese email"


def test_login_ok_and_failed_logged(client, db, make_user):
    make_user("ana@mina.pe", password="clave-segura-1")
    bad = client.post("/api/auth/login", json={"email": "ana@mina.pe", "password": "incorrecta-123"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Email o contraseña incorrectos"
    assert len(_actions(db, "auth.login_failed")) == 1

    unknown = client.post("/api/auth/login", json={"email": "nadie@mina.pe", "password": "incorrecta-123"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "Email o contraseña incorrectos"

    ok = client.post("/api/auth/login", json={"email": "ANA@MINA.PE", "password": "clave-segura-1"})
    assert ok.status_code == 200
    assert ok.json()["accessToken"]
    assert len(_actions(db, "auth.login")) == 1
    assert db.scalar(select(User.last_login_at).where(User.email == "ana@mina.pe")) is not None


def test_login_inactive_account_rejected(client, db, make_user):
    user, _ = make_user()
    user.is_active = False
    db.flush()
    r = client.post("/api/auth/login", json={"email": "ana@mina.pe", "password": "clave-segura-1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Email o contraseña incorrectos"


def test_password_min_length(client):
    r = client.post("/api/auth/register", json={**REGISTER, "password": "1234567"})
    assert r.status_code == 422


def test_invite_mode(client, settings_override):
    with settings_override(registration_mode="invite", invite_code="X1"):
        r = client.post("/api/auth/register", json=REGISTER)
        assert r.status_code == 403
        assert r.json()["detail"] == "Código de invitación inválido"
        r = client.post("/api/auth/register", json={**REGISTER, "inviteCode": "mal"})
        assert r.status_code == 403
        r = client.post("/api/auth/register", json={**REGISTER, "inviteCode": "X1"})
        assert r.status_code == 201


def test_invite_mode_without_configured_code_rejects_everyone(client, settings_override):
    with settings_override(registration_mode="invite", invite_code=""):
        r = client.post("/api/auth/register", json={**REGISTER, "inviteCode": ""})
        assert r.status_code == 403


def test_protected_requires_token(client, db, make_user):
    assert client.get("/api/users").status_code == 401
    assert client.get("/api/users", headers={"Authorization": "Bearer basura"}).status_code == 401
    user, headers = make_user()
    ok = client.get("/api/users", headers=headers)
    assert ok.status_code == 200
    assert [u["email"] for u in ok.json()] == ["ana@mina.pe"]
    user.is_active = False
    db.flush()
    r = client.get("/api/users", headers=headers)
    assert r.status_code == 401
    assert r.json()["detail"] == "Sesión inválida o vencida"


def test_expired_token_rejected(client, make_user, settings_override):
    with settings_override(jwt_expire_hours=-1):
        _, headers = make_user()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_cli_deactivate_and_activate(db, make_user):
    user, _ = make_user()
    assert main(["users", "deactivate", "Ana@Mina.pe"], db=db) == 0
    db.refresh(user)
    assert user.is_active is False
    logs = _actions(db, "user.deactivate")
    assert len(logs) == 1 and logs[0].user_name == "Sistema" and logs[0].user_id is None
    assert main(["users", "activate", "ana@mina.pe"], db=db) == 0
    db.refresh(user)
    assert user.is_active is True
    assert len(_actions(db, "user.activate")) == 1


def test_cli_unknown_email_returns_error(db, capsys):
    assert main(["users", "deactivate", "nadie@mina.pe"], db=db) == 1
    assert "nadie@mina.pe" in capsys.readouterr().err
