from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Dependency, Resource, Singleton

from src.agent.llm import LLMFactory
from src.agent.services.cv_analyzer import CVAnalyzer


class AgentContainer(DeclarativeContainer):
    logger = Dependency()

    llm = Resource(LLMFactory.create_llm)

    cv_analyzer = Singleton(
        CVAnalyzer,
        model=llm,
        logger=logger,
    )
