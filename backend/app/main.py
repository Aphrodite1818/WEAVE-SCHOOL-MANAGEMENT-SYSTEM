"""FastAPI application factory and router registration."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import text

import app.models  # noqa: F401
from app.config.database import engine
from app.config.logging import get_logger
from app.config.settings import settings
from app.core.cache.redis import close_redis, connect_redis, redis_health_check
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware.platform_lockdown import PlatformLockdownMiddleware
from app.core.middleware.request_timing import RequestTimingMiddleware
from app.core.middleware.security_headers import SecurityHeadersMiddleware
from app.core.middleware.trusted_proxy import TrustedProxyHeadersMiddleware
from app.modules.announcements.router import (
    feed_router as announcement_feed_router,
    superadmin_router as superadmin_announcement_router,
    teacher_router as teacher_announcement_router,
    tenant_admin_router as tenant_admin_announcement_router,
)
from app.modules.attendance.router import (
    parent_router as parent_attendance_router,
    student_router as student_attendance_router,
    teacher_router as teacher_attendance_router,
    tenant_admin_router as tenant_admin_attendance_router,
)
from app.modules.auth.router import router as auth_router
from app.modules.bulk_imports.router import router as bulk_import_router
from app.modules.classes.class_subjects_router import router as class_subjects_router
from app.modules.classes.router import router as class_router
from app.modules.email_outbox.router import router as email_outbox_router
from app.modules.media.router import router as media_router
from app.modules.metrics.events import register_metrics_cache_invalidation_events
from app.modules.metrics.router import router as metrics_router
from app.modules.parents.router import router as parent_router
from app.modules.report_cards.fixed_router import router as fixed_report_card_router
from app.modules.report_cards.router import (
    parent_router as parent_report_card_router,
    student_router as student_report_card_router,
    tenant_admin_router as tenant_admin_report_card_router,
)
from app.modules.school_calendar.admin_router import router as school_calendar_admin_router
from app.modules.school_calendar.shared_router import router as school_calendar_shared_router
from app.modules.search.router import router as tenant_search_router
from app.modules.student_academics.assessment_config_router import (
    router as assessment_config_router,
)
from app.modules.student_academics.grading_readiness_router import (
    router as grading_readiness_router,
)
from app.modules.student_academics.grading_scale_lifecycle_router import (
    router as grading_scale_lifecycle_router,
)
from app.modules.student_academics.open_session_config_router import (
    router as open_session_config_router,
)
from app.modules.student_academics.result_limits_router import (
    admin_router as result_limits_admin_router,
    student_router as result_limits_student_router,
    teacher_router as result_limits_teacher_router,
)
from app.modules.student_academics.router import (
    parent_router as parent_academic_router,
    student_router as student_academic_router,
    teacher_router as teacher_academic_router,
    tenant_admin_router as tenant_admin_academic_router,
)
from app.modules.student_academics.session_closure_router import router as session_closure_router
from app.modules.student_academics.student_subject_cards_router import (
    router as student_subject_cards_router,
)
from app.modules.student_academics.write_guard import (
    ensure_admin_academic_write_window,
    ensure_teacher_academic_write_window,
)
from app.modules.students.router import router as student_router
from app.modules.subjects.router import router as subject_router
from app.modules.subscriptions.router import router as subscriptions_router
from app.modules.superadmin.router import router as superadmin_router
from app.modules.teachers.router import router as teacher_router
from app.modules.tenant_admins.router import router as tenant_admin_router
from app.modules.tenant_branding.router import router as tenant_branding_router
from app.tenant_management.router import router as tenant_router

logger = get_logger(__name__)

RouteKey = tuple[str, str]
_TENANT_ADMIN_ACADEMIC_OVERRIDES: set[RouteKey] = {
    ("POST", "/tenant-admin/academics/results"),
    ("PATCH", "/tenant-admin/academics/results/{result_id}/status"),
    ("GET", "/tenant-admin/academics/grading-scales/readiness-preview"),
    ("PATCH", "/tenant-admin/academics/sessions/{session_id}"),
    ("POST", "/tenant-admin/academics/sessions/{session_id}/close-and-progress"),
}
_TEACHER_ACADEMIC_OVERRIDES: set[RouteKey] = {
    ("POST", "/teachers/academics/results"),
}
_STUDENT_ACADEMIC_OVERRIDES: set[RouteKey] = {
    ("GET", "/students/academics/subjects"),
}


def _exclude_overridden_routes(router: APIRouter, overrides: set[RouteKey]) -> None:
    """Remove legacy handlers superseded by dedicated canonical routers."""

    router.routes[:] = [
        route
        for route in router.routes
        if not (
            isinstance(route, APIRoute)
            and any((method, route.path) in overrides for method in route.methods)
        )
    ]


def _prepare_academic_routers() -> None:
    """Ensure aggregate academic routers do not duplicate canonical handlers."""

    _exclude_overridden_routes(
        tenant_admin_academic_router,
        _TENANT_ADMIN_ACADEMIC_OVERRIDES,
    )
    _exclude_overridden_routes(
        teacher_academic_router,
        _TEACHER_ACADEMIC_OVERRIDES,
    )
    _exclude_overridden_routes(
        student_academic_router,
        _STUDENT_ACADEMIC_OVERRIDES,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage shared application resources."""

    _ = app
    logger.info("Starting Weave API")
    await connect_redis()
    try:
        yield
    finally:
        logger.info("Closing Redis and database resources")
        await close_redis()
        await engine.dispose()


