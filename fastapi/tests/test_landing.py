import hashlib

import pytest


@pytest.fixture
def downloads(tmp_path, settings_override):
    with settings_override(downloads_dir=tmp_path):
        yield tmp_path


def _msi(folder, name, content=b"MSI-de-prueba"):
    path = folder / name
    path.write_bytes(content)
    return path


def test_landing_is_public_html_with_download(client, downloads):
    content = b"x" * (3 * 1024 * 1024 + 300_000)
    _msi(downloads, "PulsoLaboral_0.1.0_x64_es-ES.msi", content)
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in r.headers["content-security-policy"]
    body = r.text
    assert 'href="/descargar/windows"' in body
    assert "Versión 0.1.0" in body
    assert "3,3 MB" in body
    assert hashlib.sha256(content).hexdigest() in body


def test_landing_without_installer_says_so(client, downloads):
    r = client.get("/")
    assert r.status_code == 200
    assert "todavía no está publicado" in r.text
    assert 'href="/descargar/windows"' not in r.text


def test_download_serves_newest_msi_as_attachment(client, downloads):
    _msi(downloads, "PulsoLaboral_0.9.0_x64_es-ES.msi", b"vieja")
    _msi(downloads, "PulsoLaboral_0.10.0_x64_es-ES.msi", b"nueva")
    r = client.get("/descargar/windows")
    assert r.status_code == 200
    assert r.content == b"nueva"
    assert r.headers["content-type"] == "application/x-msi"
    assert 'attachment; filename="PulsoLaboral_0.10.0_x64_es-ES.msi"' == r.headers["content-disposition"]


def test_download_404_when_missing(client, downloads):
    r = client.get("/descargar/windows")
    assert r.status_code == 404
    assert "todavía no está publicado" in r.json()["detail"]


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("invite", "código de invitación"), ("open", "crear tu cuenta desde la aplicación")],
)
def test_landing_account_note_follows_registration_mode(client, downloads, settings_override, mode, expected):
    with settings_override(registration_mode=mode):
        assert expected in client.get("/").text


@pytest.mark.parametrize(
    ("path", "ctype"),
    [("/recursos/icono.png", "image/png"), ("/recursos/public-sans-latin-400-normal.woff2", "font/woff2")],
)
def test_page_resources_are_served(client, path, ctype):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"] == ctype


def test_api_routes_still_require_auth(client, downloads):
    assert client.get("/api/state").status_code == 401
