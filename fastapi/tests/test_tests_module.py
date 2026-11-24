import io

from openpyxl import Workbook, load_workbook
from sqlalchemy import select

from app.models.audit import AuditLog
from tests.fixtures.cvs import candidate_in
from tests.test_classifier import make_queued_candidate

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
Q3 = ["Dominio de la molienda SAG", "Lectura de planos de planta", "Control de variables operativas"]


def _setup(client, db, make_user, settings_override, rrhh_root):
    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override)
    return cand, h


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def _create_test(client, h, name="Prueba de planta", category="Técnica Minera", questions=Q3, passing=70):
    r = client.post("/api/recruitment/tests", json={
        "name": name, "category": category, "targetArea": "Planta", "durationMinutes": 20,
        "passingScore": passing, "questions": questions}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["test"]


def _xlsx(rows, header=("Prueba Evaluada", "Pregunta", "Respuesta")) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Prueba"
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _filled_template(client, h, test_id, cand_id, answers):
    r = client.get(f"/api/tests/excel-template?testId={test_id}&candidateId={cand_id}", headers=h)
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb["Prueba"]
    assert [c.value for c in ws[1]] == ["Prueba Evaluada", "Candidato", "Pregunta", "Respuesta", "Escala Máxima"]
    for row, a in zip(ws.iter_rows(min_row=2), answers):
        assert row[3].value is None and row[4].value == 5
        row[3].value = a
    out = io.BytesIO()
    wb.save(out)
    return r, out.getvalue()


def _upload(client, h, data, cand_id, test_id=None, test_name="", filename="resultado.xlsx"):
    form = {"candidateId": cand_id, "testName": test_name}
    if test_id:
        form["testId"] = test_id
    return client.post("/api/recruitment/tests/upload-excel", files={"file": (filename, data, XLSX)}, data=form,
                       headers=h)


def test_send_and_submit_psych(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    r = client.post("/api/recruitment/psych-tests/send",
                    json={"candidateId": cand.id, "testBatteryName": "Batería HSEC"}, headers=h)
    assert r.status_code == 200, r.text
    ev = candidate_in(r.json()["state"], cand.id)["psychEvaluation"]
    assert ev["status"] == "Enviada" and ev["accessCode"] == "PL-PS-0001" and ev["sentBy"]
    r = client.post(f"/api/recruitment/psych-tests/{cand.id}/submit", json={"answers": {
        "estabilidad": 5, "tolerancia": 4, "seguridad": 5, "equipo": 4, "razonamiento": 5}}, headers=h)
    assert r.status_code == 200, r.text
    c = candidate_in(r.json()["state"], cand.id)
    ev = c["psychEvaluation"]
    assert ev["status"] == "Completada" and ev["averageScore"] and ev["aptitudeLevel"] == "Apto Recomendado"
    assert ev["accessCode"] == "PL-PS-0001" and ev["testBatteryName"] == "Batería HSEC"
    assert c["metricReport"]["psychScore"] == ev["averageScore"]
    assert len(_logs(db, "psych.send")) == 1 and len(_logs(db, "psych.submit")) == 1


def test_template_roundtrip(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    test = _create_test(client, h)
    resp, data = _filled_template(client, h, test["id"], cand.id, [5, 4, 5])
    assert "Prueba_prueba-de-planta_juan-carlos-quispe-mamani.xlsx" in resp.headers["content-disposition"]
    r = _upload(client, h, data, cand.id, test_id=test["id"])
    assert r.status_code == 200, r.text
    res = r.json()["excelResult"]
    assert res["concreteVerdict"] == "Resultados Concretos" and res["answeredCount"] == 3
    assert res["testId"] == test["id"] and len(res["parsedRows"]) == 3
    shown = candidate_in(r.json()["state"], cand.id)["excelTestResults"]
    assert len(shown) == 1 and shown[0]["parsedRows"] == [] and shown[0]["passingScore"] == 70
    assert len(_logs(db, "test.upload_result")) == 1


def test_default_template_questions(client, db, make_user, settings_override, rrhh_root):
    _, h = _setup(client, db, make_user, settings_override, rrhh_root)
    r = client.get("/api/tests/excel-template", headers=h)
    ws = load_workbook(io.BytesIO(r.content))["Prueba"]
    assert [row[2].value for row in ws.iter_rows(min_row=2)] == [
        "Estabilidad operativa bajo presión en faena", "Cumplimiento estricto de normas HSEC y PETAR",
        "Dominio técnico del puesto minero", "Coordinación efectiva en guardia 14x7"]


def test_upload_empty_template_registered_only(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    test = _create_test(client, h)
    _, data = _filled_template(client, h, test["id"], cand.id, [None, None, None])
    r = _upload(client, h, data, cand.id, test_id=test["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registeredOnly"] is True and body["message"] and "excelResult" not in body
    assert candidate_in(body["state"], cand.id)["excelTestResults"] == []


def test_import_excel_detects_name_category(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    data = _xlsx([("Examen Seguridad HSEC Tajo", "Norma DS-024-2016-EM", 5),
                  ("Examen Seguridad HSEC Tajo", "Uso de IPERC Continuo", 4)])
    r = client.post("/api/recruitment/tests/import-excel", files={"file": ("examen_hsec.xlsx", data, XLSX)},
                    data={"candidateId": cand.id}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["isNewTest"] is True and body["test"]["name"] == "Examen Seguridad HSEC Tajo"
    assert body["test"]["category"] == "Seguridad HSEC" and len(body["test"]["questions"]) == 2
    assert body["test"]["sourceFileName"] == "examen_hsec.xlsx"
    assert body["excelResult"]["answeredCount"] == 2
    assert [t["id"] for t in body["state"]["testCatalog"]] == [body["test"]["id"]]
    again = client.post("/api/recruitment/tests/import-excel", files={"file": ("examen_hsec.xlsx", data, XLSX)},
                        headers=h)
    assert again.json()["isNewTest"] is False
    assert len(_logs(db, "test.import")) == 1


def test_psicolaboral_result_updates_person_psych(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    qs = ["Estabilidad emocional bajo presión", "Trabajo en equipo en guardia", "Cumplimiento de normas de seguridad"]
    test = _create_test(client, h, name="Perfil psicolaboral minero", category="Psicolaboral", questions=qs)
    _, data = _filled_template(client, h, test["id"], cand.id, [5, 4, 5])
    r = _upload(client, h, data, cand.id, test_id=test["id"])
    assert r.status_code == 200, r.text
    c = candidate_in(r.json()["state"], cand.id)
    ev = c["psychEvaluation"]
    assert ev["status"] == "Completada" and ev["testBatteryName"] == "Perfil psicolaboral minero"
    assert ev["averageScore"] and set(ev["scores"]) >= {"estabilidadEmocional", "trabajoEquipo"}
    assert c["metricReport"]["psychScore"] == ev["averageScore"]


def test_passed_uses_passing_score(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    hard = _create_test(client, h, name="Prueba difícil", passing=95)
    easy = _create_test(client, h, name="Prueba fácil", passing=80)
    _, d1 = _filled_template(client, h, hard["id"], cand.id, [4, 4, 4])  # 86
    _, d2 = _filled_template(client, h, easy["id"], cand.id, [4, 4, 4])
    assert _upload(client, h, d1, cand.id, test_id=hard["id"]).json()["excelResult"]["passed"] is False
    assert _upload(client, h, d2, cand.id, test_id=easy["id"]).json()["excelResult"]["passed"] is True


def test_delete_test_logged(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    test = _create_test(client, h)
    _, data = _filled_template(client, h, test["id"], cand.id, [5, 5, 5])
    _upload(client, h, data, cand.id, test_id=test["id"])
    r = client.delete(f"/api/recruitment/tests/{test['id']}", headers=h)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["testCatalog"] == []
    assert candidate_in(state, cand.id)["excelTestResults"][0]["testId"] is None  # el resultado se conserva
    assert len(_logs(db, "test.create")) == 1 and len(_logs(db, "test.delete")) == 1
    assert client.delete(f"/api/recruitment/tests/{test['id']}", headers=h).status_code == 404


def test_bad_excel_is_422(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    r = _upload(client, h, b"no es un excel", cand.id, test_name="X")
    assert r.status_code == 422


def test_template_neutralizes_formulas(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    test = _create_test(client, h, name="=cmd|' /C calc'!A0", questions=['=HYPERLINK("http://x","clic")', "+1+1"])
    r = client.get(f"/api/tests/excel-template?testId={test['id']}&candidateId={cand.id}", headers=h)
    ws = load_workbook(io.BytesIO(r.content))["Prueba"]
    for row in ws.iter_rows(min_row=2):
        for cell in row[:3]:
            assert cell.data_type != "f" and not str(cell.value).startswith("=")
    assert ws["C2"].value == "'=HYPERLINK(\"http://x\",\"clic\")"
