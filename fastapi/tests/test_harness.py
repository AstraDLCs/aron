"""Fija el comportamiento del arnés de pruebas para que las tareas siguientes puedan confiar en él."""
from sqlalchemy import func, inspect, select

from app.config import get_settings
from app.models.user import User


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(User))


def test_rollback_per_test_part_1_commit_is_visible_inside(db):
    db.add(User(full_name="Fugaz", email="fugaz@mina.pe", password_hash="x", job_title="t"))
    db.commit()  # incluso un commit dentro del test no debe sobrevivir al test
    assert _count(db) == 1


def test_rollback_per_test_part_2_row_is_gone(db):
    assert _count(db) == 0


def test_session_does_not_expire_on_commit(db, make_user):
    user, _ = make_user()
    db.commit()
    assert "email" not in inspect(user).expired_attributes
    assert user.email == "ana@mina.pe"


def test_settings_override_restores_values(settings_override):
    original = get_settings().registration_mode
    with settings_override(registration_mode="invite", invite_code="Z9") as s:
        assert s.registration_mode == "invite"
        assert get_settings().invite_code == "Z9"
    assert get_settings().registration_mode == original
    assert get_settings().invite_code != "Z9"


def test_rrhh_root_is_tmp_dir(rrhh_root, tmp_path):
    assert get_settings().rrhh_root == rrhh_root == tmp_path
    assert rrhh_root.is_dir()


def test_openrouter_key_is_empty_by_default():
    assert get_settings().openrouter_api_key == ""
