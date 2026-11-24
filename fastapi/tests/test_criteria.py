from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.people import Candidate
from tests.fixtures.cvs import (
    candidate_in,
    create_position,
    create_source,
    make_cv_pdf,
    upload_cv,
)

CRITERION_KEYS = {
    "id", "title", "appliesToDepartment", "weightLabel", "ruleText", "isCorrection", "wrongAiAssumption",
    "learnedFromCandidate", "createdBy", "createdAt", "updatedAt",
}
JUAN = dict(full_name="Juan Carlos Quispe Mamani", dni="45678912", email="juan.quispe@correo.pe", phone="987654321")
ROSA = dict(full_name="Rosa Elena Huamán Torres", dni="70011223", email="rosa.huaman@correo.pe", phone="955111222")
BODY = "EXPERIENCIA\nOperador de planta 2015 - 2023\nCertificación en soldadura TIG vigente\n"


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def _two_areas(client, h):
    planta = create_position(client, h, "Operador de Planta", area="Planta")
    mina = create_position(client, h, "Operador de Mina", area="Mina")
    src = create_source(client, h, "Portal Minero Perú")
    ids = {}
    for key, pos, person in (("planta", planta, JUAN), ("mina", mina, ROSA)):
        r = upload_cv(client, h, make_cv_pdf(**person, body=BODY), f"{key}.pdf", pos["id"], src["id"])
        assert r.status_code == 201, r.text
        ids[key] = r.json()["result"]["candidateId"]
    return planta, mina, ids


def _create(client, h, **kw):
    body = {"title": "Soldadura TIG", "ruleText": "Certificación en soldadura TIG", **kw}
    return client.post("/api/criteria", json=body, headers=h)


