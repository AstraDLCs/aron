from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from sqlalchemy import select

from app import worker
from app.models.audit import AuditLog
from app.models.people import Candidate, Person
from app.models.settings import AppSettings
from app.routers import settings as settings_router
from app.services.openrouter import OpenRouterClient
from tests.fixtures.cvs import create_position, create_source, make_cv_pdf, upload_cv
from tests.test_classifier import BASE, ai_payload, completion, make_queued_candidate

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
CLIENT = OpenRouterClient("test-key")


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def test_upload_with_ai_available_is_queued(client, db, make_user, settings_override, rrhh_root):
    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override)
    assert cand.ai_status == "En cola"
    with settings_override(openrouter_api_key="test-key"):
        queue = client.get("/api/ai/queue", headers=h).json()
    assert queue["queued"] == 1 and queue["aiEnabled"] is True and queue["pausedUntil"] is None
    assert queue["model"] and set(queue) == {
        "queued", "processing", "errors", "sinIa", "pausedUntil", "aiEnabled", "model",
        "workerSeenAt", "workerStatus", "nextAttemptAt", "lastError",
    }


def test_worker_processes_and_audits(client, db, make_user, settings_override, rrhh_root):
    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override, email="")
    person = db.get(Person, cand.person_id)
    assert person.email == ""
    r = client.patch(f"/api/persons/{person.id}", json={"phone": "999 000 111"}, headers=h)
    assert r.status_code == 200
    with respx.mock:
        respx.post(BASE).mock(return_value=completion(ai_payload(datosPersonales={
            **ai_payload()["datosPersonales"], "email": "ia@correo.pe", "telefono": "111 222 333"})))
        assert worker.process_one(db, CLIENT, NOW) == "processed"
    db.refresh(cand)
    assert cand.ai_status == "Clasificado"
    db.refresh(person)
    assert person.email == "ia@correo.pe"  # la IA llena el vacío
    assert person.phone == "999 000 111"  # y no pisa lo que editó un usuario
    log = _logs(db, "ai.classify")[0]
    assert log.user_name == "Sistema (IA)"
    assert worker.process_one(db, CLIENT, NOW) == "idle"
    assert worker.process_one(db, None, NOW) == "idle"


def test_worker_daily_limit_pauses_queue(client, db, make_user, settings_override, rrhh_root):
    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override)
    reset = NOW + timedelta(hours=6)
    with respx.mock:
        route = respx.post(BASE).mock(return_value=httpx.Response(
            429, json={"error": {"message": "free-models-per-day"}},
            headers={"X-RateLimit-Reset": str(int(reset.timestamp() * 1000))},
        ))
        assert worker.process_one(db, CLIENT, NOW) == "paused"
        assert worker.process_one(db, CLIENT, NOW + timedelta(hours=1)) == "paused"  # ni llama al modelo
        assert route.call_count == 1
        db.refresh(cand)
        assert cand.ai_status == "En cola" and cand.ai_attempts == 0
        with settings_override(openrouter_api_key="test-key"):
            assert client.get("/api/ai/queue", headers=h).json()["pausedUntil"] is not None
        assert len(_logs(db, "ai.daily_limit")) == 1

        route.mock(return_value=completion(ai_payload()))
        assert worker.process_one(db, CLIENT, reset + timedelta(minutes=1)) == "processed"
    db.refresh(cand)
    assert cand.ai_status == "Clasificado"
    assert db.get(AppSettings, 1).ai_paused_until is None


def test_worker_daily_limit_logs_only_when_date_changes(client, db, make_user, settings_override, rrhh_root):
    make_queued_candidate(client, db, make_user, settings_override)
    reset = NOW + timedelta(hours=6)
    with respx.mock:
        respx.post(BASE).mock(return_value=httpx.Response(
            429, json={"error": {"message": "per-day"}}, headers={"X-RateLimit-Reset": str(int(reset.timestamp() * 1000))},
        ))
        worker.process_one(db, CLIENT, NOW)
        db.get(AppSettings, 1).ai_paused_until = None
        db.flush()
        worker.process_one(db, CLIENT, NOW)  # misma fecha de reinicio, pero cambió respecto de lo guardado
    assert len(_logs(db, "ai.daily_limit")) == 2


