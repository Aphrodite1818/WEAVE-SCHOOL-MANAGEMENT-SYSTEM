# ====================================== #
#      core/exception_handlers.py        #
# ====================================== #

"""Application exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import get_logger
from app.core.exceptions import (
    AppException,
    ImportParserError,
    ImportTemplateNotFoundError,
)
from app.modules.superadmin.security_alert_service import SecurityAlertService


logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register application exception handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Return an application error, then run queued security notifications."""

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

        content = {"detail": exc.detail}
        if getattr(exc, "payload", None):
            content.update(exc.payload)

        # FastAPI automatically runs BackgroundTasks after normal route
        # responses. Security flows often commit containment changes and then
        # raise AppException (for example refresh-token reuse). Attach the
        # queued tasks to this exception response so the client receives the
        # rejection first and email delivery happens afterward.
        background_tasks = SecurityAlertService.take_pending_background_tasks()

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
            background=background_tasks,
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
