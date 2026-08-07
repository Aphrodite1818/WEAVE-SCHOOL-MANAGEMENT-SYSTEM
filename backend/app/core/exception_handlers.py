# ====================================== #
#      core/exception_handlers.py        #
# ====================================== #

"""Application exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import get_logger
from app.config.sentry import capture_exception
from app.core.exceptions import (
    AppException,
    ImportParserError,
    ImportTemplateNotFoundError,
)
from app.modules.superadmin.security_alert_service import (
    SecurityAlertService,
)


logger = get_logger(__name__)


def _request_context(
    request: Request,
    status_code: int,
) -> dict[str, dict[str, object]]:
    """Build safe request and actor context for Sentry."""

    actor = getattr(
        request.state,
        "actor",
        None,
    )

    return {
        "request": {
            "request_id": getattr(
                request.state,
                "request_id",
                None,
            ),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
        },
        "actor": {
            "actor_type": getattr(
                actor,
                "actor_type",
                None,
            ),
            "actor_id": getattr(
                actor,
                "id",
                None,
            ),
            "tenant_id": getattr(
                actor,
                "tenant_id",
                None,
            ),
        },
    }


def _capture_http_exception(
    request: Request,
    exc: BaseException,
    status_code: int,
) -> None:
    """Capture one server-side HTTP exception."""

    capture_exception(
        exc,
        tags={
            "error_boundary": "fastapi",
            "http_status": status_code,
        },
        contexts=_request_context(
            request,
            status_code,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register application exception handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        """Return an application error and run queued notifications."""

        log_fn = (
            logger.warning
            if exc.status_code < 500
            else logger.error
        )

        log_fn(
            "Application error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        )

        # Expected application errors such as 400, 401, 403,
        # 404, 409, and 422 are not Sentry incidents.
        if exc.status_code >= 500:
            _capture_http_exception(
                request,
                exc,
                exc.status_code,
            )

        content = {
            "detail": exc.detail,
        }

        if getattr(exc, "payload", None):
            content.update(exc.payload)

        # FastAPI automatically runs BackgroundTasks after normal
        # responses. Security flows can commit containment changes
        # and then raise AppException. Preserve those tasks.
        background_tasks = (
            SecurityAlertService.take_pending_background_tasks()
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(
                exc,
                "headers",
                None,
            ),
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
            content={
                "detail": str(exc),
            },
        )

    @app.exception_handler(ImportTemplateNotFoundError)
    async def import_template_error_handler(
        request: Request,
        exc: ImportTemplateNotFoundError,
    ) -> JSONResponse:
        """Return clean 400 responses for unsupported templates."""

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
            content={
                "detail": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""

        logger.exception(
            "Unhandled server error",
            extra={
                "method": request.method,
                "path": request.url.path,
            },
        )

        _capture_http_exception(
            request,
            exc,
            500,
        )

        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
            },
        )