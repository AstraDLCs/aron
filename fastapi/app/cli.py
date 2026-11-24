"""Administración por consola: `python -m app.cli users deactivate|activate <email>`."""
import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.constants import SYSTEM_ACTOR
from app.db import SessionLocal
from app.models.user import User

_ACTIONS = {
    "deactivate": (False, "user.deactivate", "Se desactivó la cuenta de {name} ({email})"),
    "activate": (True, "user.activate", "Se activó la cuenta de {name} ({email})"),
}


def _set_active(db: Session, email: str, command: str) -> int:
    active, action, template = _ACTIONS[command]
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        print(f"No existe una cuenta con el email {email}", file=sys.stderr)
        return 1
    user.is_active = active
    log_action(
        db, actor=SYSTEM_ACTOR, action=action, entity_type="user", entity_id=user.id,
        summary=template.format(name=user.full_name, email=user.email),
    )
    db.commit()
    print(f"{user.email}: {'activa' if active else 'desactivada'}")
    return 0


def main(argv: list[str], db: Session | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="group", required=True)
    users = sub.add_parser("users", help="gestión de cuentas").add_subparsers(dest="command", required=True)
    for command in _ACTIONS:
        users.add_parser(command).add_argument("email")
    args = parser.parse_args(argv)

    if db is not None:  # sesión inyectada (pruebas): quien la pasa la cierra
        return _set_active(db, args.email, args.command)
    with SessionLocal() as session:
        return _set_active(session, args.email, args.command)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
