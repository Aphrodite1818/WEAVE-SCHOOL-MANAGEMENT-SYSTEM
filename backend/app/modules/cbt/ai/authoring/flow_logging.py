"""Dedicated logging for the CBT AI question-generation flow.

Development keeps this diagnostic stream out of the terminal by writing it to
its own rotating file. Staging and production emit the same stream to stdout so
platform logging can collect it normally.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from app.config.logging import ContextFormatter, JsonFormatter
from app.config.settings import BASE_DIR, settings

QUESTION_GENERATION_LOG_DIR = BASE_DIR / "logs"
QUESTION_GENERATION_LOG_FILE = QUESTION_GENERATION_LOG_DIR / "cbt_ai_question_generation.log"
_CONFIGURED_ATTR = "_weave_cbt_ai_question_generation_configured"


def _is_development() -> bool:
    return bool(getattr(settings, "is_development", False))


def _build_handler() -> logging.Handler:
    if _is_development():
        QUESTION_GENERATION_LOG_DIR.mkdir(exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            filename=QUESTION_GENERATION_LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            ContextFormatter(
                "%(asctime)s | %(levelname)-8s | source=%(source)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        return handler

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(JsonFormatter())
    return handler


def get_question_generation_logger(component: str) -> logging.Logger:
    """Return a logger isolated to the CBT AI authoring diagnostic stream."""

    normalized_component = component.strip().replace(" ", "_") or "flow"
    logger = logging.getLogger(f"cbt.ai.question_generation.{normalized_component}")

    if not getattr(logger, _CONFIGURED_ATTR, False):
        logger.handlers.clear()
        logger.addHandler(_build_handler())
        logger.setLevel(logging.DEBUG if _is_development() else logging.INFO)
        logger.propagate = False
        setattr(logger, _CONFIGURED_ATTR, True)

    return logger
