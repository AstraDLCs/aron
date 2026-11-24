from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.common import CamelModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Category = Literal["Psicolaboral", "Técnica Minera", "Seguridad HSEC", "Operación / Maquinaria"]
Rating = Annotated[int, Field(ge=1, le=5)]


class PsychSendIn(CamelModel):
    candidate_id: str
    test_battery_name: Name


class PsychAnswers(CamelModel):
    estabilidad: Rating
    tolerancia: Rating
    seguridad: Rating
    equipo: Rating
    razonamiento: Rating


class PsychSubmitIn(CamelModel):
    answers: PsychAnswers


class TestCreateIn(CamelModel):
    name: Name
    category: Category
    target_area: str = Field(default="", max_length=200)
    duration_minutes: int = Field(default=30, ge=1, le=600)
    passing_score: int = Field(default=70, ge=0, le=100)
    questions: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=200,
    )