def test_worker_per_minute_limit_defers_without_attempt(client, db, make_user, settings_override, rrhh_root):
    cand, _, _ = make_queued_candidate(client, db, make_user, settings_override)
    with respx.mock:
        respx.post(BASE).mock(return_value=httpx.Response(429, json={"error": {"message": "per-min"}},
                                                          headers={"Retry-After": "20"}))
        assert worker.process_one(db, CLIENT, NOW) == "paused"
    db.refresh(cand)
    assert cand.ai_status == "En cola" and cand.ai_attempts == 0
    assert cand.ai_next_attempt_at == NOW + timedelta(seconds=20)
    assert worker.process_one(db, CLIENT, NOW + timedelta(seconds=5)) == "idle"  # todavía no le toca


def test_worker_retries_then_error_and_requeue(client, db, make_user, settings_override, rrhh_root):
    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override)
    with respx.mock:
        respx.post(BASE).mock(return_value=httpx.Response(500, json={"error": {"message": "caído"}}))
        assert worker.process_one(db, CLIENT, NOW) == "error"
        db.refresh(cand)
        assert cand.ai_status == "En cola" and cand.ai_attempts == 1
        assert cand.ai_next_attempt_at == NOW + timedelta(seconds=60)  # 30·2^1
        assert worker.process_one(db, CLIENT, NOW) == "idle"  # aún no vence

        assert worker.process_one(db, CLIENT, NOW + timedelta(seconds=61)) == "error"
        db.refresh(cand)
        assert cand.ai_attempts == 2 and cand.ai_next_attempt_at == NOW + timedelta(seconds=61 + 120)

        assert worker.process_one(db, CLIENT, NOW + timedelta(seconds=500)) == "error"
    db.refresh(cand)
    assert cand.ai_status == "Error IA" and cand.ai_attempts == 3 and "500" in cand.ai_error
    assert len(_logs(db, "ai.classify_error")) == 1
    assert _logs(db, "ai.classify_error")[0].user_name == "Sistema (IA)"

    with settings_override(openrouter_api_key="test-key"):
        r = client.post("/api/ai/queue/retry-errors", headers=h)
    assert r.status_code == 200 and r.json()["state"]["aiQueue"]["queued"] == 1
    db.refresh(cand)
    assert cand.ai_status == "En cola" and cand.ai_attempts == 0 and cand.ai_error is None
    assert len(_logs(db, "ai.requeue")) == 1


def test_retry_errors_includes_sin_ia_only_when_available(client, db, make_user, settings_override, rrhh_root):
    _, h = make_user()
    pos, src = create_position(client, h, "Operador"), create_source(client, h, "Portal")
    res = upload_cv(client, h, make_cv_pdf("Rosa Elena Huamán Torres", "70011223", "rosa@x.pe", "955 111 222"),
                    "cv.pdf", pos["id"], src["id"]).json()["result"]
    cand = db.get(Candidate, res["candidateId"])
    assert cand.ai_status == "Sin IA"
    client.post("/api/ai/queue/retry-errors", headers=h)
    db.refresh(cand)
    assert cand.ai_status == "Sin IA"  # sin clave no hay a dónde encolar
    with settings_override(openrouter_api_key="test-key"):
        client.post("/api/ai/queue/retry-errors", headers=h)
    db.refresh(cand)
    assert cand.ai_status == "En cola"


def test_recover_stuck_processing(client, db, make_user, settings_override, rrhh_root):
    cand, _, _ = make_queued_candidate(client, db, make_user, settings_override)
    cand.ai_status = "Procesando"
    db.flush()
    assert worker.recover_stuck(db) == 1
    db.refresh(cand)
    assert cand.ai_status == "En cola"
    assert worker.recover_stuck(db) == 0


