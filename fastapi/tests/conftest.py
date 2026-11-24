import os
from contextlib import contextmanager
from pathlib import Path

# Debe definirse antes de importar la app: JWT_SECRET es obligatorio.
os.environ.setdefault("JWT_SECRET", "secreto-solo-para-pruebas-" + "x" * 32)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

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
    settings = get_settings()
    url = settings.test_database_url
    if not url:
        pytest.exit("TEST_DATABASE_URL no está definida (ejecutar con docker compose run --rm api pytest)", 2)
    test_name = make_url(url).database or ""
    prod_name = make_url(settings.database_url).database or ""
    if not test_name.endswith("_test") or test_name == prod_name:
        pytest.exit(
            f"TEST_DATABASE_URL apunta a '{test_name}': debe terminar en '_test' y ser distinta de "
            f"DATABASE_URL ('{prod_name}'). Se aborta para no borrar datos reales.",
            2,
        )
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
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)

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


@pytest.fixture
def make_user(db):
    def _make(email="ana@mina.pe", full_name="Ana Torres", job_title="Jefe de RR.HH.", password="clave-segura-1"):
        user = User(
            full_name=full_name,
            email=email.lower(),
            password_hash=hash_password(password),
            job_title=job_title,
        )
        db.add(user)
        db.flush()
        return user, {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _make