async def _database_health_check() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed.")
        return False


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    register_metrics_cache_invalidation_events()
    _prepare_academic_routers()

    app = FastAPI(
        title="Weave Assistant",
        description="School management and academic workflow API",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    middleware_options: dict[str, Any] = {
        "allow_origins": settings.ALLOWED_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.is_development:
        middleware_options["allow_origin_regex"] = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    app.add_middleware(PlatformLockdownMiddleware)
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        allow_docs_cdn=settings.is_development,
        strict_transport_security=settings.is_production_like,
    )
    app.add_middleware(CORSMiddleware, **middleware_options)
    # Added last so forwarding headers are normalized before every other middleware.
    app.add_middleware(TrustedProxyHeadersMiddleware)
    register_exception_handlers(app)

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(superadmin_router, prefix="/api/v1")
    app.include_router(tenant_admin_router, prefix="/api/v1/tenant-admin", tags=["Tenant Admin"])
    app.include_router(media_router, prefix="/api/v1/tenant-admin")
    app.include_router(tenant_branding_router, prefix="/api/v1/tenant-admin")
    app.include_router(bulk_import_router, prefix="/api/v1/tenant-admin")
    app.include_router(email_outbox_router, prefix="/api/v1/tenant-admin")
    app.include_router(tenant_router, prefix="/api/v1/tenants", tags=["Tenants"])
    app.include_router(teacher_router, prefix="/api/v1/teachers", tags=["Teachers"])
    app.include_router(student_router, prefix="/api/v1/students", tags=["Students"])
    app.include_router(parent_router, prefix="/api/v1")
    app.include_router(subject_router, prefix="/api/v1/subjects", tags=["Subjects"])
    app.include_router(class_router, prefix="/api/v1", tags=["Classes"])
    app.include_router(class_subjects_router, prefix="/api/v1", tags=["Class Subjects"])
    app.include_router(superadmin_announcement_router, prefix="/api/v1")
    app.include_router(tenant_admin_announcement_router, prefix="/api/v1")
    app.include_router(teacher_announcement_router, prefix="/api/v1")
    app.include_router(announcement_feed_router, prefix="/api/v1")
    app.include_router(metrics_router, prefix="/api/v1")

    app.include_router(result_limits_admin_router, prefix="/api/v1")
    app.include_router(result_limits_teacher_router, prefix="/api/v1")
    app.include_router(result_limits_student_router, prefix="/api/v1")
    app.include_router(grading_readiness_router, prefix="/api/v1")
    app.include_router(student_subject_cards_router, prefix="/api/v1")
    app.include_router(open_session_config_router, prefix="/api/v1")
    app.include_router(session_closure_router, prefix="/api/v1")
    app.include_router(school_calendar_admin_router, prefix="/api/v1")
    app.include_router(school_calendar_shared_router, prefix="/api/v1")
    app.include_router(tenant_admin_attendance_router, prefix="/api/v1")
    app.include_router(teacher_attendance_router, prefix="/api/v1")
    app.include_router(student_attendance_router, prefix="/api/v1")
    app.include_router(parent_attendance_router, prefix="/api/v1")

    admin_write_guard = [Depends(ensure_admin_academic_write_window)]
    teacher_write_guard = [Depends(ensure_teacher_academic_write_window)]

    app.include_router(
        tenant_admin_academic_router,
        prefix="/api/v1",
        dependencies=admin_write_guard,
    )
    app.include_router(assessment_config_router, prefix="/api/v1", dependencies=admin_write_guard)
    app.include_router(
        grading_scale_lifecycle_router,
        prefix="/api/v1",
        dependencies=admin_write_guard,
    )
    app.include_router(
        teacher_academic_router,
        prefix="/api/v1",
        dependencies=teacher_write_guard,
    )
    app.include_router(student_academic_router, prefix="/api/v1")
    app.include_router(parent_academic_router, prefix="/api/v1")
    app.include_router(fixed_report_card_router, prefix="/api/v1")
    app.include_router(
        tenant_admin_report_card_router,
        prefix="/api/v1",
        dependencies=admin_write_guard,
    )
    app.include_router(student_report_card_router, prefix="/api/v1")
    app.include_router(parent_report_card_router, prefix="/api/v1")
    app.include_router(tenant_search_router, prefix="/api/v1")
    app.include_router(subscriptions_router, prefix="/api/v1")

    @app.get("/health/live", tags=["Health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health", tags=["Health"])
    @app.get("/health/ready", tags=["Health"])
    async def readiness() -> JSONResponse:
        database_ok = await _database_health_check()
        redis_ok = await redis_health_check()
        ready = database_ok and redis_ok
        return JSONResponse(
            status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "ready" if ready else "unavailable",
                "dependencies": {
                    "database": "ok" if database_ok else "unavailable",
                    "redis": "ok" if redis_ok else "unavailable",
                },
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import logging

    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
