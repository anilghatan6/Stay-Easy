
import logging
import sys
from typing import Optional


class LoggerFactory:
    """
    Centralized logger factory for the entire application.
    """

    _loggers: dict[str, logging.Logger] = {}

    @staticmethod
    def get_logger(
        name: str, level: int = logging.INFO, log_format: Optional[str] = None
    ) -> logging.Logger:

        if name in LoggerFactory._loggers:
            return LoggerFactory._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False  # IMPORTANT: prevents duplicate logs

        if logger.handlers:
            return logger

        log_format = log_format or (
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        formatter = logging.Formatter(fmt=log_format, datefmt="%Y-%m-%d %H:%M:%S")

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)

        logger.addHandler(stream_handler)

        LoggerFactory._loggers[name] = logger

        return logger
