"""Minimal dev app for testing global parent/teacher account flows."""

from fastapi import FastAPI

from app.core.exception_handlers import register_exception_handlers
from app.modules import import_model_modules
from app.modules.account_flows.router import router as account_flow_router
from app.modules.auth.router import router as auth_router


import_model_modules()

app = FastAPI(title="Weave Account Flow Test API")

register_exception_handlers(app)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(account_flow_router, prefix="/api/v1")
