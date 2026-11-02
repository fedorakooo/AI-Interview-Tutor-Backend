from uuid import UUID

from shared_models.assessment import AssessmentTemplateSnapshot

from src.app.container import AppContainer


async def template_for_attempt(container: AppContainer, attempt_id: UUID) -> AssessmentTemplateSnapshot:
    return (await container.assessment_context_client.get_context(attempt_id)).template
