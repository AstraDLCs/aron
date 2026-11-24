from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.criteria import RecruitmentCriterion
from app.routers._util import DbDep, apply_changes
from app.schemas.criteria import CriterionCreate, CriterionUpdate
from app.services.criteria import create_criterion, rescore_departments
from app.services.snapshot import build_state, criteria_payload, pick

router = APIRouter(prefix="/criteria", tags=["criteria"])


@router.get("")
def list_criteria(user: CurrentUser, db: DbDep):
    return {"criteria": criteria_payload(db)}


@router.post("", status_code=201)
def create(body: CriterionCreate, request: Request, user: CurrentUser, db: DbDep):
    criterion = create_criterion(
        db, actor=user, title=body.title, rule_text=body.rule_text, department=body.applies_to_department,
        weight=body.weight_label, is_correction=body.is_correction, wrong_ai_assumption=body.wrong_ai_assumption,
        ip=client_ip(request),
    )
    db.commit()
    state = build_state(db, user)
    return {"criterion": pick(state, "recruitmentCriteria", criterion.id), "state": state}


@router.patch("/{criterion_id}")
def update(criterion_id: str, body: CriterionUpdate, request: Request, user: CurrentUser, db: DbDep):
    criterion = db.scalar(
        select(RecruitmentCriterion).where(RecruitmentCriterion.id == criterion_id).with_for_update()
    )
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterio no encontrado")
    old_department = criterion.applies_to_department
    before, after = apply_changes(criterion, body.model_dump(exclude_unset=True))
    if before:
        db.flush()
        log_action(
            db, actor=user, action="criterion.update", entity_type="criterion", entity_id=criterion.id,
            summary=f"Editó el criterio «{criterion.title}»", details={"before": before, "after": after},
            ip=client_ip(request),
        )
        # el criterio deja de aplicar al área anterior y empieza a aplicar al área nueva
        rescore_departments(db, {old_department, criterion.applies_to_department})
    db.commit()
    state = build_state(db, user)
    return {"criterion": pick(state, "recruitmentCriteria", criterion.id), "state": state}
