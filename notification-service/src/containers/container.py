import logging.config

from dependency_injector import providers
from dependency_injector.containers import DeclarativeContainer

from src.containers.inbound_adapters import InboundAdaptersContainer
from src.containers.outbound_adapters import OutboundAdaptersContainer
from src.containers.use_cases import UseCasesContainer


class Container(DeclarativeContainer):
    yaml_config = providers.Configuration(yaml_files=["config.yaml"])

    logging_config = providers.Resource(logging.config.dictConfig, config=yaml_config.logger)

    logger = providers.Singleton(
        logging.getLogger,
    )

    outbound_adapters = providers.Container(
        OutboundAdaptersContainer,
        logger=logger,
    )

    use_cases = providers.Container(
        UseCasesContainer,
        outbound_adapters=outbound_adapters,
    )

    inbound_adapters = providers.Container(
        InboundAdaptersContainer,
        use_cases=use_cases,
        logger=logger,
    )
