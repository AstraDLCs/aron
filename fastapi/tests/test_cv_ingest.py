import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.org import Requirement
from app.models.people import Candidate, CvFile, Person
from app.services import ingest
from app.services.scoring import fit_verdict, global_index
from tests.fixtures.cvs import (
    candidate_in,
    create_position,
    create_requirement,
    create_source,
    make_blank_pdf,
    make_cv_pdf,
    upload_cv,
)

JUAN = dict(full_name="Juan Carlos Quispe Mamani", dni="45678912", email="juan.quispe@correo.pe", phone="987 654 321")
ROSA = dict(full_name="Rosa Elena Huamán Torres", dni="70011223", email="rosa.huaman@correo.pe", phone="955 111 222")

CANDIDATE_KEYS = {
    "id", "personId", "cvFileId", "positionId", "requirementId", "targetNeedId", "targetRoleTitle",
    "sourceBoardId", "sourceBoardName",
    "fullName", "firstNames", "lastNames", "documentId", "email", "phone", "phoneOrEmail", "age",
    "originLocation", "university", "career", "yearsWorked", "workHistorySummary", "specifications",
    "languages", "licenses", "interviewNotes",
    "cvFileName", "cvMimeType", "cvUploadedAt", "cvUploadedBy", "cvOrigin", "cvPath", "cvMissing",
    "psychEvaluation", "excelTestResults", "metricReport",
    "aiStatus", "aiVerdict", "aiAptitudeScore", "aiStrengths", "aiObservations", "aiReason", "aiAppliedCriteria",
    "aiAppliedCorrectionTitle", "aiModel", "aiClassifiedAt", "aiError", "aiSummary", "aiObservedScore",
    "decision", "managerScore", "managerNotes", "evaluatedBy", "evaluatedAt",
    "possibleSamePersonIds", "otherApplications", "processDaysElapsed", "createdAt",
}
METRIC_KEYS = {
    "technicalSpecsScore", "experienceScore", "educationCareerScore", "psychScore", "overallScore", "fitVerdict",
    "aiDetailedReport", "generatedAt",
}
DEFAULT_PSYCH = {
    "testBatteryName": "Pendiente de prueba", "accessCode": "", "status": "Sin enviar", "scores": None,
    "averageScore": None, "aptitudeLevel": "Pendiente", "aiPsychObservation": "",
}


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def _files(root):
    return sorted(p for p in root.rglob("*") if p.is_file())


def _org(client, h, n_positions=1):
    positions = [create_position(client, h, name) for name in ("Operador de Planta", "Supervisor HSEC")[:n_positions]]
    src = create_source(client, h, "Portal Minero Perú")
    return positions, src


