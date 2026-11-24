from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def log_action(
    db: Session,
    *,
    actor: User | str | None,
    action: str,
    entity_type: str,
    summary: str,
    entity_id: str | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Agrega una fila a la bitácora en la transacción actual (el commit lo hace quien llama)."""
    if isinstance(actor, User):
        user_id, user_name = actor.id, actor.full_name
    else:
        user_id, user_name = None, actor or ""
    entry = AuditLog(
        user_id=user_id,
        user_name=user_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=details,
        ip=ip,
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)  # carga `at` (default del servidor)
    return entry
