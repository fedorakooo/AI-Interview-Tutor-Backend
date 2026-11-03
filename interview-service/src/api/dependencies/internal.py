from uuid import UUID

from shared_models.assessment import AssessmentTemplateSnapshot

from src.api.dependencies.container import ApiContainer


async def template_for_attempt(container: ApiContainer, attempt_id: UUID) -> AssessmentTemplateSnapshot:
    return await container.get_assessment_template_use_case(attempt_id)