def test_upload_creates_candidate_person_and_file(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    data = make_cv_pdf(**JUAN)
    r = upload_cv(client, h, data, "cv juan.pdf", pos["id"], src["id"])
    assert r.status_code == 201, r.text
    res = r.json()["result"]
    assert res["status"] == "created" and res["message"]
    assert res["candidateId"] and res["cvFileId"] and res["personId"]

    path = rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv juan.pdf"
    assert path.read_bytes() == data

    state = r.json()["state"]
    cand = candidate_in(state, res["candidateId"])
    assert cand["decision"] == "Pendiente de revisión"
    assert cand["aiStatus"] == "Sin IA"
    assert cand["fullName"] == "Juan Carlos Quispe Mamani"
    assert cand["firstNames"] == "Juan Carlos" and cand["lastNames"] == "Quispe Mamani"
    assert cand["documentId"] == "45678912"
    assert cand["personId"] == res["personId"] and cand["cvFileId"] == res["cvFileId"]
    assert cand["phoneOrEmail"] == "juan.quispe@correo.pe · 987 654 321"
    assert cand["cvPath"] == "operador-de-planta/portal-minero-peru/cv juan.pdf"
    assert cand["cvFileName"] == "cv juan.pdf" and cand["cvMimeType"] == "application/pdf"
    assert cand["cvOrigin"] == "app" and cand["cvUploadedBy"] == "Ana Torres" and cand["cvMissing"] is False
    assert cand["targetRoleTitle"] == "Operador de Planta" and cand["sourceBoardName"] == "Portal Minero Perú"
    assert cand["requirementId"] is None and cand["targetNeedId"] == ""
    assert cand["processDaysElapsed"] == 0
    assert state["positions"][0]["candidatesCount"] == 1
    assert state["jobBoards"][0]["candidatesReceived"] == 1
    assert state["kpis"]["totalCandidates"] == 1

    cv = db.get(CvFile, res["cvFileId"])
    assert cv.sha256 == hashlib.sha256(data).hexdigest()
    assert cv.text_status == "ok" and "Quispe" in cv.text and cv.size == len(data)
    logs = _logs(db, "cv.upload")
    assert len(logs) == 1
    assert logs[0].summary == "Subió el CV de Juan Carlos Quispe Mamani a operador-de-planta/portal-minero-peru"
    assert logs[0].user_name == "Ana Torres"


def test_snapshot_candidate_contract_keys(client, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    r = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"])
    cand = r.json()["state"]["candidates"][0]
    assert set(cand) == CANDIDATE_KEYS
    assert set(cand["metricReport"]) == METRIC_KEYS
    assert cand["psychEvaluation"] == DEFAULT_PSYCH
    assert cand["excelTestResults"] == [] and cand["otherApplications"] == []
    assert cand["aiVerdict"] is None and cand["aiStrengths"] == [] and cand["aiModel"] is None
    assert cand["aiObservedScore"] == cand["metricReport"]["overallScore"]


def test_metric_report_rules_then_ai_pillars(client, db, make_user, rrhh_root):
    user, h = make_user()
    (pos,), src = _org(client, h)
    r = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"])
    cand_id = r.json()["result"]["candidateId"]
    mr = candidate_in(r.json()["state"], cand_id)["metricReport"]
    c = db.get(Candidate, cand_id)
    expected = global_index(c.rule_technical, c.rule_experience, c.rule_education, None, c.rule_bonus)
    assert mr["overallScore"] == expected and mr["psychScore"] == 64
    assert mr["technicalSpecsScore"] == c.rule_technical and mr["fitVerdict"] == fit_verdict(expected)
    assert mr["aiDetailedReport"] == c.rule_report and c.rule_report

    c.ai_status = "Clasificado"
    c.ai_technical, c.ai_experience, c.ai_education = 90, 80, 70
    c.ai_detailed_report = "Informe de la IA"
    c.rule_bonus = 5  # el bono de reglas no se usa cuando hay IA
    person = db.get(Person, c.person_id)
    person.psych_evaluation = {**DEFAULT_PSYCH, "status": "Completada", "averageScore": 80,
                               "aptitudeLevel": "Apto Recomendado"}
    db.flush()
    mr = candidate_in(client.get("/api/state", headers=h).json(), cand_id)["metricReport"]
    assert mr["overallScore"] == global_index(90, 80, 70, 80, 0)
    assert mr["technicalSpecsScore"] == 90 and mr["psychScore"] == 80
    assert mr["aiDetailedReport"] == "Informe de la IA"


def test_duplicate_same_position_409(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    data = make_cv_pdf(**JUAN)
    r1 = upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"])
    assert r1.status_code == 201
    r2 = upload_cv(client, h, data, "otro nombre.pdf", pos["id"], src["id"])
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["code"] == "duplicate" and detail["message"]
    assert detail["existing"]["uploadedBy"] == "Ana Torres"
    assert detail["existing"]["path"] == "operador-de-planta/portal-minero-peru/cv.pdf"
    assert detail["existing"]["uploadedAt"]
    assert len(_logs(db, "cv.duplicate_rejected")) == 1
    assert len(_files(rrhh_root)) == 1
    assert len(db.scalars(select(Candidate)).all()) == 1


def test_duplicate_race_integrity_error_maps_to_duplicate(client, db, make_user, rrhh_root, monkeypatch):
    """Si dos subidas compiten, la restricción única decide y el perdedor borra el archivo que escribió."""
    _, h = make_user()
    (pos,), src = _org(client, h)
    data = make_cv_pdf(**JUAN)
    assert upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"]).status_code == 201

    real = ingest.find_duplicate
    calls = {"n": 0}

    def blind_first_check(*args, **kwargs):  # simula que la otra subida aún no había confirmado
        calls["n"] += 1
        return None if calls["n"] == 1 else real(*args, **kwargs)

    monkeypatch.setattr(ingest, "find_duplicate", blind_first_check)
    r = upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "duplicate"
    assert _files(rrhh_root) == [rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv.pdf"]
    assert len(db.scalars(select(CvFile)).all()) == 1
    assert len(_logs(db, "cv.duplicate_rejected")) == 1


def test_missing_file_path_is_not_reused(client, db, make_user, rrhh_root):
    """Un CV registrado cuyo archivo falta conserva su ruta: otro CV con el mismo nombre usa un sufijo."""
    _, h = make_user()
    (pos,), src = _org(client, h)
    a = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"]).json()["result"]
    folder = rrhh_root / "operador-de-planta" / "portal-minero-peru"
    (folder / "cv.pdf").unlink()
    rosa = make_cv_pdf(**ROSA)
    r = upload_cv(client, h, rosa, "cv.pdf", pos["id"], src["id"])
    assert r.status_code == 201, r.text
    b = candidate_in(r.json()["state"], r.json()["result"]["candidateId"])
    assert b["cvPath"] == f"operador-de-planta/portal-minero-peru/cv-{hashlib.sha256(rosa).hexdigest()[:8]}.pdf"
    assert db.get(CvFile, a["cvFileId"]).stored_path == "operador-de-planta/portal-minero-peru/cv.pdf"
    assert _files(rrhh_root) == [rrhh_root / b["cvPath"]]


def test_stored_path_conflict_retries_with_new_name(client, db, make_user, rrhh_root, monkeypatch):
    """Si la ruta elegida ya estaba registrada, se reintenta con otro nombre y no se borra nada ajeno."""
    _, h = make_user()
    (pos,), src = _org(client, h)
    a = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"]).json()["result"]
    (rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv.pdf").unlink()
    monkeypatch.setattr(ingest, "registered_paths", lambda *args: set())  # no sabe de la ruta registrada
    rosa = make_cv_pdf(**ROSA)
    r = upload_cv(client, h, rosa, "cv.pdf", pos["id"], src["id"])
    assert r.status_code == 201, r.text
    b = candidate_in(r.json()["state"], r.json()["result"]["candidateId"])
    assert b["cvPath"].endswith(f"/cv-{hashlib.sha256(rosa).hexdigest()[:8]}.pdf")
    assert (rrhh_root / b["cvPath"]).read_bytes() == rosa
    assert _files(rrhh_root) == [rrhh_root / b["cvPath"]]  # el primer intento (cv.pdf) era propio y se quitó
    assert db.get(CvFile, a["cvFileId"]).stored_path == "operador-de-planta/portal-minero-peru/cv.pdf"


def test_same_file_other_position_new_application_same_person(client, db, make_user, rrhh_root):
    _, h = make_user()
    (p1, p2), src = _org(client, h, n_positions=2)
    data = make_cv_pdf(**JUAN)
    r1 = upload_cv(client, h, data, "cv.pdf", p1["id"], src["id"])
    r2 = upload_cv(client, h, data, "cv.pdf", p2["id"], src["id"])
    assert r1.status_code == 201 and r2.status_code == 201, r2.text
    assert r1.json()["result"]["personId"] == r2.json()["result"]["personId"]
    assert len(_files(rrhh_root)) == 2
    state = r2.json()["state"]
    c1 = candidate_in(state, r1.json()["result"]["candidateId"])
    c2 = candidate_in(state, r2.json()["result"]["candidateId"])
    assert c1["otherApplications"] == [
        {"candidateId": c2["id"], "positionName": "Supervisor HSEC", "decision": "Pendiente de revisión"}
    ]
    assert len(c2["otherApplications"]) == 1 and c2["otherApplications"][0]["candidateId"] == c1["id"]
    assert len(_logs(db, "person.link")) == 1


def test_check_endpoint_statuses(client, make_user, rrhh_root):
    _, h = make_user()
    (p1, p2), src = _org(client, h, n_positions=2)
    a, b = make_cv_pdf(**JUAN), make_cv_pdf(**ROSA)
    sha = lambda d: hashlib.sha256(d).hexdigest()  # noqa: E731
    upload_cv(client, h, a, "a.pdf", p1["id"], src["id"])
    rb = upload_cv(client, h, b, "b.pdf", p1["id"], src["id"])
    assert client.delete(f"/api/cv-files/{rb.json()['result']['cvFileId']}", headers=h).status_code == 200
    items = [
        {"sha256": sha(a), "positionId": p1["id"]},
        {"sha256": sha(b), "positionId": p1["id"]},
        {"sha256": sha(b"nuevo"), "positionId": p1["id"]},
        {"sha256": sha(a).upper(), "positionId": p2["id"]},
    ]
    r = client.post("/api/cv-files/check", json={"items": items}, headers=h)
    assert r.status_code == 200
    assert [x["status"] for x in r.json()["results"]] == ["duplicate", "deleted_before", "new", "new"]
    assert r.json()["results"][0] == {"sha256": sha(a), "positionId": p1["id"], "status": "duplicate"}
    bad = client.post("/api/cv-files/check", json={"items": [{"sha256": "xyz", "positionId": p1["id"]}]}, headers=h)
    assert bad.status_code == 422


def test_delete_blocks_reimport_and_removes_personal_data(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    data = make_cv_pdf(**JUAN)
    res = upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"]).json()["result"]
    path = rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv.pdf"
    assert path.exists()

    r = client.delete(f"/api/cv-files/{res['cvFileId']}", headers=h)
    assert r.status_code == 200
    assert not path.exists()
    assert db.get(CvFile, res["cvFileId"]) is None
    assert db.get(Candidate, res["candidateId"]) is None
    assert db.get(Person, res["personId"]) is None
    assert db.scalar(select(Person).where(Person.document_id == "45678912")) is None
    state = r.json()["state"]
    assert state["candidates"] == []
    blocked = state["blockedCvFiles"]
    assert len(blocked) == 1
    assert set(blocked[0]) == {"id", "sha256", "positionId", "originalName", "deletedBy", "deletedAt"}
    assert blocked[0]["originalName"] == "cv.pdf" and blocked[0]["deletedBy"] == "Ana Torres"
    log = _logs(db, "cv.delete")[0]
    assert log.summary == "Eliminó el CV de Juan Carlos Quispe Mamani (Operador de Planta)"

    again = upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"])
    assert again.status_code == 409 and again.json()["detail"]["code"] == "deleted_before"
    assert again.json()["detail"]["existing"]["deletedBy"] == "Ana Torres"
    assert len(_logs(db, "cv.rejected_deleted")) == 1
    assert not path.exists()

    r = client.delete(f"/api/cv-files/blocked/{blocked[0]['id']}", headers=h)
    assert r.status_code == 200 and r.json()["state"]["blockedCvFiles"] == []
    assert len(_logs(db, "cv.unblock")) == 1
    assert upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"]).status_code == 201
    assert client.delete("/api/cv-files/blocked/no-existe", headers=h).status_code == 404
    assert client.delete("/api/cv-files/no-existe", headers=h).status_code == 404


def test_delete_keeps_person_with_other_applications(client, db, make_user, rrhh_root):
    _, h = make_user()
    (p1, p2), src = _org(client, h, n_positions=2)
    data = make_cv_pdf(**JUAN)
    r1 = upload_cv(client, h, data, "cv.pdf", p1["id"], src["id"]).json()["result"]
    r2 = upload_cv(client, h, data, "cv.pdf", p2["id"], src["id"]).json()["result"]
    r = client.delete(f"/api/cv-files/{r1['cvFileId']}", headers=h)
    assert r.status_code == 200
    assert db.get(Person, r1["personId"]) is not None
    remaining = r.json()["state"]["candidates"]
    assert [c["id"] for c in remaining] == [r2["candidateId"]]
    assert remaining[0]["otherApplications"] == []
    assert (rrhh_root / "supervisor-hsec" / "portal-minero-peru" / "cv.pdf").exists()


def test_move_cv_between_positions(client, db, make_user, rrhh_root, settings_override):
    _, h = make_user()
    (p1, p2), src = _org(client, h, n_positions=2)
    src2 = create_source(client, h, "Red de Referidos", category="Referidos Faena")
    req1 = create_requirement(client, h, p1["id"])
    req2 = create_requirement(client, h, p2["id"])
    data = make_cv_pdf(**JUAN)
    res = upload_cv(client, h, data, "cv.pdf", p1["id"], src["id"]).json()["result"]
    assert candidate_in(client.get("/api/state", headers=h).json(), res["candidateId"])["requirementId"] == req1["id"]

    with settings_override(openrouter_api_key="sk-test"):
        r = client.patch(f"/api/cv-files/{res['cvFileId']}", json={"positionId": p2["id"], "sourceId": src2["id"]},
                         headers=h)
    assert r.status_code == 200, r.text
    assert not (rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv.pdf").exists()
    assert (rrhh_root / "supervisor-hsec" / "red-de-referidos" / "cv.pdf").read_bytes() == data
    assert db.get(CvFile, res["cvFileId"]).stored_path == "supervisor-hsec/red-de-referidos/cv.pdf"
    cand = candidate_in(r.json()["state"], res["candidateId"])
    assert cand["positionId"] == p2["id"] and cand["requirementId"] == req2["id"]
    assert cand["sourceBoardId"] == src2["id"] and cand["cvPath"] == "supervisor-hsec/red-de-referidos/cv.pdf"
    assert cand["aiStatus"] == "En cola"
    assert len(_logs(db, "cv.move")) == 1

    # el mismo archivo vuelve a subirse al puesto 1; moverlo al puesto 2 choca con el que ya está allí
    res2 = upload_cv(client, h, data, "cv.pdf", p1["id"], src["id"]).json()["result"]
    r = client.patch(f"/api/cv-files/{res2['cvFileId']}", json={"positionId": p2["id"]}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "duplicate"
    assert (rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv.pdf").exists()
    assert client.patch(f"/api/cv-files/{res2['cvFileId']}", json={"positionId": "nope"}, headers=h).status_code == 422


def test_unsupported_and_too_large(client, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    r = upload_cv(client, h, b"documento antiguo de word", "cv.doc", pos["id"], src["id"])
    assert r.status_code == 415 and r.json()["detail"] == "Formato no soportado: usa PDF, DOCX, TXT o RTF"
    big = b"%PDF-1.4\n" + b"0" * (16 * 1024 * 1024)
    r = upload_cv(client, h, big, "grande.pdf", pos["id"], src["id"])
    assert r.status_code == 413 and r.json()["detail"] == "El archivo supera 15 MB"
    assert _files(rrhh_root) == []
    r = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"], origin="carpeta_servidor")
    assert r.status_code == 422
    r = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", "no-existe", src["id"])
    assert r.status_code == 422


def test_scanned_pdf_sin_texto(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    r = upload_cv(client, h, make_blank_pdf(), "escaneado.pdf", pos["id"], src["id"])
    assert r.status_code == 201
    cand = candidate_in(r.json()["state"], r.json()["result"]["candidateId"])
    assert cand["aiStatus"] == "Sin texto"
    assert cand["fullName"] == "Postulante (Verificar Nombre)"
    assert db.get(CvFile, cand["cvFileId"]).text_status == "empty"


def test_txt_cv_with_overlong_fields_is_trimmed_not_500(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    text = "\n".join([
        "Nombre: Lucía Mendoza Flores",
        "DNI: 46543210",
        "Universidad: " + "Instituto Minero " * 40,
        "Carrera: " + "Operación de planta " * 30,
        "Procedencia: " + "Arequipa " * 40,
    ])
    r = upload_cv(client, h, text.encode("utf-8"), "../../lucia.txt", pos["id"], src["id"])
    assert r.status_code == 201, r.text
    cand = candidate_in(r.json()["state"], r.json()["result"]["candidateId"])
    assert cand["fullName"] == "Lucía Mendoza Flores" and cand["documentId"] == "46543210"
    assert 0 < len(cand["university"]) <= 300 and 0 < len(cand["career"]) <= 300
    assert cand["cvFileName"] == "lucia.txt" and cand["cvMimeType"] == "text/plain"
    assert cand["cvPath"] == "operador-de-planta/portal-minero-peru/lucia.txt"


def test_requirement_assignment(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos, other), src = _org(client, h, n_positions=2)
    old = create_requirement(client, h, pos["id"])
    new = create_requirement(client, h, pos["id"])
    now = datetime.now(UTC)
    db.get(Requirement, old["id"]).opened_at = now - timedelta(days=5)
    db.get(Requirement, new["id"]).opened_at = now - timedelta(days=1)
    db.flush()

    r = upload_cv(client, h, make_cv_pdf(**JUAN), "a.pdf", pos["id"], src["id"])
    cand = candidate_in(r.json()["state"], r.json()["result"]["candidateId"])
    assert cand["requirementId"] == old["id"] and cand["targetNeedId"] == old["id"]

    r = upload_cv(client, h, make_cv_pdf(**ROSA), "b.pdf", pos["id"], src["id"], requirement_id=new["id"])
    assert candidate_in(r.json()["state"], r.json()["result"]["candidateId"])["requirementId"] == new["id"]

    cancelled = create_requirement(client, h, pos["id"])
    client.patch(f"/api/requirements/{cancelled['id']}", json={"status": "Cancelado"}, headers=h)
    third = make_cv_pdf("Pedro Luis Ramos Ccama", "71234567", "pedro.ramos@correo.pe", "944 333 222")
    r = upload_cv(client, h, third, "c.pdf", pos["id"], src["id"], requirement_id=cancelled["id"])
    assert r.status_code == 422
    other_req = create_requirement(client, h, other["id"])
    r = upload_cv(client, h, third, "c.pdf", pos["id"], src["id"], requirement_id=other_req["id"])
    assert r.status_code == 422
    assert len(_files(rrhh_root)) == 2

    assert ingest.pick_requirement(db, pos["id"], None).id == old["id"]


def test_unicode_filename_roundtrip(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    name = "CV José Ñuñez (1).pdf"
    data = make_cv_pdf("José Antonio Ñuñez Paredes", "41234567", "jose.nunez@correo.pe", "966 777 888")
    res = upload_cv(client, h, data, name, pos["id"], src["id"]).json()["result"]
    r = client.get(f"/api/cv-files/{res['cvFileId']}/download", headers=h)
    assert r.status_code == 200
    assert r.content == data
    assert f"filename*=UTF-8''{quote(name, safe='')}" in r.headers["content-disposition"]
    assert r.headers["content-type"] == "application/pdf"
    assert len(_logs(db, "cv.download")) == 1
    assert client.get("/api/cv-files/nope/download", headers=h).status_code == 404

    (rrhh_root / "operador-de-planta" / "portal-minero-peru" / name).unlink()
    r = client.get(f"/api/cv-files/{res['cvFileId']}/download", headers=h)
    assert r.status_code == 404
    assert candidate_in(client.get("/api/state", headers=h).json(), res["candidateId"])["cvMissing"] is True


def test_manual_candidate(client, db, make_user, rrhh_root, settings_override):
    _, h = make_user()
    (pos,), src = _org(client, h)
    body = {
        "fullName": "María Fernanda Ccori Apaza", "career": "Ingeniería de Minas", "positionId": pos["id"],
        "sourceId": src["id"], "yearsWorked": 6, "age": 31, "email": "maria.ccori@correo.pe",
        "phone": "933 222 111", "documentId": "40112233", "specifications": ["IPERC", "DS-024"],
        "interviewNotes": "Referida por el supervisor de turno",
    }
    r = client.post("/api/candidates", json=body, headers=h)
    assert r.status_code == 201, r.text
    cand = candidate_in(r.json()["state"], r.json()["candidateId"])
    assert cand["cvFileId"] is None and cand["cvMissing"] is False and cand["cvPath"] is None
    assert cand["fullName"] == "María Fernanda Ccori Apaza"
    assert cand["firstNames"] == "María Fernanda" and cand["lastNames"] == "Ccori Apaza"
    assert cand["career"] == "Ingeniería de Minas" and cand["yearsWorked"] == 6 and cand["age"] == 31
    assert cand["specifications"] == ["IPERC", "DS-024"]
    assert cand["interviewNotes"] == "Referida por el supervisor de turno"
    assert cand["aiStatus"] == "Sin IA" and cand["decision"] == "Pendiente de revisión"
    log = _logs(db, "candidate.create_manual")
    assert len(log) == 1 and "María Fernanda Ccori Apaza" in log[0].summary

    text = ingest.candidate_text(db, db.get(Candidate, cand["id"]))
    assert "María Fernanda Ccori Apaza" in text and "Ingeniería de Minas" in text and "IPERC" in text

    with settings_override(openrouter_api_key="sk-test"):
        r = client.post("/api/candidates", json={**body, "documentId": "40998877", "fullName": "Otra Persona"},
                        headers=h)
    assert candidate_in(r.json()["state"], r.json()["candidateId"])["aiStatus"] == "En cola"

    assert client.post("/api/candidates", json={**body, "fullName": " "}, headers=h).status_code == 422
    assert client.post("/api/candidates", json={**body, "positionId": "nope"}, headers=h).status_code == 422


def test_rename_position_folder_updates_paths(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    data = make_cv_pdf(**JUAN)
    res = upload_cv(client, h, data, "cv.pdf", pos["id"], src["id"]).json()["result"]
    r = client.patch(f"/api/positions/{pos['id']}", json={"folderName": "Planta Concentradora"}, headers=h)
    assert r.status_code == 200
    cand = candidate_in(r.json()["state"], res["candidateId"])
    assert cand["cvPath"] == "planta-concentradora/portal-minero-peru/cv.pdf"
    assert db.get(CvFile, res["cvFileId"]).stored_path == "planta-concentradora/portal-minero-peru/cv.pdf"
    d = client.get(f"/api/cv-files/{res['cvFileId']}/download", headers=h)
    assert d.status_code == 200 and d.content == data


def test_rename_failure_keeps_paths_and_folder(client, db, make_user, rrhh_root, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    _, h = make_user()
    (pos,), src = _org(client, h)
    res = upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"]).json()["result"]

    def boom(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr("app.routers.positions.log_action", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.patch(f"/api/positions/{pos['id']}", json={"folderName": "otra"}, headers=h)
    assert r.status_code == 500
    monkeypatch.undo()
    assert (rrhh_root / "operador-de-planta" / "portal-minero-peru" / "cv.pdf").exists()
    db.expire_all()
    assert db.get(CvFile, res["cvFileId"]).stored_path == "operador-de-planta/portal-minero-peru/cv.pdf"


def test_position_with_candidates_cannot_be_deleted(client, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    upload_cv(client, h, make_cv_pdf(**JUAN), "cv.pdf", pos["id"], src["id"])
    r = client.delete(f"/api/positions/{pos['id']}", headers=h)
    assert r.status_code == 409


def test_counts_in_state(client, db, make_user, rrhh_root):
    _, h = make_user()
    (pos,), src = _org(client, h)
    req = create_requirement(client, h, pos["id"], quantity=2)
    a = upload_cv(client, h, make_cv_pdf(**JUAN), "a.pdf", pos["id"], src["id"]).json()["result"]
    b = upload_cv(client, h, make_cv_pdf(**ROSA), "b.pdf", pos["id"], src["id"]).json()["result"]
    db.get(Candidate, a["candidateId"]).decision = "Contratado"
    db.get(Candidate, b["candidateId"]).decision = "Aprobado"
    db.flush()
    s = client.get("/api/state", headers=h).json()
    assert s["positions"][0]["candidatesCount"] == 2
    board = s["jobBoards"][0]
    assert (board["candidatesReceived"], board["shortlistedCount"], board["hiredCount"]) == (2, 2, 1)
    assert s["jobNeeds"][0]["filledCount"] == 1
    assert s["kpis"]["filledVacancies"] == 1 and s["kpis"]["preselectedOrHired"] == 2

    db.get(Candidate, b["candidateId"]).decision = "Contratado"
    db.flush()
    r = client.patch(f"/api/requirements/{req['id']}", json={"quantity": 1}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"] == "La cantidad no puede ser menor que los 2 contratado(s)"


def test_cv_routes_require_auth(client):
    assert client.post("/api/cv-files/check", json={"items": []}).status_code == 401
    assert client.post("/api/cv-files").status_code == 401
    assert client.delete("/api/cv-files/x").status_code == 401
    assert client.patch("/api/persons/x", json={}).status_code == 401
    assert client.post("/api/candidates", json={}).status_code == 401
