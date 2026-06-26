from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import DependenciesContainer, Factory

from src.use_cases.cv_analyze_use_case import CVAnalyzeUseCase


class UseCasesContainer(DeclarativeContainer):
    outbound_adapters = DependenciesContainer()

    agent = DependenciesContainer()

    cv_analyze_use_case = Factory(
        CVAnalyzeUseCase,
        s3_client=outbound_adapters.s3_client,
        cv_analyzer=agent.cv_analyzer,
        pdf_loader=outbound_adapters.pdf_loader,
        mongo_repository=outbound_adapters.mongo_cv_analysis_repository,
        rabbitmq_producer=outbound_adapters.rabbitmq_producer_cv_results,
    )
