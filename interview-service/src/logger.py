import logging.config

from src.config import settings

logging.config.dictConfig(settings.logger_settings.logging_config)

app_logger = logging.getLogger("app")
