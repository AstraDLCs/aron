from fastapi import APIRouter

from app.deps import CurrentUser
from app.routers._util import DbDep
from app.services.snapshot import build_state

router = APIRouter(prefix="/state", tags=["state"])


@router.get("")
def get_state(user: CurrentUser, db: DbDep):
    state = build_state(db, user)
    db.commit()  # build_state puede crear la fila de configuración la primera vez
    return state
