from datetime import datetime
from typing import Annotated, ClassVar

from pydantic import AfterValidator, Field, StringConstraints

from app.schemas.common import CamelModel
from app.schemas.org import _Patch

Sha256 = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9a-fA-F]{64}$"),
                   AfterValidator(str.lower)]
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Text300 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Items = Annotated[list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]], Field(max_length=50)]


# --- entradas --------------------------------------------------------------


class CvCheckItem(CamelModel):
    sha256: Sha256
    position_id: str


class CvCheckIn(CamelModel):
    items: list[CvCheckItem] = Field(max_length=2000)


class CvFileUpdate(_Patch):
    not_nullable: ClassVar[tuple[str, ...]] = ("position_id", "source_id")
    position_id: str | None = None
    source_id: str | None = None


class PersonUpdate(_Patch):
    """Corrección manual de datos personales (fuente 'user'). `age` y `yearsWorked` admiten null para vaciarlos."""

    not_nullable: ClassVar[tuple[str, ...]] = (
        "first_names", "last_names", "full_name", "document_id", "email", "phone", "origin_location", "university",
        "career", "work_history_summary", "specifications", "languages", "licenses",
    )
    first_names: Text200 | None = None
    last_names: Text200 | None = None
    full_name: FullName | None = None
    document_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    age: int | None = Field(default=None, ge=14, le=100)
    origin_location: Text200 | None = None
    university: Text300 | None = None
    career: Text300 | None = None
    years_worked: int | None = Field(default=None, ge=0, le=60)
    work_history_summary: Annotated[str, StringConstraints(max_length=5000)] | None = None
    specifications: Items | None = None
    languages: Items | None = None
    licenses: Items | None = None


class PersonMergeIn(CamelModel):
    other_person_id: str


class ManualCandidateIn(CamelModel):
    full_name: FullName
    career: Text300
    position_id: str
    source_id: str
    requirement_id: str | None = None
    age: int | None = Field(default=None, ge=14, le=100)
    origin_location: Text200 = ""
    university: Text300 = ""
    years_worked: int | None = Field(default=None, ge=0, le=60)
    work_history_summary: Annotated[str, StringConstraints(max_length=5000)] = ""
    specifications: Items = []
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] = ""
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""
    document_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] = ""
    interview_notes: Annotated[str, StringConstraints(max_length=5000)] = ""


# --- foto ------------------------------------------------------------------


class MetricReportOut(CamelModel):
    technical_specs_score: int
    experience_score: int
    education_career_score: int
    psych_score: int | float
    overall_score: int
    fit_verdict: str
    ai_detailed_report: str
    generated_at: datetime


class OtherApplicationOut(CamelModel):
    candidate_id: str
    position_name: str
    decision: str


class CandidateOut(CamelModel):
    """Una postulación en la foto, con los datos de la persona incrustados (contrato `Candidate`)."""

    id: str
    person_id: str
    cv_file_id: str | None
    position_id: str
    requirement_id: str | None
    target_need_id: str
    target_role_title: str
    source_board_id: str
    source_board_name: str

    full_name: str
    first_names: str
    last_names: str
    document_id: str
    email: str
    phone: str
    phone_or_email: str
    age: int | None
    origin_location: str
    university: str
    career: str
    years_worked: int | None
    work_history_summary: str
    specifications: list[str]
    languages: list[str]
    licenses: list[str]
    interview_notes: str

    cv_file_name: str | None
    cv_mime_type: str | None
    cv_uploaded_at: datetime | None
    cv_uploaded_by: str | None
    cv_origin: str | None
    cv_path: str | None
    cv_missing: bool

    psych_evaluation: dict
    excel_test_results: list[dict]
    metric_report: MetricReportOut

    ai_status: str
    ai_verdict: str | None
    ai_aptitude_score: int | None
    ai_strengths: list[str]
    ai_observations: list[str]
    ai_reason: str
    ai_applied_criteria: list[str]
    ai_applied_correction_title: str | None
    ai_model: str | None
    ai_classified_at: datetime | None
    ai_error: str | None
    ai_summary: str
    ai_observed_score: int

    decision: str
    manager_score: int | None
    manager_notes: str
    evaluated_by: str | None
    evaluated_at: datetime | None

    possible_same_person_ids: list[str]
    other_applications: list[OtherApplicationOut]
    process_days_elapsed: int
    created_at: datetime


class BlockedCvFileOut(CamelModel):
    id: str
    sha256: str
    position_id: str
    original_name: str
    deleted_by: str
    deleted_at: datetime
