from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel


def parse_model_specs(raw: str) -> list[str]:
    return [spec.strip() for spec in raw.split(",") if spec.strip()]


def resolve_model(specs: list[str]) -> Model | str:
    if not specs:
        raise ValueError("At least one model must be configured")
    if len(specs) == 1:
        return specs[0]
    return FallbackModel(*specs)
