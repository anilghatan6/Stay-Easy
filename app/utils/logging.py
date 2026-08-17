
import logging
import sys
from typing import Optional
from asgi_correlation_id import CorrelationIdFilter
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
        
        # 1. Create the correlation id filter
        cid_filter = CorrelationIdFilter(uuid_length=16)

        log_format = log_format or (
            # "[REQ-%(correlation_id)s] | %(asctime)s | %(levelname)s | %(name)s | %(message)s"
            "[REQ-%(correlation_id)s] | %(asctime)s | %(levelname)s | %(message)s"

        )
        formatter = logging.Formatter(fmt=log_format, datefmt="%Y-%m-%d %H:%M:%S")

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)

        # 2. ADD CHANGE HERE: Attach the filter to the handler instead of the logger
        stream_handler.addFilter(cid_filter)

        logger.addHandler(stream_handler)

        LoggerFactory._loggers[name] = logger

        return logger
