import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def _preflight(client, origin):
    return client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("origin", ["http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"])
def test_desktop_app_origins_always_allowed(settings_override, origin):
    # Aunque CORS_ORIGINS se configure solo con el dominio de la API, la app de escritorio debe poder llamarla.
    with settings_override(cors_origins=["https://aron.astra-industria.dev"]):
        client = TestClient(create_app())
    r = _preflight(client, origin)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin


def test_extra_origins_from_settings_are_added(settings_override):
    with settings_override(cors_origins=["https://panel.ejemplo.com"]):
        client = TestClient(create_app())
    assert _preflight(client, "https://panel.ejemplo.com").headers["access-control-allow-origin"] == (
        "https://panel.ejemplo.com"
    )


def test_unknown_origin_rejected(settings_override):
    with settings_override(cors_origins=[]):
        client = TestClient(create_app())
    r = _preflight(client, "https://sitio-malicioso.example")
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers
