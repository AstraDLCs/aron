from sqlalchemy import select

from app.models.audit import AuditLog
from tests.fixtures.cvs import create_position, create_source, make_cv_pdf, upload_cv


def _setup(client, h, names=("Juan Carlos Quispe Mamani",)):
    pos = create_position(client, h, "Operador de Planta")
    src = create_source(client, h, "Portal Minero Perú")
    ids = []
    for i, name in enumerate(names):
        r = upload_cv(client, h, make_cv_pdf(name, f"4567891{i}", f"p{i}@correo.pe", f"98765432{i}"),
                      f"cv{i}.pdf", pos["id"], src["id"])
        assert r.status_code == 201, r.text
        ids.append(r.json()["result"]["candidateId"])
    return pos, src, ids


def test_candidates_csv_and_admin_doc(client, make_user, rrhh_root):
    _, h = make_user()
    _setup(client, h)
    r = client.get("/api/reports/candidates-csv", headers=h)
    assert r.status_code == 200
    text = r.content.decode("utf-8")
    assert text.startswith("\ufeff")
    assert "Universidad / Instituto" in text and "Seguridad HSEC" in text
    assert "Estado IA" in text and "Veredicto IA" in text and "Puntaje Aptitud IA" in text
    assert "Decidido por" in text and "\r\n" in text
    k = client.get("/api/reports/kpis-csv", headers=h)
    assert k.content.decode("utf-8").startswith("\ufeff")
    assert "Compañía Minera Las Bravas" in k.content.decode("utf-8")
    d = client.get("/api/reports/admin-doc", headers=h)
    assert d.headers["content-type"].startswith("application/msword")
    html = d.content.decode("utf-8")
    assert "Compañía Minera Las Bravas" in html and "Ranking de Bolsas de Trabajo" in html
    assert "Informe_Ejecutivo_" in d.headers["content-disposition"]


def test_candidate_doc_shows_decider(client, make_user, rrhh_root):
    _, h = make_user()
    _, _, ids = _setup(client, h)
    assert client.post(f"/api/candidates/{ids[0]}/decision", json={"decision": "Aprobado"}, headers=h).status_code == 200
    r = client.get(f"/api/reports/candidate/{ids[0]}/doc", headers=h)
    assert r.status_code == 200
    html = r.content.decode("utf-8")
    assert "Dictamen Consolidado de la IA para Gerencia General" in html
    assert "Ana Torres" in html and "Aprobado" in html
    assert "Ficha_juan-carlos-quispe-mamani.doc" in r.headers["content-disposition"]
    assert client.get("/api/reports/candidate/no-existe/doc", headers=h).status_code == 404


def test_report_downloads_are_logged(client, db, make_user, rrhh_root):
    _, h = make_user()
    _, _, ids = _setup(client, h)
    for url in ("/api/reports/admin-doc", f"/api/reports/candidate/{ids[0]}/doc", "/api/reports/candidates-csv",
                "/api/reports/kpis-csv"):
        assert client.get(url, headers=h).status_code == 200
    logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "report.download").order_by(AuditLog.id)))
    assert [r.details["report"] for r in logs] == ["admin-doc", "candidate-doc", "candidates-csv", "kpis-csv"]
    assert client.get("/api/reports/admin-doc").status_code == 401