def test_ai_links_person_by_extracted_dni(client, db, make_user, settings_override, rrhh_root):
    cand_a, h, pos = make_queued_candidate(client, db, make_user, settings_override)
    src = create_source(client, h, "Otra fuente")
    other = make_cv_pdf("Pedro Ramos Díaz", "11112222", "pedro@x.pe", "944 000 111")
    with settings_override(openrouter_api_key="test-key"):
        res = upload_cv(client, h, other, "pedro.pdf", pos["id"], src["id"]).json()["result"]
    cand_b = db.get(Candidate, res["candidateId"])
    assert cand_b.person_id != cand_a.person_id
    # el CV de B trae un DNI distinto al de A, pero la IA lee el DNI de A
    with respx.mock:
        respx.post(BASE).mock(return_value=completion(ai_payload(datosPersonales={
            **ai_payload()["datosPersonales"], "documento": "11112222", "email": "otro@x.pe"})))
        assert worker.process_one(db, CLIENT, NOW) == "processed"  # A (la más antigua)
    person_a, person_b = db.get(Person, cand_a.person_id), db.get(Person, cand_b.person_id)
    assert person_a.document_id == "11112222"
    assert person_a.id != person_b.id and db.get(Person, person_b.id) is not None  # nada se une solo
    assert person_b.id in person_a.possible_same_person_ids and person_a.id in person_b.possible_same_person_ids
    log = _logs(db, "person.possible_same")[0]
    assert log.user_name == "Sistema (IA)" and log.details["reason"] == "mismo documento"
    assert not _logs(db, "person.merge")


