import logging
import os
from typing import List

from galaxy.core.models import Config

__all__ = ["InMemoryLogHandler", "get_magneto_logs", "setup_logger", "get_log_format"]


class InMemoryLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs: List[str] = []

    def emit(self, record) -> None:
        log_entry = self.format(record)
        self.logs.append(log_entry)


def get_magneto_logs(logger: logging.Logger) -> InMemoryLogHandler | None:
    for handler in logger.handlers:
        if isinstance(handler, InMemoryLogHandler):
            return handler
    return None


def get_log_format(config) -> str:
    return f"%(asctime)s - {config.integration.type}-{config.integration.id} - %(levelname)s - %(message)s"


def setup_logger(config: Config) -> logging.Logger:
    logger = logging.getLogger("galaxy")
    console_handler = logging.StreamHandler()
    memory_handler = InMemoryLogHandler()

    if os.environ.get("RELY_INTEGRATION_DEBUG", "false").lower() == "true":
        logger.setLevel(logging.DEBUG)
        # To avoid sending tokens and so on to the logs of magneto when running in debug mode
        memory_handler.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.INFO)

    console_formatter = logging.Formatter(get_log_format(config))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    logger.addHandler(memory_handler)

    return logger
