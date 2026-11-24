from datetime import UTC, datetime

import httpx
import respx
from sqlalchemy import select

from app.models.ai import AiConversation
from app.models.audit import AuditLog
from app.models.criteria import RecruitmentCriterion
from tests.test_classifier import BASE, completion, make_queued_candidate

REPORT = {
    "recommendation": "Recomiendo avanzar a entrevista", "strengths": ["Molienda SAG"],
    "watchouts": ["Sin inglés"], "concreteSummary": "Operador con 8 años",
}


def _setup(client, db, make_user, settings_override, rrhh_root):
    cand, h, pos = make_queued_candidate(client, db, make_user, settings_override)
    return cand, h


def _evaluate(client, h, cand, settings_override):
    with settings_override(openrouter_api_key="test-key"), respx.mock:
        respx.post(BASE).mock(return_value=completion(REPORT))
        return client.post("/api/ai/evaluate-candidate", json={"candidateId": cand.id}, headers=h)


def _logs(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def test_evaluate_creates_structured_conversation(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    r = _evaluate(client, h, cand, settings_override)
    assert r.status_code == 200, r.text
    conv = r.json()["conversation"]
    assert conv["candidateId"] == cand.id and conv["candidateName"]
    assert conv["structuredReport"] == REPORT
    assert [m["role"] for m in conv["messages"]] == ["assistant"]
    assert "Recomiendo avanzar" in conv["messages"][0]["content"]
    assert any(c["id"] == conv["id"] for c in r.json()["state"]["aiConversations"])
    assert len(_logs(db, "ai.evaluate")) == 1


def test_chat_appends_and_sends_history(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    with settings_override(openrouter_api_key="test-key"), respx.mock:
        route = respx.post(BASE).mock(return_value=completion("Primera respuesta"))
        r1 = client.post("/api/ai/assistant-chat", json={"candidateId": cand.id, "message": "Pregunta uno"}, headers=h)
        assert r1.status_code == 200, r1.text
        conv_id = r1.json()["conversation"]["id"]
        route.mock(return_value=completion("Segunda respuesta"))
        r2 = client.post(
            "/api/ai/assistant-chat",
            json={"conversationId": conv_id, "candidateId": cand.id, "message": "Pregunta dos"}, headers=h,
        )
        body = route.calls.last.request.content.decode()
    assert r2.status_code == 200
    msgs = r2.json()["conversation"]["messages"]
    assert [m["content"] for m in msgs] == ["Pregunta uno", "Primera respuesta", "Pregunta dos", "Segunda respuesta"]
    assert "Pregunta uno" in body and "Primera respuesta" in body
    assert len(_logs(db, "ai.chat")) == 2


def _conv_with_message(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    conv = _evaluate(client, h, cand, settings_override).json()["conversation"]
    return cand, h, conv, conv["messages"][0]["id"]


def test_vote_down_with_note_creates_criterion(client, db, make_user, settings_override, rrhh_root):
    cand, h, conv, mid = _conv_with_message(client, db, make_user, settings_override, rrhh_root)
    r = client.post("/api/ai/vote-response", json={
        "conversationId": conv["id"], "messageId": mid, "vote": "down",
        "feedbackNote": "Valorar más la experiencia en molienda SAG",
    }, headers=h)
    assert r.status_code == 200, r.text
    crit = r.json()["criterion"]
    assert crit["title"] == "Valorar más la experiencia en molienda SAG"
    assert crit["isCorrection"] is True and crit["weightLabel"] == "Importante"
    assert crit["wrongAiAssumption"] and "Recomiendo" in crit["wrongAiAssumption"]
    stored = db.scalar(select(RecruitmentCriterion).where(RecruitmentCriterion.id == crit["id"]))
    assert stored.rule_text == "Valorar más la experiencia en molienda SAG"
    state_msg = r.json()["state"]["aiConversations"][0]["messages"][0]
    assert state_msg["vote"] == "down" and state_msg["feedbackNote"].startswith("Valorar")
    assert len(_logs(db, "ai.vote")) == 1


def test_vote_up_no_criterion(client, db, make_user, settings_override, rrhh_root):
    _, h, conv, mid = _conv_with_message(client, db, make_user, settings_override, rrhh_root)
    r = client.post("/api/ai/vote-response", json={
        "conversationId": conv["id"], "messageId": mid, "vote": "up"}, headers=h)
    assert r.status_code == 200 and "criterion" not in r.json()
    assert r.json()["state"]["aiConversations"][0]["messages"][0]["vote"] == "up"
    assert db.scalar(select(RecruitmentCriterion).where(RecruitmentCriterion.is_correction.is_(True))) is None


def test_daily_limit_returns_429_message(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    reset = datetime(2026, 11, 25, 5, 0, tzinfo=UTC)  # 00:00 en Lima
    with settings_override(openrouter_api_key="test-key"), respx.mock:
        respx.post(BASE).mock(return_value=httpx.Response(
            429, json={"error": {"message": "free-models-per-day"}},
            headers={"X-RateLimit-Reset": str(int(reset.timestamp() * 1000))},
        ))
        r = client.post("/api/ai/assistant-chat", json={"candidateId": cand.id, "message": "Hola"}, headers=h)
    assert r.status_code == 429
    assert r.json()["detail"] == "Límite diario de IA alcanzado; se reanuda a las 00:00 (hora de Perú)"


def test_openrouter_error_returns_502(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    with settings_override(openrouter_api_key="test-key"), respx.mock:
        respx.post(BASE).mock(return_value=httpx.Response(500, json={"error": {"message": "caído"}}))
        r = client.post("/api/ai/evaluate-candidate", json={"candidateId": cand.id}, headers=h)
    assert r.status_code == 502 and r.json()["detail"].startswith("No se pudo consultar la IA:")


def test_ai_unavailable_503(client, db, make_user, settings_override, rrhh_root):
    cand, h = _setup(client, db, make_user, settings_override, rrhh_root)
    r = client.post("/api/ai/evaluate-candidate", json={"candidateId": cand.id}, headers=h)  # sin clave
    assert r.status_code == 503
    assert r.json()["detail"] == "La IA no está configurada (falta OPENROUTER_API_KEY o está desactivada)"


def test_conversations_in_state_and_cascade_on_cv_delete(client, db, make_user, settings_override, rrhh_root):
    cand, h, conv, _ = _conv_with_message(client, db, make_user, settings_override, rrhh_root)
    assert [c["id"] for c in client.get("/api/state", headers=h).json()["aiConversations"]] == [conv["id"]]
    r = client.delete(f"/api/cv-files/{cand.cv_file_id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["aiConversations"] == []
    db.expire_all()
    assert db.scalar(select(AiConversation).where(AiConversation.id == conv["id"])) is None
