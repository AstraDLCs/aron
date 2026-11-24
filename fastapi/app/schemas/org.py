from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from app.schemas.common import CamelModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Urgency = Literal["Urgente", "Media", "Planificada"]
SourceCategory = Literal["Portal Minero", "Red Profesional", "Bolsa Nacional", "Referidos Faena"]


def _clean_models(values: list[str]) -> list[str]:
    return [v.strip() for v in values if v and v.strip()]


class _Patch(CamelModel):
    """Base de los PATCH: los campos no nulos no admiten `null` explícito."""

    not_nullable: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _reject_null(self):
        for name in self.not_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} no puede ser nulo")
        return self


# --- puestos ---------------------------------------------------------------


class PositionCreate(CamelModel):
    name: Name
    folder_name: str | None = Field(default=None, max_length=200)
    area: Name
    parent_id: str | None = None
    description: str = ""
    required_skills: str = ""
    technical_specifications: str = ""
    min_years_experience: int = Field(default=0, ge=0, le=60)
    education_profile: str = ""
    sort_order: int = 0


class PositionUpdate(_Patch):
    not_nullable: ClassVar[tuple[str, ...]] = (
        "name", "folder_name", "area", "description", "required_skills", "technical_specifications",
        "min_years_experience", "education_profile", "sort_order",
    )
    name: Name | None = None
    folder_name: str | None = Field(default=None, max_length=200)
    area: Name | None = None
    parent_id: str | None = None
    description: str | None = None
    required_skills: str | None = None
    technical_specifications: str | None = None
    min_years_experience: int | None = Field(default=None, ge=0, le=60)
    education_profile: str | None = None
    sort_order: int | None = None


class PositionOut(CamelModel):
    id: str
    name: str
    folder_name: str
    area: str
    parent_id: str | None
    description: str
    required_skills: str
    technical_specifications: str
    min_years_experience: int
    education_profile: str
    sort_order: int
    open_requirements_count: int
    candidates_count: int


# --- fuentes ---------------------------------------------------------------


class SourceCreate(CamelModel):
    name: Name
    folder_name: str | None = Field(default=None, max_length=200)
    category: SourceCategory
    avg_response_hours: float = Field(default=0, ge=0)


class SourceUpdate(_Patch):
    not_nullable: ClassVar[tuple[str, ...]] = ("name", "category", "active", "avg_response_hours")
    name: Name | None = None
    category: SourceCategory | None = None
    active: bool | None = None
    avg_response_hours: float | None = Field(default=None, ge=0)


class ProposalIn(CamelModel):
    requirement_id: str


class JobBoardOut(CamelModel):
    id: str
    name: str
    folder_name: str
    category: str
    proposals_sent: int
    candidates_received: int
    shortlisted_count: int
    hired_count: int
    avg_response_hours: float
    last_proposal_at: datetime | None
    active: bool


# --- requerimientos --------------------------------------------------------


class RequirementCreate(CamelModel):
    position_id: str
    quantity: int = Field(ge=1, le=1000)
    urgency: Urgency
    target_days_to_fill: int = Field(default=30, ge=1, le=3650)
    context: str = ""
    extra_skills: str = ""
    published_source_ids: list[str] = []


class RequirementUpdate(_Patch):
    not_nullable: ClassVar[tuple[str, ...]] = ("quantity", "urgency", "target_days_to_fill", "context", "extra_skills",
                     "published_source_ids", "status")
    quantity: int | None = Field(default=None, ge=1, le=1000)
    urgency: Urgency | None = None
    target_days_to_fill: int | None = Field(default=None, ge=1, le=3650)
    context: str | None = None
    extra_skills: str | None = None
    published_source_ids: list[str] | None = None
    status: Literal["Abierto", "Cancelado"] | None = None


class JobNeedOut(CamelModel):
    id: str
    position_id: str
    title: str
    department: str
    urgency: str
    vacancies: int
    filled_count: int
    required_skills: str
    technical_specifications: str
    company_context: str
    published_boards: list[str]
    published_source_ids: list[str]
    opened_at: datetime
    target_days_to_fill: int
    created_by: str
    status: str
    extra_skills: str


# --- configuración ---------------------------------------------------------


class SettingsOut(CamelModel):
    company_name: str
    ai_model: str
    ai_fallback_models: list[str]
    ai_preapprove_threshold: int
    ai_enabled: bool
    ai_configured: bool


class SettingsUpdate(_Patch):
    not_nullable: ClassVar[tuple[str, ...]] = ("company_name", "ai_model", "ai_fallback_models", "ai_preapprove_threshold", "ai_enabled")
    company_name: Name | None = None
    ai_model: str | None = Field(default=None, max_length=200)
    ai_fallback_models: Annotated[list[str] | None, AfterValidator(lambda v: v if v is None else _clean_models(v))] = None
    ai_preapprove_threshold: int | None = Field(default=None, ge=0, le=100)
    ai_enabled: bool | None = None


class AiQueueOut(CamelModel):
    queued: int
    processing: int
    errors: int
    sin_ia: int
    paused_until: datetime | None
    ai_enabled: bool
    model: str
    # Qué está haciendo el worker y cuándo dio señales; próximo reintento y último motivo de espera o error.
    worker_seen_at: datetime | None = None
    worker_status: str = ""
    next_attempt_at: datetime | None = None
    last_error: str | None = None
