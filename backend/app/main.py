#======================================#
#              main.py                 #
#======================================#

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.logging import get_logger
from app.config.database import engine
from app.config.settings import settings
from app.core.cache.redis import close_redis, connect_redis
from app.core.exception_handlers import register_exception_handlers
from app.modules import import_model_modules
from app.modules.superadmin.router import router as superadmin_router
from app.modules.auth.router import router as auth_router
from app.modules.tenant_admins.router import router as tenant_admin_router
from app.tenant_management.router import router as tenant_router
from app.modules.subjects.router import router as subject_router
from app.modules.students.admin_access_router import router as student_admin_access_router
from app.modules.students.router import router as student_router
from app.modules.parents.router import router as parent_router
from app.modules.teachers.router import router as teacher_router
from app.modules.classes.router import router as class_router
from app.modules.classes.class_subjects_router import router as class_subjects_router
from app.modules.announcements.router import (
    feed_router as announcement_feed_router,
    superadmin_router as superadmin_announcement_router,
    teacher_router as teacher_announcement_router,
    tenant_admin_router as tenant_admin_announcement_router,
)
from app.modules.metrics.router import router as metrics_router
from app.modules.student_academics.router import (
    parent_router as parent_academic_router,
    student_router as student_academic_router,
    teacher_router as teacher_academic_router,
    tenant_admin_router as tenant_admin_academic_router,
)
from app.modules.report_cards.router import (
    parent_router as parent_report_card_router,
    student_router as student_report_card_router,
    tenant_admin_router as tenant_admin_report_card_router,
)
from app.modules.search.router import router as tenant_search_router
from app.modules.subscriptions.router import router as subscriptions_router


logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # fixed: was [None, Any, None]
    """Perform lifespan."""
    logger.info("Starting up — school-ai-assistant API")
    await connect_redis()
    try:
        yield
    finally:
        logger.info("Shutting down — closing Redis and DB connections")
        await close_redis()
        await engine.dispose()


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create app."""
    import_model_modules()

    app = FastAPI(
        title="LearnlyAI Assistant",
        description="WhatsApp-powered school management assistant API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    middleware_options = {
        "allow_origins": settings.ALLOWED_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.is_development:
        middleware_options["allow_origin_regex"] = (
            r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        )

    app.add_middleware(
        CORSMiddleware,
        **middleware_options,
    )

    # ── Exception Handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(superadmin_router, prefix="/api/v1")
    # Student access routes are registered before the wider tenant-admin router so
    # the refined access-code implementation handles the overlapping student paths.
    app.include_router(
        student_admin_access_router,
        prefix="/api/v1/tenant-admin",
        tags=["Tenant Admin"],
    )
    app.include_router(tenant_admin_router, prefix="/api/v1/tenant-admin", tags=["Tenant Admin"])
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
    app.include_router(tenant_admin_academic_router, prefix="/api/v1")
    app.include_router(teacher_academic_router, prefix="/api/v1")
    app.include_router(student_academic_router, prefix="/api/v1")
    app.include_router(parent_academic_router, prefix="/api/v1")
    app.include_router(tenant_admin_report_card_router, prefix="/api/v1")
    app.include_router(student_report_card_router, prefix="/api/v1")
    app.include_router(parent_report_card_router, prefix="/api/v1")
    app.include_router(tenant_search_router, prefix="/api/v1")
    app.include_router(subscriptions_router, prefix="/api/v1")

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        """Perform health."""
        return {"status": "ok"}

    return app


app = create_app()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging
    import uvicorn

    from app.config.logging import is_development, resolve_log_level

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=is_development(),
        log_config=None,
        log_level=logging.getLevelName(resolve_log_level()).lower(),
    )
