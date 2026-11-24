from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import StringConstraints

from app.constants import ALL_AREAS
from app.schemas.common import CamelModel
from app.schemas.org import _Patch

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
RuleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Weight = Literal["Prioritario", "Importante", "Deseable"]


class CriterionCreate(CamelModel):
    title: Title
    applies_to_department: Title = ALL_AREAS
    weight_label: Weight = "Importante"
    rule_text: RuleText
    is_correction: bool = False
    wrong_ai_assumption: str | None = None


class CriterionUpdate(_Patch):
    not_nullable: ClassVar[tuple[str, ...]] = (
        "title", "applies_to_department", "weight_label", "rule_text", "is_correction",
    )
    title: Title | None = None
    applies_to_department: Title | None = None
    weight_label: Weight | None = None
    rule_text: RuleText | None = None
    is_correction: bool | None = None
    wrong_ai_assumption: str | None = None


class CriterionOut(CamelModel):
    id: str
    title: str
    applies_to_department: str
    weight_label: str
    rule_text: str
    is_correction: bool
    wrong_ai_assumption: str | None
    learned_from_candidate: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
