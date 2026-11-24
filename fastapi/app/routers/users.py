from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut], response_model_by_alias=True)
def list_users(_: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    return list(db.scalars(select(User).order_by(User.full_name, User.email)))
