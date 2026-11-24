from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.people import Candidate, CvFile
from app.models.user import User
from app.services.app_settings import get_app_settings
from tests.fixtures.cvs import create_position, create_source, make_cv_pdf, upload_cv


def _populate(client, h):
    pos = create_position(client, h, "Operador de Planta")
    src = create_source(client, h, "Portal Minero Perú")
    r = upload_cv(client, h, make_cv_pdf("Juan Carlos Quispe Mamani", "45678912", "j@correo.pe", "987654321"),
                  "cv.pdf", pos["id"], src["id"])
    assert r.status_code == 201, r.text


def _wipe(client, h, confirm="BORRAR", reload_demo=False):
    return client.post("/api/datacenter/wipe", json={"confirm": confirm, "reloadDemo": reload_demo}, headers=h)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_wipe_deletes_business_data_and_files_but_keeps_users_audit_settings(client, db, make_user, rrhh_root):
    _, h = make_user()
    make_user("otro@mina.pe", "Otro Usuario")
    _populate(client, h)
    get_app_settings(db).company_name = "Minera de Prueba"
    db.flush()
    assert any(p.is_file() for p in rrhh_root.rglob("*"))

    r = _wipe(client, h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deletedFiles"] == 1
    assert body["counts"]["candidates"] == 1 and body["counts"]["positions"] == 1
    assert body["state"]["candidates"] == [] and body["state"]["positions"] == [] and body["state"]["jobBoards"] == []
    assert _count(db, Candidate) == 0 and _count(db, CvFile) == 0
    assert not any(p.is_file() for p in rrhh_root.rglob("*"))
    assert rrhh_root.is_dir()
    assert _count(db, User) == 2
    assert get_app_settings(db).company_name == "Minera de Prueba"
    last = db.scalars(select(AuditLog).order_by(AuditLog.id.desc())).first()
    assert last.action == "datacenter.wipe" and last.user_name == "Ana Torres"
    assert _count(db, AuditLog) > 1  # la bitácora anterior sigue ahí


def test_wipe_can_reload_demo(client, db, make_user, rrhh_root):
    _, h = make_user()
    _populate(client, h)
    r = _wipe(client, h, reload_demo=True)
    assert r.status_code == 200, r.text
    s = r.json()["state"]
    assert len(s["positions"]) == 28 and len(s["jobNeeds"]) == 15 and s["candidates"] == []


def test_wipe_requires_typed_confirmation(client, db, make_user, rrhh_root):
    _, h = make_user()
    _populate(client, h)
    r = _wipe(client, h, confirm="borrar")
    assert r.status_code == 422
    assert _count(db, Candidate) == 1


def test_wipe_can_be_disabled_per_server(client, db, make_user, rrhh_root, settings_override):
    _, h = make_user()
    _populate(client, h)
    with settings_override(allow_wipe=False):
        r = _wipe(client, h)
    assert r.status_code == 403
    assert _count(db, Candidate) == 1


def test_wipe_requires_session(client, rrhh_root):
    assert _wipe(client, {}).status_code == 401