def test_ai_models_endpoint_cached_and_needs_key(client, make_user, settings_override):
    _, h = make_user()
    settings_router.reset_models_cache()
    assert client.get("/api/settings/ai-models", headers=h).status_code == 503
    assert "falta OPENROUTER_API_KEY" in client.get("/api/settings/ai-models", headers=h).json()["detail"]
    with settings_override(openrouter_api_key="test-key"), respx.mock:
        route = respx.get("https://openrouter.ai/api/v1/models").mock(return_value=httpx.Response(200, json={"data": [
            {"id": "a/gratis:free", "name": "Gratis", "context_length": 40000, "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "b/paga", "name": "Paga", "context_length": 8000, "pricing": {"prompt": "1", "completion": "1"}},
        ]}))
        first = client.get("/api/settings/ai-models", headers=h).json()
        client.get("/api/settings/ai-models", headers=h)
    assert first == {"models": [{"id": "a/gratis:free", "name": "Gratis", "contextLength": 40000}]}
    assert route.call_count == 1  # la segunda salió de la memoria
    settings_router.reset_models_cache()


def test_settings_only_free_models(client, make_user):
    _, h = make_user()
    settings_router.reset_models_cache()
    r = client.patch("/api/settings", json={"aiModel": "openai/gpt-4o"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"] == "Solo se permiten modelos gratuitos"
    r = client.patch("/api/settings", json={"aiFallbackModels": ["a/gratis:free", "b/paga"]}, headers=h)
    assert r.status_code == 422
    r = client.patch("/api/settings", json={"aiModel": "a/gratis:free", "aiFallbackModels": ["b/otro:free"]}, headers=h)
    assert r.status_code == 200 and r.json()["state"]["settings"]["aiModel"] == "a/gratis:free"


def test_default_model_when_settings_empty(client, make_user):
    from app.config import DEFAULT_AI_FALLBACK_MODELS, DEFAULT_AI_MODEL

    _, h = make_user()
    s = client.get("/api/state", headers=h).json()
    assert s["settings"]["aiModel"] == s["aiQueue"]["model"] == DEFAULT_AI_MODEL
    assert s["settings"]["aiFallbackModels"] == DEFAULT_AI_FALLBACK_MODELS
    assert DEFAULT_AI_MODEL.endswith(":free") and all(m.endswith(":free") for m in DEFAULT_AI_FALLBACK_MODELS)


def test_reclassify_candidate_and_position(client, db, make_user, settings_override, rrhh_root):
    cand, h, pos = make_queued_candidate(client, db, make_user, settings_override)
    with respx.mock:
        respx.post(BASE).mock(return_value=completion(ai_payload()))
        worker.process_one(db, CLIENT, NOW)
    db.refresh(cand)
    assert cand.ai_status == "Clasificado"
    assert client.post(f"/api/candidates/{cand.id}/reclassify", headers=h).status_code == 409  # sin IA configurada
    with settings_override(openrouter_api_key="test-key"):
        r = client.post(f"/api/candidates/{cand.id}/reclassify", headers=h)
        assert r.status_code == 200
        db.refresh(cand)
        assert cand.ai_status == "En cola" and cand.ai_verdict is None and cand.ai_model is None
        assert client.post("/api/candidates/no-existe/reclassify", headers=h).status_code == 404
        cand.ai_status = "Clasificado"
        db.flush()
        r = client.post(f"/api/positions/{pos['id']}/reclassify", headers=h)
        assert r.status_code == 200 and r.json()["requeued"] == 1
    db.refresh(cand)
    assert cand.ai_status == "En cola"
    assert len(_logs(db, "candidate.reclassify")) == 1 and len(_logs(db, "position.reclassify")) == 1


class _StopLoop(BaseException):
    pass


def test_run_forever_survives_iteration_errors(monkeypatch):
    import app.db

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(app.db, "SessionLocal", FakeSession)
    monkeypatch.setattr(worker, "recover_stuck", lambda db: 0)
    monkeypatch.setattr(worker, "make_client", lambda: None)
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    outcomes = iter([RuntimeError("falla"), "idle", _StopLoop()])

    def fake_process_one(db, client, now):
        item = next(outcomes)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(worker, "process_one", fake_process_one)
    with pytest.raises(_StopLoop):
        worker.run_forever()
    assert next(outcomes, None) is None  # llegó hasta el final: la primera excepción no lo detuvo


def _worker_row(db):
    db.expire_all()
    return db.get(AppSettings, 1)


def test_worker_reports_what_it_is_doing(client, db, make_user, settings_override, rrhh_root):
    assert worker.process_one(db, None, NOW) == "idle"
    row = _worker_row(db)
    assert row.worker_status == worker.STATUS_NO_KEY and row.worker_seen_at == NOW
    assert worker.process_one(db, CLIENT, NOW) == "idle"
    assert _worker_row(db).worker_status == worker.STATUS_EMPTY

    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override)
    with respx.mock:
        respx.post(BASE).mock(return_value=completion(ai_payload()))
        assert worker.process_one(db, CLIENT, NOW) == "processed"
    status = _worker_row(db).worker_status
    assert status.startswith("Clasificó a ") and " con " in status
    q = client.get("/api/state", headers=h).json()["aiQueue"]
    assert q["workerStatus"] == status and q["workerSeenAt"]


def test_saturated_models_leave_the_reason_visible(client, db, make_user, settings_override, rrhh_root):
    cand, h, _ = make_queued_candidate(client, db, make_user, settings_override)
    with respx.mock:
        route = respx.post(BASE).mock(return_value=httpx.Response(
            429, json={"error": {"message": "x is temporarily rate-limited upstream"}}, headers={"Retry-After": "30"}))
        assert worker.process_one(db, CLIENT, NOW) == "paused"
        assert route.call_count > 1  # probó los modelos de respaldo antes de esperar
    db.refresh(cand)
    assert cand.ai_status == "En cola" and cand.ai_attempts == 0  # esperar no gasta intentos
    assert "saturados" in cand.ai_error
    assert _worker_row(db).worker_status.startswith("Modelos saturados al clasificar a ")
    assert worker.process_one(db, CLIENT, NOW) == "idle"  # todavía no le toca reintentar
    assert _worker_row(db).worker_status == worker.STATUS_WAITING
    q = client.get("/api/ai/queue", headers=h).json()
    assert q["queued"] == 1 and "saturados" in q["lastError"] and q["workerStatus"] == worker.STATUS_WAITING


def test_default_chain_is_appended_to_configured_models(db):
    from app.config import DEFAULT_AI_MODEL
    from app.services.app_settings import fallback_chain, get_app_settings

    row = get_app_settings(db)
    row.ai_model, row.ai_fallback_models = "google/gemma-4-31b-it:free", ["otro/modelo:free"]
    chain = fallback_chain(row)
    assert chain[0] == "otro/modelo:free" and DEFAULT_AI_MODEL in chain
    assert "google/gemma-4-31b-it:free" not in chain and len(chain) <= 5
