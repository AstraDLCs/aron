import pytest
from sqlalchemy import select

from app.constants import DECISION_TRANSITIONS, DECISIONS
from app.models.audit import AuditLog
from app.models.org import Requirement
from app.models.people import Candidate
from tests.fixtures.cvs import (
    candidate_in,
    create_position,
    create_requirement,
    create_source,
    make_cv_pdf,
    upload_cv,
)

PEOPLE = [
    dict(full_name="Juan Carlos Quispe Mamani", dni="45678912", email="juan.quispe@correo.pe", phone="987654321"),
    dict(full_name="Rosa Elena Huamán Torres", dni="70011223", email="rosa.huaman@correo.pe", phone="955111222"),
    dict(full_name="Luis Alberto Ccori Apaza", dni="41122334", email="luis.ccori@correo.pe", phone="944222333"),
]


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def _setup(client, h, quantity=1, with_requirement=True, n=1, position="Operador de Planta"):
    pos = create_position(client, h, position)
    src = create_source(client, h, "Portal Minero Perú")
    req = create_requirement(client, h, pos["id"], quantity=quantity) if with_requirement else None
    ids = []
    for person in PEOPLE[:n]:
        r = upload_cv(client, h, make_cv_pdf(**person), f"{person['dni']}.pdf", pos["id"], src["id"])
        assert r.status_code == 201, r.text
        ids.append(r.json()["result"]["candidateId"])
    return pos, req, ids


def _decide(client, h, cid, decision, **extra):
    return client.post(f"/api/candidates/{cid}/decision", json={"decision": decision, **extra}, headers=h)


def _need(state, req_id):
    return next(j for j in state["jobNeeds"] if j["id"] == req_id)


def _reach(client, h, cid, state_name):
    """Lleva la postulación (Pendiente) hasta el estado indicado por un camino permitido."""
    path = {
        "Pendiente de revisión": [],
        "Aprobado": ["Aprobado"],
        "Rechazado": ["Rechazado"],
        "Contratado": ["Aprobado", "Contratado"],
    }[state_name]
    for step in path:
        assert _decide(client, h, cid, step).status_code == 200


@pytest.mark.parametrize("origin", DECISIONS)
@pytest.mark.parametrize("target", DECISIONS)
def test_transitions_matrix(client, db, make_user, rrhh_root, origin, target):
    _, h = make_user()
    _, req, (cid,) = _setup(client, h)
    _reach(client, h, cid, origin)
    r = _decide(client, h, cid, target)
    if target in DECISION_TRANSITIONS[origin]:
        assert r.status_code == 200, r.text
        assert candidate_in(r.json()["state"], cid)["decision"] == target
    else:
        assert r.status_code == 409
        assert r.json()["detail"] == f"Transición no permitida: {origin} → {target}"
        assert candidate_in(client.get("/api/state", headers=h).json(), cid)["decision"] == origin


