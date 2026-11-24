from fastapi import APIRouter, HTTPException, Request
from pydantic.alias_generators import to_camel

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.people import Person
from app.routers._util import DbDep
from app.schemas.people import PersonMergeIn, PersonUpdate
from app.services.candidate_rules import rescore_person
from app.services.persons import apply_person_fields, merge_persons, refresh_possible_same, with_name_parts
from app.services.snapshot import state_response

router = APIRouter(prefix="/persons", tags=["persons"])


@router.patch("/{person_id}")
def update_person(person_id: str, body: PersonUpdate, request: Request, user: CurrentUser, db: DbDep):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    values = with_name_parts(body.model_dump(exclude_unset=True), person)
    owners_before = dict(person.field_sources or {})
    changed = apply_person_fields(person, values, "user", allow_clear=True)
    owners_after = person.field_sources or {}
    # también es una modificación que un campo pase a ser del usuario aunque su valor no cambie
    claimed = [f for f in owners_after if owners_after[f] != owners_before.get(f) and f not in changed]
    if changed:
        refresh_possible_same(db, person)
        rescore_person(db, person)
    if changed or claimed:
        log_action(
            db, actor=user, action="person.update", entity_type="person", entity_id=person.id,
            summary=f"Actualizó los datos personales de {person.full_name}",
            details={"fields": [to_camel(f) for f in [*changed, *claimed]]},  # sin valores: datos personales
            ip=client_ip(request),
        )
    db.commit()
    return state_response(db, user)


@router.post("/{person_id}/merge")
def merge_person(person_id: str, body: PersonMergeIn, request: Request, user: CurrentUser, db: DbDep):
    try:
        merge_persons(db, person_id, body.other_person_id, user, ip=client_ip(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    db.commit()
    return state_response(db, user)
