"""Structured JSON logging with request/correlation context binding."""

import logging
import sys
from contextvars import ContextVar

import structlog

from app.core.config import get_settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

_SENSITIVE_KEYS = {"password", "api_key", "authorization", "secret", "token", "refresh_token"}


def _redact_sensitive(_: object, __: str, event_dict: dict) -> dict:
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def _add_context(_: object, __: str, event_dict: dict) -> dict:
    settings = get_settings()
    event_dict.setdefault("service", settings.app_name)
    event_dict.setdefault("version", settings.app_version)
    event_dict.setdefault("environment", settings.environment)
    event_dict.setdefault("request_id", request_id_var.get())
    event_dict.setdefault("user_id", user_id_var.get())
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(stream=sys.stdout, level=settings.log_level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.add_log_level,
            _add_context,
            _redact_sensitive,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
