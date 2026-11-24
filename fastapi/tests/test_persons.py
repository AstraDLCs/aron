from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.people import Candidate, Person
from app.services.persons import apply_person_fields
from tests.fixtures.cvs import candidate_in, create_position, create_source, make_cv_pdf, upload_cv

JUAN = dict(full_name="Juan Carlos Quispe Mamani", dni="45678912", email="juan.quispe@correo.pe", phone="987 654 321")
MINAS_BODY = "EXPERIENCIA LABORAL\nIngeniero de Minas en Minera Ficticia 2010 - 2024\nIPERC y PETAR.\n"


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def _org(client, h):
    p1 = create_position(client, h, "Operador de Planta")
    p2 = create_position(client, h, "Supervisor HSEC")
    src = create_source(client, h, "Portal Minero Perú")
    return p1, p2, src


def test_link_by_document_or_email(client, db, make_user, rrhh_root):
    _, h = make_user()
    p1, p2, src = _org(client, h)
    a = upload_cv(client, h, make_cv_pdf(**JUAN), "a.pdf", p1["id"], src["id"]).json()["result"]

    # otro PDF, mismo DNI (sin email): misma persona
    b_pdf = make_cv_pdf(JUAN["full_name"], JUAN["dni"], "", JUAN["phone"], body=MINAS_BODY)
    b = upload_cv(client, h, b_pdf, "b.pdf", p1["id"], src["id"]).json()["result"]
    assert b["personId"] == a["personId"]

    # sin DNI, mismo email con otras mayúsculas: misma persona
    c_pdf = make_cv_pdf(JUAN["full_name"], "", "Juan.Quispe@CORREO.pe", "", body="Otro texto de prueba suficiente.")
    c = upload_cv(client, h, c_pdf, "c.pdf", p2["id"], src["id"]).json()["result"]
    assert c["personId"] == a["personId"]
    assert len(_logs(db, "person.link")) == 2

    # solo coincide el teléfono: personas distintas, marcadas como posible misma persona
    d_pdf = make_cv_pdf("Pedro Luis Ramos Ccama", "71234567", "pedro.ramos@correo.pe", "+51 987 654 321")
    d = upload_cv(client, h, d_pdf, "d.pdf", p1["id"], src["id"])
    assert d.status_code == 201
    d = d.json()
    assert d["result"]["personId"] != a["personId"]
    state = d["state"]
    assert candidate_in(state, d["result"]["candidateId"])["possibleSamePersonIds"] == [a["personId"]]
    assert d["result"]["personId"] in candidate_in(state, a["candidateId"])["possibleSamePersonIds"]
    assert len(db.scalars(select(Person)).all()) == 2


def test_link_fills_blanks_without_overwriting(client, db, make_user, rrhh_root):
    _, h = make_user()
    p1, p2, src = _org(client, h)
    cv1 = make_cv_pdf(JUAN["full_name"], JUAN["dni"], "", JUAN["phone"], city="Arequipa")
    a = upload_cv(client, h, cv1, "cv1.pdf", p1["id"], src["id"]).json()["result"]
    person = db.get(Person, a["personId"])
    assert person.origin_location == "Arequipa, Perú" and person.email == ""
    career = person.career

    cv2 = make_cv_pdf("Juan C. Quispe", JUAN["dni"], JUAN["email"], "912 000 111", body=MINAS_BODY, city="Lima")
    b = upload_cv(client, h, cv2, "cv2.pdf", p2["id"], src["id"]).json()["result"]
    assert b["personId"] == a["personId"]
    db.refresh(person)
    assert person.origin_location == "Arequipa, Perú"  # no se pisa
    assert person.full_name == JUAN["full_name"] and person.phone == JUAN["phone"] and person.career == career
    assert person.email == JUAN["email"]  # vacío en el CV 1: se llena
    assert person.field_sources["email"] == "reglas"
    link = _logs(db, "person.link")
    assert len(link) == 1 and link[0].details == {"reason": "mismo documento"}


