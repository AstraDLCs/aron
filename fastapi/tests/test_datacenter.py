from sqlalchemy import func, select

from app import seed
from app.models.audit import AuditLog
from app.models.people import Candidate, CvFile
from app.models.user import User
from tests.fixtures.cvs import create_position, create_source, make_cv_pdf, upload_cv


def _populate(client, h):
    pos = create_position(client, h, "Operador de Planta")
    src = create_source(client, h, "Portal Minero Perú")
    r = upload_cv(client, h, make_cv_pdf("Juan Carlos Quispe Mamani", "45678912", "j@correo.pe", "987654321"),
                  "cv.pdf", pos["id"], src["id"])
    assert r.status_code == 201, r.text
    return r.json()["result"]["candidateId"]


def _counts(db):
    return {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in (Candidate, CvFile)}


def _restore(client, h, backup, confirm="RESTAURAR"):
    return client.post("/api/datacenter/restore", json={"confirm": confirm, "backup": backup}, headers=h)


def test_backup_restore_roundtrip(client, db, make_user, rrhh_root):
    _, h = make_user()
    _populate(client, h)
    seed_counts = _counts(db)
    state_before = client.get("/api/state", headers=h).json()
    r = client.get("/api/datacenter/backup", headers=h)
    assert r.status_code == 200
    assert "Respaldo_Pulso_Laboral_" in r.headers["content-disposition"]
    backup = r.json()
    assert backup["version"] == 1 and "users" not in backup["data"] and "audit_log" not in backup["data"]
    assert len(backup["data"]["candidates"]) == 1 and len(backup["data"]["cvFiles"]) == 1
    # el respaldo se restaura sobre una base distinta
    rr = _restore(client, h, backup)
    assert rr.status_code == 200, rr.text
    assert rr.json()["counts"]["candidates"] == 1 and rr.json()["missingFiles"] == []
    assert _counts(db) == seed_counts
    after = client.get("/api/state", headers=h).json()
    assert [c["id"] for c in after["candidates"]] == [c["id"] for c in state_before["candidates"]]
    assert len(after["positions"]) == len(state_before["positions"])
    status = client.get("/api/datacenter/status", headers=h).json()
    assert status["candidatesCount"] == 1 and status["mode"] == "PostgreSQL" and status["totalRecords"] > 0


def test_restore_replaces_existing_data(client, db, make_user, rrhh_root):
    _, h = make_user()
    backup = client.get("/api/datacenter/backup", headers=h).json()  # vacío
    _populate(client, h)
    assert _restore(client, h, backup).status_code == 200
    assert client.get("/api/state", headers=h).json()["candidates"] == []
    assert client.get("/api/state", headers=h).json()["positions"] == []


def test_restore_demo_backup(client, db, make_user, rrhh_root):
    _, h = make_user()
    seed.main(["--demo"], db=db)
    backup = client.get("/api/datacenter/backup", headers=h).json()
    assert _restore(client, h, backup).status_code == 200
    s = client.get("/api/state", headers=h).json()
    assert len(s["positions"]) == 28 and len(s["jobNeeds"]) == 15


def test_restore_never_touches_users_or_audit(client, db, make_user, rrhh_root):
    _, h = make_user()
    make_user("otro@mina.pe", "Otro Usuario")
    _populate(client, h)
    users = db.scalar(select(func.count()).select_from(User))
    audit_before = db.scalar(select(func.count()).select_from(AuditLog))
    backup = client.get("/api/datacenter/backup", headers=h).json()
    assert _restore(client, h, backup).status_code == 200
    assert db.scalar(select(func.count()).select_from(User)) == users
    assert db.scalar(select(func.count()).select_from(AuditLog)) > audit_before
    log = db.scalar(select(AuditLog).where(AuditLog.action == "datacenter.restore"))
    assert log.details["counts"]["candidates"] == 1


def test_restore_marks_missing_files(client, db, make_user, rrhh_root):
    _, h = make_user()
    _populate(client, h)
    backup = client.get("/api/datacenter/backup", headers=h).json()
    for f in rrhh_root.rglob("*.pdf"):
        f.unlink()
    r = _restore(client, h, backup)
    assert r.status_code == 200
    assert len(r.json()["missingFiles"]) == 1
    cand = r.json()["state"]["candidates"][0]
    assert cand["cvMissing"] is True


def test_restore_requires_confirm(client, db, make_user, rrhh_root):
    _, h = make_user()
    _populate(client, h)
    backup = client.get("/api/datacenter/backup", headers=h).json()
    r = _restore(client, h, backup, confirm="restaurar")
    assert r.status_code == 422 and "Escribe RESTAURAR para confirmar" in r.text
    assert _restore(client, h, {"version": 2, "data": {}}).status_code == 422
    assert db.scalar(select(func.count()).select_from(Candidate)) == 1
