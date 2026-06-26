from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import DependenciesContainer, Factory

from src.application.use_cases.reset_password_use_case import ResetPasswordUseCase


class UseCasesContainer(DeclarativeContainer):
    outbound_adapters = DependenciesContainer()

    reset_password_use_case = Factory(
        ResetPasswordUseCase,
        mongo_repository=outbound_adapters.messages_mongo_repository,
        ses_client=outbound_adapters.ses_client,
    )
