import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.audit import log_action
from app.models.audit import AuditLog


def test_log_action_with_user_and_system_actor(db, make_user):
    user, _ = make_user()
    a = log_action(db, actor=user, action="x.test", entity_type="user", entity_id=user.id,
                   summary="Prueba", details={"k": 1}, ip="10.0.0.1")
    b = log_action(db, actor="Sistema", action="x.test", entity_type="user", summary="Otra")
    c = log_action(db, actor=None, action="x.test", entity_type="user", summary="Anónima")
    assert (a.user_id, a.user_name, a.details, a.ip) == (user.id, "Ana Torres", {"k": 1}, "10.0.0.1")
    assert (b.user_id, b.user_name, b.details) == (None, "Sistema", None)
    assert c.user_name == ""
    assert a.id and a.at is not None
    assert len(list(db.scalars(select(AuditLog)))) == 3


@pytest.mark.parametrize("stmt", [
    "UPDATE audit_log SET summary='x'",
    "DELETE FROM audit_log",
    "TRUNCATE audit_log",
])
def test_audit_log_is_append_only(db, stmt):
    log_action(db, actor="Sistema", action="x.test", entity_type="user", summary="Intocable")
    db.flush()
    with pytest.raises(DBAPIError, match="solo de inserción"):
        with db.begin_nested():
            db.execute(text(stmt))
    assert db.scalar(select(AuditLog.summary)) == "Intocable"