def test_create_list_update_criterion(client, db, make_user):
    _, h = make_user()
    r = _create(client, h, appliesToDepartment="Planta", weightLabel="Prioritario")
    assert r.status_code == 201, r.text
    crit = r.json()["criterion"]
    assert set(crit) == CRITERION_KEYS
    assert crit["createdBy"] == "Ana Torres" and crit["isCorrection"] is False
    assert crit["weightLabel"] == "Prioritario" and crit["appliesToDepartment"] == "Planta"
    assert r.json()["state"]["recruitmentCriteria"] == [crit]

    assert client.get("/api/criteria", headers=h).json()["criteria"] == [crit]

    r = client.patch(f"/api/criteria/{crit['id']}", json={"weightLabel": "Deseable", "title": "TIG"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["criterion"]["weightLabel"] == "Deseable" and r.json()["criterion"]["title"] == "TIG"
    (create_log,) = _logs(db, "criterion.create")
    (update_log,) = _logs(db, "criterion.update")
    assert create_log.user_name == "Ana Torres" and update_log.entity_id == crit["id"]
    assert update_log.details["before"]["weightLabel"] == "Prioritario"
    assert update_log.details["after"]["weightLabel"] == "Deseable"


def test_criterion_defaults_and_validation(client, db, make_user):
    _, h = make_user()
    crit = _create(client, h).json()["criterion"]
    assert crit["appliesToDepartment"] == "Todas las áreas" and crit["weightLabel"] == "Importante"
    assert _create(client, h, weightLabel="Crítico").status_code == 422
    assert _create(client, h, title="  ").status_code == 422
    assert client.patch("/api/criteria/nada", json={"title": "x"}, headers=h).status_code == 404
    assert client.patch(f"/api/criteria/{crit['id']}", json={"title": None}, headers=h).status_code == 422
    assert client.get("/api/criteria").status_code == 401


def test_criterion_recomputes_rule_scores_for_its_area(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, ids = _two_areas(client, h)
    before = client.get("/api/state", headers=h).json()
    assert candidate_in(before, ids["planta"])["aiAppliedCriteria"] == []

    r = _create(client, h, appliesToDepartment="Planta", weightLabel="Prioritario")
    assert r.status_code == 201
    state = r.json()["state"]
    planta, mina = candidate_in(state, ids["planta"]), candidate_in(state, ids["mina"])
    assert planta["aiAppliedCriteria"] == ["Soldadura TIG"]
    assert planta["metricReport"]["overallScore"] >= candidate_in(before, ids["planta"])["metricReport"]["overallScore"]
    assert mina["aiAppliedCriteria"] == []  # otra área: no aplica
    assert db.get(Candidate, ids["planta"]).rule_bonus == 4

    # un criterio de todas las áreas alcanza a las dos
    state = _create(client, h, title="Soldadura", ruleText="soldadura").json()["state"]
    assert "Soldadura" in candidate_in(state, ids["mina"])["aiAppliedCriteria"]

    # cambiar el área del primero lo saca de Planta
    crit = r.json()["criterion"]
    resp = client.patch(f"/api/criteria/{crit['id']}", json={"appliesToDepartment": "Mina"}, headers=h)
    state = resp.json()["state"]
    assert "Soldadura TIG" not in candidate_in(state, ids["planta"])["aiAppliedCriteria"]
    assert "Soldadura TIG" in candidate_in(state, ids["mina"])["aiAppliedCriteria"]


def test_new_ingest_uses_criteria(client, db, make_user, rrhh_root):
    _, h = make_user()
    planta, _, _ = _two_areas(client, h)
    _create(client, h, appliesToDepartment="Planta")
    src = create_source(client, h, "Bolsa Nacional Minera", "Bolsa Nacional")
    other = dict(full_name="Luis Alberto Ccori Apaza", dni="41122334", email="luis.ccori@correo.pe", phone="944222333")
    r = upload_cv(client, h, make_cv_pdf(**other, body=BODY), "luis.pdf", planta["id"], src["id"])
    cand = candidate_in(r.json()["state"], r.json()["result"]["candidateId"])
    assert cand["aiAppliedCriteria"] == ["Soldadura TIG"]


def test_teach_ai_creates_area_criterion(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, ids = _two_areas(client, h)
    r = client.post(
        f"/api/candidates/{ids['planta']}/decision",
        json={
            "decision": "Rechazado", "teachAi": True, "criterionTitle": "Soldadura TIG",
            "criterionRule": "Certificación en soldadura TIG", "criterionWeight": "Prioritario",
            "isCorrection": True, "wrongAiAssumption": "La IA pensó que no hacía falta",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    (crit,) = state["recruitmentCriteria"]
    assert crit["appliesToDepartment"] == "Planta"  # el área del puesto
    assert crit["learnedFromCandidate"] == "Juan Carlos Quispe Mamani"
    assert crit["isCorrection"] is True and crit["weightLabel"] == "Prioritario"
    assert crit["wrongAiAssumption"] == "La IA pensó que no hacía falta"
    assert crit["createdBy"] == "Ana Torres"
    (log,) = _logs(db, "criterion.create")
    assert log.user_name == "Ana Torres" and log.entity_id == crit["id"]
    assert candidate_in(state, ids["planta"])["decision"] == "Rechazado"
    assert candidate_in(state, ids["planta"])["aiAppliedCriteria"] == ["Soldadura TIG"]  # R11: reglas recalculadas
    assert candidate_in(state, ids["mina"])["aiAppliedCriteria"] == []


def test_teach_ai_defaults_and_requires_text(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, ids = _two_areas(client, h)
    r = client.post(
        f"/api/candidates/{ids['planta']}/decision", json={"decision": "Aprobado", "teachAi": True}, headers=h,
    )
    assert r.status_code == 422
    assert not _logs(db, "criterion.create") and not _logs(db, "candidate.decision")
    r = client.post(
        f"/api/candidates/{ids['planta']}/decision",
        json={"decision": "Aprobado", "teachAi": True, "criterionTitle": "HSEC", "criterionRule": "hsec vigente"},
        headers=h,
    )
    (crit,) = r.json()["state"]["recruitmentCriteria"]
    assert crit["weightLabel"] == "Importante" and crit["isCorrection"] is False
    assert crit["wrongAiAssumption"] is None


def test_teach_ai_not_created_when_transition_fails(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, ids = _two_areas(client, h)
    r = client.post(
        f"/api/candidates/{ids['planta']}/decision",
        # repetir el estado actual es la única transición que falla
        json={"decision": "Pendiente de revisión", "teachAi": True, "criterionTitle": "X", "criterionRule": "y"},
        headers=h,
    )
    assert r.status_code == 409
    assert client.get("/api/criteria", headers=h).json()["criteria"] == []
