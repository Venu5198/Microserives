import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="n/a")


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "correlation_id": correlation_id_ctx.get(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(level.upper())
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name=service_name))
    logger.addHandler(handler)
    logger.propagate = False

    # Also attach formatter to root and common loggers
    for log_name in ["rabbitmq-client", "outbox-worker"]:
        sub_logger = logging.getLogger(log_name)
        sub_logger.setLevel(level.upper())
        sub_logger.handlers.clear()
        sub_logger.addHandler(handler)
        sub_logger.propagate = False

    return logger
