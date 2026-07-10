#======================================#
#      core/exception_handlers.py      #
#======================================#

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import get_logger
from app.core.exceptions import (
    AppException,
    ImportParserError,
    ImportTemplateNotFoundError,
)

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register application exception handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Handle application-specific exceptions."""
        log_fn = logger.warning if exc.status_code < 500 else logger.error
        log_fn(
            "Application error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        )
        headers = getattr(exc, "headers", None)
        content = {"detail": exc.detail}
        if getattr(exc, "payload", None):
            content.update(exc.payload)
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=headers,
        )

    @app.exception_handler(ImportParserError)
    async def import_parser_error_handler(
        request: Request,
        exc: ImportParserError,
    ) -> JSONResponse:
        """Return clean 400 responses for invalid import files."""

        logger.warning(
            "Bulk import parser error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "detail": str(exc),
            },
        )
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ImportTemplateNotFoundError)
    async def import_template_error_handler(
        request: Request,
        exc: ImportTemplateNotFoundError,
    ) -> JSONResponse:
        """Return clean 400 responses for unsupported import templates."""

        logger.warning(
            "Bulk import template error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "detail": str(exc),
            },
        )
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception(
            "Unhandled server error",
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
