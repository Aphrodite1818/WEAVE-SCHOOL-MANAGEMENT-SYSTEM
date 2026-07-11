# ====================================== #
#               logging.py               #
# ====================================== #

"""Application logging configuration."""

import logging
import logging.handlers
import sys
from copy import copy
from pathlib import Path

try:
    from app.config.settings import BASE_DIR, settings
except Exception:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    class _FallbackSettings:
        ENV = "dev"
        LOG_LEVEL = None

        @property
        def is_development(self) -> bool:
            return self.ENV == "dev"

    settings = _FallbackSettings()


LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

_CONFIGURED_ATTR = "_learnlyai_logging_configured"
_STANDARD_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | frozenset({"message", "asctime", "source"})


def is_development() -> bool:
    return bool(getattr(settings, "is_development", False))


def _level_from_name(name: str) -> int:
    level = getattr(logging, name.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {name}")
    return level


def resolve_log_level() -> int:
    if settings.LOG_LEVEL:
        return _level_from_name(settings.LOG_LEVEL)
    return logging.DEBUG if is_development() else logging.INFO


class ContextFormatter(logging.Formatter):
    """Format application records with structured context."""

    _ACCESS_LOGGER_NAME = "uvicorn.access"
    _PLAIN_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: str = "%",
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self._plain_formatter = logging.Formatter(
            fmt=self._PLAIN_FORMAT,
            datefmt=datefmt,
            style=style,
        )

    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy(record)

        if record_copy.name == self._ACCESS_LOGGER_NAME:
            return self._plain_formatter.format(record_copy)

        record_copy.source = self._source_path(record_copy)
        message = super().format(record_copy)
        extras = [
            (key, value)
            for key, value in record_copy.__dict__.items()
            if key not in _STANDARD_RECORD_ATTRS
        ]

        if not extras:
            return message

        extra_part = " | ".join(
            f"{key}={value!r}" for key, value in sorted(extras)
        )
        return f"{message} | {extra_part}"

    @staticmethod
    def _source_path(record: logging.LogRecord) -> str:
        try:
            path = Path(record.pathname).resolve().relative_to(BASE_DIR)
        except ValueError:
            path = Path(record.pathname).name
        return f"{path}:{record.lineno}"


def _build_console_handler(console_level: int) -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(console_level)
    handler.setFormatter(
        ContextFormatter(
            "%(asctime)s | %(levelname)-8s | source=%(source)s | "
            "%(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def _build_file_handler() -> logging.Handler:
    LOG_DIR.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        ContextFormatter(
            "%(asctime)s | %(levelname)-8s | source=%(source)s | "
            "%(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def _build_handlers(console_level: int) -> list[logging.Handler]:
    handlers: list[logging.Handler] = [_build_console_handler(console_level)]
    if is_development():
        handlers.append(_build_file_handler())
    return handlers


def _attach_handlers(
    target_logger: logging.Logger,
    handlers: list[logging.Handler],
) -> None:
    target_logger.handlers.clear()
    for handler in handlers:
        target_logger.addHandler(handler)
    target_logger.propagate = False


def configure_logging() -> None:
    """Configure application and dependency loggers once."""

    app_logger = logging.getLogger("backend")
    if getattr(app_logger, _CONFIGURED_ATTR, False):
        return

    console_level = resolve_log_level()
    handlers = _build_handlers(console_level)

    app_logger.setLevel(logging.DEBUG)
    _attach_handlers(app_logger, handlers)

    # RequestTimingMiddleware is the canonical HTTP request log. Keeping
    # uvicorn.access at WARNING avoids logging every request twice.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.setLevel(logging.INFO)
        _attach_handlers(uvicorn_logger, handlers)

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.WARNING)
    _attach_handlers(access_logger, handlers)

    # SQL statement logging is extremely noisy and can expose parameter values.
    # Enable it manually during a focused diagnostic session instead of by default.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    setattr(app_logger, _CONFIGURED_ATTR, True)

    app_logger.info(
        "Logging configured",
        extra={
            "env": settings.ENV,
            "console_level": logging.getLevelName(console_level),
            "file_logging": is_development(),
        },
    )


configure_logging()


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("backend."):
        name = f"backend.{name.lstrip('.')}"
    return logging.getLogger(name)
