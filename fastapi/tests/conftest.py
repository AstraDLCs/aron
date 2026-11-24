from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _override_settings(**kw):
    """Parchea los campos de la instancia que devuelve get_settings() y los restaura al salir."""
    settings = get_settings()
    previous = {k: getattr(settings, k) for k in kw}
    for k, v in kw.items():
        setattr(settings, k, v)
    try:
        yield settings
    finally:
        for k, v in previous.items():
            setattr(settings, k, v)


@pytest.fixture(scope="session")
def test_engine():
    url = get_settings().test_database_url
    if not url:
        pytest.exit("TEST_DATABASE_URL no está definida (ejecutar con docker compose run --rm api pytest)", 2)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config()
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine):
    conn = test_engine.connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        outer.rollback()
        conn.close()


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def settings_override():
    return _override_settings


@pytest.fixture(autouse=True)
def _no_openrouter_key():
    with _override_settings(openrouter_api_key=""):
        yield


@pytest.fixture
def rrhh_root(tmp_path):
    with _override_settings(rrhh_root=tmp_path):
        yield tmp_path
