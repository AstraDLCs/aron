from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base de todos los esquemas: JSON en camelCase, y se acepta también snake_case al construir."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)
