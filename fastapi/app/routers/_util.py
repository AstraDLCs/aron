from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends
from pydantic.alias_generators import to_camel
from sqlalchemy.orm import Session

from app.db import get_db

DbDep = Annotated[Session, Depends(get_db)]


def _jsonable(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def apply_changes(obj: Any, values: dict[str, Any]) -> tuple[dict, dict]:
    """Aplica `values` al objeto y devuelve (antes, después) solo de los campos que cambiaron, en camelCase."""
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for field, new in values.items():
        old = getattr(obj, field)
        if old != new:
            before[to_camel(field)] = _jsonable(old)
            after[to_camel(field)] = _jsonable(new)
            setattr(obj, field, new)
    return before, after
