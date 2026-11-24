"""Respaldo y restauración de los datos de negocio (todo salvo `users`, `audit_log` y `alembic_version`).

Las tablas se toman del metadata de SQLAlchemy y se ordenan por dependencias, así que las tablas que se agreguen
después (conversaciones de IA, pruebas, resultados de Excel) quedan incluidas sin tocar este módulo.
"""
import importlib
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Table, delete, func, insert, select, update
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra las tablas)
from app.audit import log_action
from app.db import Base
from app.models.audit import AuditLog
from app.models.user import User
from app.services.storage import RrhhStorage

for _optional in ("app.models.ai", "app.models.tests_module"):  # tareas 9 y 10: pueden no existir todavía
    try:
        importlib.import_module(_optional)
    except ModuleNotFoundError:
        pass

BACKUP_VERSION = 1
EXCLUDED_TABLES = {"users", "audit_log", "alembic_version"}
KEY_BY_TABLE = {
    "positions": "positions",
    "sources": "sources",
    "requirements": "requirements",
    "persons": "persons",
    "cv_files": "cvFiles",
    "deleted_cv_hashes": "deletedCvHashes",
    "candidates": "candidates",
    "recruitment_criteria": "criteria",
    "test_definitions": "tests",
    "excel_test_results": "excelResults",
    "ai_conversations": "conversations",
    "ai_messages": "messages",
    "app_settings": "settings",
}


def business_tables() -> list[Table]:
    """Tablas de negocio en orden de dependencias (las referenciadas van primero)."""
    return [t for t in Base.metadata.sorted_tables if t.name not in EXCLUDED_TABLES]


def table_key(table: Table) -> str:
    return KEY_BY_TABLE.get(table.name, table.name)


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def export_business_data(db: Session) -> dict:
    data = {}
    for table in business_tables():
        rows = db.execute(select(table)).mappings().all()
        data[table_key(table)] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
    return {"version": BACKUP_VERSION, "exportedAt": datetime.now().astimezone().isoformat(), "data": data}


# --- restauración -----------------------------------------------------------


def _self_fk_columns(table: Table) -> list[str]:
    return [c.name for c in table.columns for fk in c.foreign_keys if fk.column.table is table]


def _order_parents_first(table: Table, rows: list[dict]) -> list[dict]:
    cols = _self_fk_columns(table)
    if not cols:
        return rows
    pk = next(iter(table.primary_key.columns)).name
    pending, done, ordered = list(rows), set(), []
    while pending:
        progressed = False
        rest = []
        for row in pending:
            if all(row.get(c) is None or row.get(c) in done for c in cols):
                ordered.append(row)
                done.add(row[pk])
                progressed = True
            else:
                rest.append(row)
        if not progressed:  # ciclo o padre ausente: se inserta como venga y la base decidirá
            ordered.extend(rest)
            break
        pending = rest
    return ordered


def _prepare_row(table: Table, row: dict, user_ids: set[str]) -> dict:
    out = {}
    for col in table.columns:
        if col.name not in row:
            continue
        value = row[col.name]
        if value is not None and isinstance(col.type, DateTime) and isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value is not None and any(fk.column.table.name == "users" for fk in col.foreign_keys):
            if value not in user_ids:  # el usuario de la copia ya no existe aquí
                value = None
        out[col.name] = value
    return out


def _validate(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("version") != BACKUP_VERSION:
        raise ValueError("Versión de respaldo no compatible")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("El respaldo no tiene datos")
    return data


def restore_business_data(db: Session, payload: dict, actor: User, storage: RrhhStorage, ip: str | None = None) -> dict:
    """Reemplaza los datos de negocio por los del respaldo, en la transacción de `db` (no hace commit)."""
    data = _validate(payload)
    tables = business_tables()
    user_ids = set(db.scalars(select(User.id)))

    for table in reversed(tables):  # primero las tablas que dependen de otras
        cols = _self_fk_columns(table)
        if cols:
            db.execute(update(table).values({c: None for c in cols}))
        db.execute(delete(table))

    counts: dict[str, int] = {}
    for table in tables:
        rows = _order_parents_first(table, list(data.get(table_key(table)) or []))
        prepared = [_prepare_row(table, r, user_ids) for r in rows]
        if prepared:
            db.execute(insert(table), prepared)
        counts[table_key(table)] = len(prepared)

    missing = []
    cv_table = Base.metadata.tables["cv_files"]
    for cv_id, rel in db.execute(select(cv_table.c.id, cv_table.c.stored_path)).all():
        try:
            exists = storage.abs_path(rel).is_file()
        except ValueError:
            exists = False
        if not exists:
            missing.append(rel)
        db.execute(update(cv_table).where(cv_table.c.id == cv_id).values(missing=not exists))
    db.expire_all()

    log_action(
        db, actor=actor, action="datacenter.restore", entity_type="datacenter",
        summary=f"Restauró un respaldo ({sum(counts.values())} registros)",
        details={"counts": counts, "missingFiles": len(missing)}, ip=ip,
    )
    return {"counts": counts, "missingFiles": missing}


def status(db: Session, storage_path: str) -> dict:
    from app.models.criteria import RecruitmentCriterion
    from app.models.org import Position, Requirement, Source
    from app.models.people import Candidate, Person

    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    total = sum(db.scalar(select(func.count()).select_from(t)) or 0 for t in business_tables())
    last = db.scalar(select(func.max(AuditLog.at)))
    psych_completed = sum(
        1 for ev in db.scalars(select(Person.psych_evaluation)) if (ev or {}).get("status") == "Completada"
    )
    return {
        "mode": "PostgreSQL",
        "storagePath": storage_path,
        "totalRecords": total,
        "candidatesCount": count(Candidate),
        "vacanciesCount": count(Requirement),
        "boardsCount": count(Source),
        "criteriaCount": count(RecruitmentCriterion),
        "psychCompletedCount": psych_completed,
        "lastSavedAt": (last or datetime.now().astimezone()).isoformat(),
        "positionsCount": count(Position),
    }