def test_person_field_precedence(client, db, make_user, rrhh_root):
    _, h = make_user()
    p1, p2, src = _org(client, h)
    a = upload_cv(client, h, make_cv_pdf(**JUAN), "a.pdf", p1["id"], src["id"]).json()["result"]
    pid = a["personId"]
    person = db.get(Person, pid)
    assert person.career == "Seguridad Industrial y Minera (HSEC)" and person.field_sources["career"] == "reglas"

    r = client.patch(f"/api/persons/{pid}", json={"career": "Ingeniería Metalúrgica", "phone": "999 888 777"},
                     headers=h)
    assert r.status_code == 200, r.text
    cand = candidate_in(r.json()["state"], a["candidateId"])
    assert cand["career"] == "Ingeniería Metalúrgica" and cand["phone"] == "999 888 777"
    log = _logs(db, "person.update")
    assert len(log) == 1 and sorted(log[0].details["fields"]) == ["career", "phone"]
    assert set(log[0].details) == {"fields"}

    # otro CV con el mismo DNI: las reglas no pisan lo que editó el usuario
    b_pdf = make_cv_pdf(JUAN["full_name"], JUAN["dni"], JUAN["email"], "911 000 111", body=MINAS_BODY)
    b = upload_cv(client, h, b_pdf, "b.pdf", p2["id"], src["id"]).json()["result"]
    assert b["personId"] == pid
    db.refresh(person)
    assert person.career == "Ingeniería Metalúrgica" and person.phone == "999 888 777"

    # la IA reemplaza un valor de las reglas, pero no uno del usuario; un vacío no borra nada
    assert person.university == "TECSUP" and person.field_sources["university"] == "reglas"
    assert apply_person_fields(person, {"university": "UNI - Universidad Nacional de Ingeniería"}, "ia") == [
        "university"
    ]
    assert person.field_sources["university"] == "ia"
    assert apply_person_fields(person, {"university": "SENATI"}, "reglas") == []
    assert apply_person_fields(person, {"career": "Otra"}, "ia") == []
    assert apply_person_fields(person, {"email": ""}, "ia") == []
    assert person.email == JUAN["email"]

    # el nombre completo editado se separa en nombres y apellidos
    r = client.patch(f"/api/persons/{pid}", json={"fullName": "Juan Carlos Quispe Huamán"}, headers=h)
    cand = candidate_in(r.json()["state"], a["candidateId"])
    assert (cand["firstNames"], cand["lastNames"]) == ("Juan Carlos", "Quispe Huamán")
    assert client.patch("/api/persons/nope", json={"career": "x"}, headers=h).status_code == 404
    assert client.patch(f"/api/persons/{pid}", json={"fullName": None}, headers=h).status_code == 422


def test_merge_persons(client, db, make_user, rrhh_root):
    _, h = make_user()
    p1, p2, src = _org(client, h)
    a = upload_cv(client, h, make_cv_pdf(**JUAN), "a.pdf", p1["id"], src["id"]).json()["result"]
    d_pdf = make_cv_pdf("Juan C. Quispe", "", "", JUAN["phone"], body=MINAS_BODY)
    d = upload_cv(client, h, d_pdf, "d.pdf", p2["id"], src["id"]).json()["result"]
    keep, drop = a["personId"], d["personId"]
    assert keep != drop
    dropped = db.get(Person, drop)
    dropped.psych_evaluation = {
        "testBatteryName": "Batería Minera", "accessCode": "PL-PS-0001", "status": "Completada",
        "scores": None, "averageScore": 81, "aptitudeLevel": "Apto Recomendado", "aiPsychObservation": "ok",
    }
    db.flush()

    r = client.post(f"/api/persons/{keep}/merge", json={"otherPersonId": drop}, headers=h)
    assert r.status_code == 200, r.text
    assert db.get(Person, drop) is None
    assert {c.person_id for c in db.scalars(select(Candidate))} == {keep}
    state = r.json()["state"]
    ca, cd = candidate_in(state, a["candidateId"]), candidate_in(state, d["candidateId"])
    assert ca["personId"] == cd["personId"] == keep
    assert ca["fullName"] == "Juan Carlos Quispe Mamani"
    assert ca["psychEvaluation"]["status"] == "Completada" and ca["metricReport"]["psychScore"] == 81
    assert ca["possibleSamePersonIds"] == []
    assert len(ca["otherApplications"]) == 1 and len(cd["otherApplications"]) == 1
    assert len(_logs(db, "person.merge")) == 1

    assert client.post(f"/api/persons/{keep}/merge", json={"otherPersonId": keep}, headers=h).status_code == 422
    assert client.post(f"/api/persons/{keep}/merge", json={"otherPersonId": "nope"}, headers=h).status_code == 404