def test_invalid_decision_value_is_422(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, (cid,) = _setup(client, h)
    assert _decide(client, h, cid, "Contratadísimo").status_code == 422
    assert _decide(client, h, cid, "Aprobado", managerScore=101).status_code == 422
    assert _decide(client, h, "no-existe", "Aprobado").status_code == 404
    unauth = client.post(f"/api/candidates/{cid}/decision", json={"decision": "Aprobado"})
    assert unauth.status_code == 401


def _auto_created(db):
    return [e for e in _logs(db, "requirement.create") if (e.details or {}).get("auto")]


def test_hire_without_requirement_creates_one_slot_requirement(client, db, make_user, rrhh_root):
    _, h = make_user()
    pos, _, (a,) = _setup(client, h, with_requirement=False)
    r = _decide(client, h, a, "Contratado")  # directo desde Pendiente, sin requerimiento: no se bloquea
    assert r.status_code == 200, r.text
    cand = candidate_in(r.json()["state"], a)
    assert cand["decision"] == "Contratado" and cand["requirementId"]
    need = _need(r.json()["state"], cand["requirementId"])
    assert need["positionId"] == pos["id"] and need["vacancies"] == 1 and need["status"] == "Cubierto"
    (log,) = _auto_created(db)
    assert log.summary == "Creó un requerimiento de 1 plaza para Operador de Planta al contratar a Juan Carlos Quispe Mamani"


def test_hire_when_requirement_is_full_creates_another(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, req, (a, b) = _setup(client, h, quantity=1, n=2)
    r = _decide(client, h, a, "Contratado")
    assert r.status_code == 200, r.text
    need = _need(r.json()["state"], req["id"])
    assert need["status"] == "Cubierto" and need["filledCount"] == 1
    covered = _logs(db, "requirement.covered")
    assert len(covered) == 1 and covered[0].user_name == "Sistema" and covered[0].entity_id == req["id"]
    assert not _auto_created(db)

    r = _decide(client, h, b, "Contratado")
    assert r.status_code == 200, r.text
    cand_b = candidate_in(r.json()["state"], b)
    assert cand_b["decision"] == "Contratado" and cand_b["requirementId"] != req["id"]
    assert _need(r.json()["state"], req["id"])["filledCount"] == 1
    assert len(_auto_created(db)) == 1


def test_hire_with_room_for_two_keeps_requirement_open(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, req, (a, b) = _setup(client, h, quantity=2, n=2)
    for cid in (a, b):
        _decide(client, h, cid, "Aprobado")
    state = _decide(client, h, a, "Contratado").json()["state"]
    assert _need(state, req["id"])["status"] == "Abierto"
    assert not _logs(db, "requirement.covered")
    state = _decide(client, h, b, "Contratado").json()["state"]
    assert _need(state, req["id"])["status"] == "Cubierto"
    assert len(_logs(db, "requirement.covered")) == 1


def test_hire_assigns_requirement_from_payload(client, db, make_user, rrhh_root):
    _, h = make_user()
    pos, _, (a,) = _setup(client, h, with_requirement=False)
    req = create_requirement(client, h, pos["id"], quantity=1)  # se crea después: la postulación no lo tiene
    assert candidate_in(client.get("/api/state", headers=h).json(), a)["requirementId"] is None
    _decide(client, h, a, "Aprobado")
    r = _decide(client, h, a, "Contratado", requirementId=req["id"])
    assert r.status_code == 200, r.text
    cand = candidate_in(r.json()["state"], a)
    assert cand["requirementId"] == req["id"] and cand["targetNeedId"] == req["id"]
    assert _need(r.json()["state"], req["id"])["status"] == "Cubierto"


def test_hire_rejects_requirement_of_other_position(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, (a,) = _setup(client, h, with_requirement=False)
    other = create_position(client, h, "Geólogo Junior")
    other_req = create_requirement(client, h, other["id"])
    _decide(client, h, a, "Aprobado")
    assert _decide(client, h, a, "Contratado", requirementId=other_req["id"]).status_code == 422
    assert _decide(client, h, a, "Contratado", requirementId="no-existe").status_code == 422
    assert candidate_in(client.get("/api/state", headers=h).json(), a)["decision"] == "Aprobado"


def test_hire_in_cancelled_requirement_uses_a_new_one(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, req, (a,) = _setup(client, h)
    _decide(client, h, a, "Aprobado")
    patch = client.patch(f"/api/requirements/{req['id']}", json={"status": "Cancelado"}, headers=h)
    assert patch.status_code == 200
    r = _decide(client, h, a, "Contratado")
    assert r.status_code == 200, r.text
    assert candidate_in(r.json()["state"], a)["requirementId"] != req["id"]
    assert _need(r.json()["state"], req["id"])["status"] == "Cancelado"
    assert len(_auto_created(db)) == 1


def test_undo_hire_reopens_requirement(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, req, (a, b) = _setup(client, h, n=2, position="Supervisor HSEC")
    _decide(client, h, a, "Aprobado")
    _decide(client, h, a, "Contratado")
    r = _decide(client, h, a, "Aprobado")
    assert r.status_code == 200, r.text
    need = _need(r.json()["state"], req["id"])
    assert need["status"] == "Abierto" and need["filledCount"] == 0
    reopened = _logs(db, "requirement.reopened")
    assert len(reopened) == 1 and reopened[0].user_name == "Sistema" and reopened[0].entity_id == req["id"]
    undo = [e for e in _logs(db, "candidate.decision") if e.summary.startswith("Deshizo")]
    assert [e.summary for e in undo] == ["Deshizo la contratación de Juan Carlos Quispe Mamani (Supervisor HSEC)"]
    assert db.get(Requirement, req["id"]).closed_at is None

    # la plaza liberada se puede volver a ocupar por otra persona
    _decide(client, h, b, "Aprobado")
    assert _decide(client, h, b, "Contratado", requirementId=req["id"]).status_code == 200


def test_undo_hire_to_rejected(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, req, (a,) = _setup(client, h)
    _decide(client, h, a, "Aprobado")
    _decide(client, h, a, "Contratado")
    r = _decide(client, h, a, "Rechazado")
    assert r.status_code == 200
    assert _need(r.json()["state"], req["id"])["status"] == "Abierto"
    assert len(_logs(db, "requirement.reopened")) == 1


def test_decision_audit_records_actor(client, db, make_user, rrhh_root):
    _, ha = make_user()
    ub, hb = make_user(email="beto@mina.pe", full_name="Beto Salas")
    _, _, (a,) = _setup(client, ha)
    r = _decide(client, hb, a, "Aprobado", managerScore=88, managerNotes="Buen perfil")
    assert r.status_code == 200
    cand = candidate_in(r.json()["state"], a)
    assert cand["evaluatedBy"] == "Beto Salas" and cand["evaluatedAt"]
    assert cand["managerScore"] == 88 and cand["managerNotes"] == "Buen perfil"
    (log,) = _logs(db, "candidate.decision")
    assert log.user_name == "Beto Salas" and log.user_id == ub.id
    assert log.entity_type == "candidate" and log.entity_id == a
    assert log.summary == "Aprobó a Juan Carlos Quispe Mamani para Operador de Planta"
    assert log.details == {"from": "Pendiente de revisión", "to": "Aprobado", "managerScore": 88}

    r = _decide(client, hb, a, "Rechazado")
    second = _logs(db, "candidate.decision")[1]
    assert second.summary == "Rechazó a Juan Carlos Quispe Mamani para Operador de Planta"
    assert second.details["managerScore"] == 88  # sin puntaje nuevo se conserva el anterior
    assert candidate_in(r.json()["state"], a)["managerNotes"] == "Buen perfil"  # las notas se conservan


def test_hire_summary_and_failed_decision_leaves_no_audit(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, (a,) = _setup(client, h)
    assert _decide(client, h, a, "Pendiente de revisión").status_code == 409  # mismo estado: no cambia nada
    assert not _logs(db, "candidate.decision")
    _decide(client, h, a, "Contratado")
    assert _logs(db, "candidate.decision")[-1].summary == "Contrató a Juan Carlos Quispe Mamani para Operador de Planta"


def test_kpis_in_state(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, req, (a, b, c) = _setup(client, h, quantity=2, n=3)
    base = client.get("/api/state", headers=h).json()["kpis"]
    assert base["filledVacancies"] == 0 and base["preselectedOrHired"] == 0 and base["aiAgreementRate"] == 100
    assert base["totalVacancies"] == 2

    # fuerza veredictos de la IA (la clasificación llega en la Tarea 7)
    db.get(Candidate, a).ai_verdict = "Pre-aprobado"
    db.get(Candidate, b).ai_verdict = "Pre-aprobado"
    db.get(Candidate, c).ai_verdict = "Pre-denegado"
    db.flush()

    _decide(client, h, a, "Aprobado")
    _decide(client, h, a, "Contratado")
    _decide(client, h, b, "Rechazado")  # la IA dijo Pre-aprobado: no coinciden
    state = _decide(client, h, c, "Rechazado").json()["state"]
    k = state["kpis"]
    assert k["filledVacancies"] == 1 and k["remainingVacancies"] == 1 and k["coveragePercent"] == 50
    assert k["preselectedOrHired"] == 1
    assert k["aiAgreementRate"] == 67  # 2 de 3 coinciden
