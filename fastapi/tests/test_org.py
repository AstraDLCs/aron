import pytest
from sqlalchemy import select

from app.models.audit import AuditLog


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def _pos(client, h, name, area="Mina", **kw):
    r = client.post("/api/positions", json={"name": name, "area": area, **kw}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["position"]


def test_create_position_tree_and_folder_name(client, db, make_user, rrhh_root):
    _, h = make_user()
    root = _pos(client, h, "Gerencia General", area="Gerencia")
    r = client.post(
        "/api/positions",
        json={"name": "Superintendencia de Mina", "area": "Mina", "parentId": root["id"]},
        headers=h,
    )
    assert r.status_code == 201
    child = r.json()["position"]
    assert child["folderName"] == "superintendencia-de-mina"
    assert child["parentId"] == root["id"]
    assert len(r.json()["state"]["positions"]) == 2
    logs = _logs(db, "position.create")
    assert len(logs) == 2
    assert logs[1].summary == "Creó el puesto Superintendencia de Mina"
    assert logs[1].user_name == "Ana Torres" and logs[1].entity_type == "position"
    assert logs[1].entity_id == child["id"]


def test_position_duplicates_409(client, make_user, rrhh_root):
    _, h = make_user()
    _pos(client, h, "Jefe de Planta")
    r = client.post("/api/positions", json={"name": "Jefe de Planta", "area": "Planta"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "Ya existe un puesto con ese nombre"
    r = client.post("/api/positions", json={"name": "Otro", "folderName": "Jefe de Planta", "area": "x"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "Ya existe un puesto con esa carpeta"
    r = client.post("/api/positions", json={"name": "Otro", "area": "x", "parentId": "no-existe"}, headers=h)
    assert r.status_code == 422


def test_position_cycle_rejected(client, make_user, rrhh_root):
    _, h = make_user()
    a = _pos(client, h, "A")
    b = _pos(client, h, "B", parentId=a["id"])
    c = _pos(client, h, "C", parentId=b["id"])
    r = client.patch(f"/api/positions/{a['id']}", json={"parentId": c["id"]}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"] == "No se puede mover un puesto debajo de sí mismo o de un subordinado"
    r = client.patch(f"/api/positions/{a['id']}", json={"parentId": a["id"]}, headers=h)
    assert r.status_code == 422


def test_position_patch_move_and_update(client, db, make_user, rrhh_root):
    _, h = make_user()
    a = _pos(client, h, "A")
    b = _pos(client, h, "B")
    r = client.patch(f"/api/positions/{b['id']}", json={"parentId": a["id"]}, headers=h)
    assert r.status_code == 200 and r.json()["position"]["parentId"] == a["id"]
    assert len(_logs(db, "position.move")) == 1
    r = client.patch(f"/api/positions/{b['id']}", json={"description": "desc", "minYearsExperience": 5}, headers=h)
    assert r.json()["position"]["description"] == "desc"
    assert r.json()["position"]["parentId"] == a["id"]  # no se tocó
    assert len(_logs(db, "position.update")) == 1
    r = client.patch(f"/api/positions/{b['id']}", json={"parentId": None}, headers=h)
    assert r.json()["position"]["parentId"] is None
    assert client.patch("/api/positions/xx", json={"area": "z"}, headers=h).status_code == 404


def test_position_folder_rename_moves_dir(client, make_user, rrhh_root):
    _, h = make_user()
    p = _pos(client, h, "Jefe de Planta")
    (rrhh_root / "jefe-de-planta" / "portal").mkdir(parents=True)
    (rrhh_root / "jefe-de-planta" / "portal" / "a.pdf").write_bytes(b"x")
    r = client.patch(f"/api/positions/{p['id']}", json={"folderName": "Jefatura Planta"}, headers=h)
    assert r.status_code == 200 and r.json()["position"]["folderName"] == "jefatura-planta"
    assert (rrhh_root / "jefatura-planta" / "portal" / "a.pdf").exists()
    assert not (rrhh_root / "jefe-de-planta").exists()


def test_delete_position_restrictions(client, db, make_user, rrhh_root):
    _, h = make_user()
    parent = _pos(client, h, "Padre")
    child = _pos(client, h, "Hijo", parentId=parent["id"])
    msg = "El puesto tiene subordinados, requerimientos o candidatos"
    r = client.delete(f"/api/positions/{parent['id']}", headers=h)
    assert r.status_code == 409 and r.json()["detail"] == msg

    q = client.post("/api/requirements", json={"positionId": child["id"], "quantity": 1, "urgency": "Media"}, headers=h)
    assert q.status_code == 201
    r = client.delete(f"/api/positions/{child['id']}", headers=h)
    assert r.status_code == 409 and r.json()["detail"] == msg

    leaf = _pos(client, h, "Hoja")
    r = client.delete(f"/api/positions/{leaf['id']}", headers=h)
    assert r.status_code == 200
    assert all(p["id"] != leaf["id"] for p in r.json()["state"]["positions"])
    assert len(_logs(db, "position.delete")) == 1
    assert client.delete(f"/api/positions/{leaf['id']}", headers=h).status_code == 404


def test_requirement_crud_and_state_shape(client, db, make_user, rrhh_root):
    _, h = make_user()
    pos = _pos(client, h, "Superintendente de Mina", area="Mina", requiredSkills="ventilación, voladura",
               technicalSpecifications="DS-024")
    r = client.post(
        "/api/requirements",
        json={"positionId": pos["id"], "quantity": 2, "urgency": "Urgente", "context": "Expansión",
              "extraSkills": "SUCAMEC"},
        headers=h,
    )
    assert r.status_code == 201
    state = r.json()["state"]
    need = state["jobNeeds"][0]
    assert set(need) == {
        "id", "positionId", "title", "department", "urgency", "vacancies", "filledCount", "requiredSkills",
        "technicalSpecifications", "companyContext", "publishedBoards", "publishedSourceIds", "openedAt",
        "targetDaysToFill", "createdBy", "status", "extraSkills",
    }
    assert need["status"] == "Abierto" and need["filledCount"] == 0
    assert need["title"] == "Superintendente de Mina" and need["department"] == "Mina"
    assert need["vacancies"] == 2 and need["targetDaysToFill"] == 30
    assert need["requiredSkills"] == "ventilación, voladura, SUCAMEC"
    assert need["companyContext"] == "Expansión" and need["createdBy"] == "Ana Torres"
    assert need["publishedBoards"] == [] and need["extraSkills"] == "SUCAMEC"
    assert r.json()["requirement"]["id"] == need["id"]
    assert state["positions"][0]["openRequirementsCount"] == 1
    assert state["kpis"]["totalVacancies"] == 2
    assert len(_logs(db, "requirement.create")) == 1

    r = client.patch(f"/api/requirements/{need['id']}", json={"quantity": 3, "urgency": "Media"}, headers=h)
    assert r.status_code == 200 and r.json()["state"]["jobNeeds"][0]["vacancies"] == 3
    assert len(_logs(db, "requirement.update")) == 1

    r = client.patch(f"/api/requirements/{need['id']}", json={"status": "Cancelado"}, headers=h)
    assert r.json()["state"]["jobNeeds"][0]["status"] == "Cancelado"
    assert r.json()["state"]["kpis"]["totalVacancies"] == 0
    assert len(_logs(db, "requirement.cancel")) == 1
    assert r.json()["state"]["positions"][0]["openRequirementsCount"] == 0

    r = client.patch(f"/api/requirements/{need['id']}", json={"status": "Abierto"}, headers=h)
    assert r.json()["state"]["jobNeeds"][0]["status"] == "Abierto"
    assert client.patch(f"/api/requirements/{need['id']}", json={"status": "Cubierto"}, headers=h).status_code == 422


def test_requirement_validation(client, make_user, rrhh_root):
    _, h = make_user()
    pos = _pos(client, h, "X")
    base = {"positionId": pos["id"], "quantity": 1, "urgency": "Media"}
    assert client.post("/api/requirements", json={**base, "quantity": 0}, headers=h).status_code == 422
    assert client.post("/api/requirements", json={**base, "urgency": "Nunca"}, headers=h).status_code == 422
    assert client.post("/api/requirements", json={**base, "positionId": "nope"}, headers=h).status_code == 422
    assert client.post("/api/requirements", json={**base, "publishedSourceIds": ["nope"]}, headers=h).status_code == 422
    assert client.patch("/api/requirements/nope", json={"quantity": 2}, headers=h).status_code == 404


def test_source_crud(client, db, make_user, rrhh_root):
    _, h = make_user()
    r = client.post("/api/sources", json={"name": "Portal Minero Perú", "category": "Portal Minero"}, headers=h)
    assert r.status_code == 201
    src = r.json()["source"]
    assert src["folderName"] == "portal-minero-peru" and src["active"] is True
    board = r.json()["state"]["jobBoards"][0]
    assert set(board) == {
        "id", "name", "folderName", "category", "proposalsSent", "candidatesReceived", "shortlistedCount",
        "hiredCount", "avgResponseHours", "lastProposalAt", "active",
    }
    assert len(_logs(db, "source.create")) == 1
    r = client.post("/api/sources", json={"name": "Portal Minero Perú", "category": "Portal Minero"}, headers=h)
    assert r.status_code == 409
    r = client.post("/api/sources", json={"name": "Otra", "category": "Inventada"}, headers=h)
    assert r.status_code == 422
    r = client.patch(f"/api/sources/{src['id']}", json={"avgResponseHours": 12.5, "active": False}, headers=h)
    assert r.status_code == 200 and r.json()["source"]["avgResponseHours"] == 12.5
    assert r.json()["source"]["active"] is False
    assert len(_logs(db, "source.update")) == 1


def test_source_proposal(client, db, make_user, rrhh_root):
    _, h = make_user()
    pos = _pos(client, h, "Jefe")
    req = client.post("/api/requirements", json={"positionId": pos["id"], "quantity": 1, "urgency": "Media"},
                      headers=h).json()["requirement"]
    src = client.post("/api/sources", json={"name": "Red", "category": "Red Profesional"}, headers=h).json()["source"]
    assert src["proposalsSent"] == 0

    r = client.post(f"/api/sources/{src['id']}/proposals", json={"requirementId": req["id"]}, headers=h)
    assert r.status_code == 200
    state = r.json()["state"]
    assert state["jobBoards"][0]["proposalsSent"] == 1
    assert state["jobBoards"][0]["lastProposalAt"] is not None
    assert state["jobNeeds"][0]["publishedSourceIds"] == [src["id"]]
    assert state["jobNeeds"][0]["publishedBoards"] == ["Red"]
    assert state["kpis"]["totalProposalsSent"] == 1
    assert len(_logs(db, "source.proposal")) == 1

    # segunda propuesta: suma otra vez pero no duplica el id
    r = client.post(f"/api/sources/{src['id']}/proposals", json={"requirementId": req["id"]}, headers=h)
    assert r.json()["state"]["jobBoards"][0]["proposalsSent"] == 2
    assert r.json()["state"]["jobNeeds"][0]["publishedSourceIds"] == [src["id"]]
    assert client.post(f"/api/sources/{src['id']}/proposals", json={"requirementId": "x"}, headers=h).status_code == 404


def test_settings_patch_logged(client, db, make_user):
    _, h = make_user()
    s = client.get("/api/settings", headers=h).json()
    assert s["aiPreapproveThreshold"] == 70 and s["companyName"] == "Compañía Minera Las Bravas"
    r = client.patch("/api/settings", json={"aiPreapproveThreshold": 75, "aiModel": "m/uno",
                                            "aiFallbackModels": ["m/dos"]}, headers=h)
    assert r.status_code == 200
    assert r.json()["state"]["settings"]["aiPreapproveThreshold"] == 75
    assert r.json()["state"]["settings"]["aiFallbackModels"] == ["m/dos"]
    log = _logs(db, "settings.update")[0]
    assert log.entity_type == "settings"
    assert log.details["before"]["aiPreapproveThreshold"] == 70
    assert log.details["after"]["aiPreapproveThreshold"] == 75
    r = client.patch("/api/settings", json={"companyName": "Minera Nueva"}, headers=h)
    assert r.json()["state"]["companyName"] == "Minera Nueva"
    assert client.patch("/api/settings", json={"aiPreapproveThreshold": 101}, headers=h).status_code == 422
    assert client.patch("/api/settings", json={"companyName": "  "}, headers=h).status_code == 422


@pytest.mark.parametrize("method,path", [
    ("post", "/api/positions"), ("patch", "/api/settings"), ("post", "/api/requirements"),
    ("post", "/api/sources"), ("get", "/api/settings"),
])
def test_routes_require_auth(client, method, path):
    assert getattr(client, method)(path, **({} if method == "get" else {"json": {}})).status_code == 401


def test_folder_rename_onto_existing_position_folder_409(client, make_user, rrhh_root):
    _, h = make_user()
    a = _pos(client, h, "Puesto A")
    _pos(client, h, "Puesto B")
    (rrhh_root / "puesto-a" / "portal").mkdir(parents=True)
    r = client.patch(f"/api/positions/{a['id']}", json={"folderName": "Puesto B"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "Ya existe un puesto con esa carpeta"
    assert (rrhh_root / "puesto-a" / "portal").is_dir() and not (rrhh_root / "puesto-b").exists()


def test_folder_rename_onto_existing_disk_dir_409(client, make_user, rrhh_root):
    _, h = make_user()
    a = _pos(client, h, "Puesto A")
    (rrhh_root / "puesto-a").mkdir()
    (rrhh_root / "huerfana").mkdir()
    r = client.patch(f"/api/positions/{a['id']}", json={"folderName": "huerfana"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"] == "La carpeta de destino ya existe en el servidor"
    assert (rrhh_root / "puesto-a").is_dir()
    # la base no cambió
    s = client.get("/api/state", headers=h).json()
    assert s["positions"][0]["folderName"] == "puesto-a"


@pytest.mark.parametrize("target", ["app.routers.positions.log_action", "commit"])
def test_folder_rename_failure_after_move_restores_dir(client, db, make_user, rrhh_root, monkeypatch, target):
    from fastapi.testclient import TestClient

    from app.main import app

    _, h = make_user()
    a = _pos(client, h, "Puesto A")
    (rrhh_root / "puesto-a" / "portal").mkdir(parents=True)
    (rrhh_root / "puesto-a" / "portal" / "a.pdf").write_bytes(b"x")

    def boom(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    if target == "commit":
        monkeypatch.setattr(db, "commit", boom)
    else:
        monkeypatch.setattr(target, boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.patch(f"/api/positions/{a['id']}", json={"folderName": "nuevo"}, headers=h)
    assert r.status_code == 500
    assert (rrhh_root / "puesto-a" / "portal" / "a.pdf").exists()
    assert not (rrhh_root / "nuevo").exists()
    monkeypatch.undo()
    assert client.get("/api/state", headers=h).json()["positions"][0]["folderName"] == "puesto-a"
