CONTRACT_KEYS = {
    "catalogVersion", "companyName", "hrChiefName", "hrChiefTitle", "currentUser", "settings", "aiQueue",
    "positions", "jobNeeds", "jobBoards", "candidates", "blockedCvFiles", "recruitmentCriteria",
    "testCatalog", "aiConversations", "kpis",
}


def test_state_requires_auth(client):
    assert client.get("/api/state").status_code == 401


def test_state_contract_keys(client, make_user):
    user, h = make_user()
    s = client.get("/api/state", headers=h).json()
    assert set(s.keys()) == CONTRACT_KEYS
    assert s["catalogVersion"] == 4
    assert s["currentUser"]["fullName"] == s["hrChiefName"] == "Ana Torres"
    assert s["hrChiefTitle"] == user.job_title == s["currentUser"]["jobTitle"]
    assert set(s["currentUser"]) == {"id", "fullName", "email", "jobTitle", "isActive"}
    assert s["companyName"] == "Compañía Minera Las Bravas"
    assert set(s["settings"]) == {
        "companyName", "aiModel", "aiFallbackModels", "aiPreapproveThreshold", "aiEnabled", "aiConfigured",
    }
    assert s["settings"]["aiConfigured"] is False
    assert s["settings"]["aiPreapproveThreshold"] == 70
    assert s["aiQueue"] == {
        "queued": 0, "processing": 0, "errors": 0, "sinIa": 0, "pausedUntil": None,
        "aiEnabled": False, "model": s["settings"]["aiModel"],
        "workerSeenAt": None, "workerStatus": "", "nextAttemptAt": None, "lastError": None,
    }
    for key in ("positions", "jobNeeds", "jobBoards", "candidates", "blockedCvFiles",
                "recruitmentCriteria", "testCatalog", "aiConversations"):
        assert s[key] == []
    assert s["kpis"]["totalVacancies"] == 0
    assert s["kpis"]["topBoardName"] == "Sin datos"


def test_ai_queue_enabled_needs_key(client, make_user, settings_override):
    _, h = make_user()
    with settings_override(openrouter_api_key="sk-test"):
        s = client.get("/api/state", headers=h).json()
    assert s["settings"]["aiConfigured"] is True
    assert s["aiQueue"]["aiEnabled"] is True
